# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011 - Nicolas AGIUS <nagius@astek.fr>
# $Id:$

###########################################################################
#
# This file is part of cxm.
#
# cxm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###########################################################################


from twisted.application.service import Service
from twisted.internet import reactor, error
from twisted.internet.defer import Deferred
from twisted.internet import defer, threads
import time
from twisted.spread import pb
from sets import Set

from dnscache import DNSCache
from messages import *
import logs as log
from heartbeats import * 
import core
from node import Node
from xencluster import XenCluster, InstantiationError
from rpc import RPCService, NodeRefusedError, RPCRefusedError
from diskheartbeat import DiskHeartbeat
from agent import Agent


class MasterService(Service):

	# Possible master roles (for self.role)
	RL_ACTIVE  = "active"			# Active master, aka master
	RL_PASSIVE = "passive"  		# Passive master, aka slave
	RL_JOINING = "joining"			# When trying to connect to the cluster
	RL_LEAVING = "leaving"			# When trying to leave the cluster
	RL_VOTING  = "voting"			# During election stage
	RL_ALONE   = "alone"			# Before joining

	# Possible states, aka error mode (for self.state)
	ST_NORMAL    = "normal" 		# Normal operations
	ST_RECOVERY  = "recovery"		# When a failed node is being recovered
	ST_PANIC     = "panic"			# "I don't do anything" mode

	# Elections and failover timeouts
	TM_TALLY	= 1					# Records vote for 1 sec
	TM_WATCHDOG	= 3					# Check for failure every 3 sec
	TM_MASTER	= TM_WATCHDOG*2		# Re-elect master if no response wihtin 6 sec
	TM_SLAVE	= TM_WATCHDOG*3		# Trigger failover if no response within 9 sec (master + tally + rounding)

	def __init__(self):
		self.role			= MasterService.RL_ALONE		# Current role of this node
		self.state			= MasterService.ST_NORMAL		# Current cluster error status
		self.master			= None							# Name of the active master
		self.masterLastSeen	= 0								# Timestamp for master failover
		self.status			= dict()						# Whole cluster status
		self.localNode		= Node(DNSCache.getInstance().name)
		self.disk			= DiskHeartbeat()
		self.s_slaveHb		= SlaveHearbeatService(self)
		self.s_masterHb		= MasterHeartbeatService(self)
		self.s_rpc			= RPCService(self) 

		# Watchdogs for failover
		self.l_slaveDog		= task.LoopingCall(self.checkMasterHeartbeat)
		self.l_masterDog	= task.LoopingCall(self.checkSlaveHeartbeats)

		# Election Stuff
		self.ballotBox 			= None		# All received votes
		self.currentElection	= None		# Election name, none if no pending election
		self.f_tally			= None		# IDelayedCall used to trigger countVotes()
		self.lastTallyDate		= 0			# Timestamp for debbuging elections
		self.panicRequested		= False		# True if panic is requested during election

	def startService(self):
		Service.startService(self)

		self._messagePort=reactor.listenUDP(core.cfg['UDP_PORT'], UDPListener(self.dispatchMessage))
		reactor.callLater(2, self.joinCluster)

	def stopService(self):
		def exit(result):
			log.info("Stopping daemon...")
			if not reactor._stopped:
				reactor.stop()

		if self.running:
			Service.stopService(self)

			# Stop receiving cluster messages
			self._messagePort.stopListening()
			self.s_rpc.stopService().addErrback(log.err)

			# Cleanly leave cluster
			d = self.leaveCluster()
			d.addErrback(log.err)
			d.addBoth(exit) # Even if there are errors
			return d
		else:
			return defer.succeed(None)
	
	def panic(self, noCheck=False):
		""" 
		Engage panic mode.
		Use noCheck=True if you want to panic whatever the cluster role.
		"""

		def panicFailed(reason):
			log.emerg("Panic query failed: %s." % (reason.getErrorMessage()))
			self.panic(True)

		if self.state == MasterService.ST_PANIC:
			log.emerg("Panic mode already engaged.")

		elif self.role == MasterService.RL_ACTIVE or noCheck:
			log.emerg("SYSTEM FAILURE: Panic mode engaged.")
			log.emerg("This is a critical error. You should bring your ass over here, right now.")
			log.emerg("Please check logs and be sure of what you're doing before re-engaging normal mode.")
			self.state=MasterService.ST_PANIC

			# TODO + stop LB
			if self.l_masterDog.running:
				self.l_masterDog.stop()

		elif self.role == MasterService.RL_VOTING:
			# No master during election stage: waiting next master
			log.warn("Panic mode requested during election stage: delaying.")
			self.panicRequested=True

		elif self.role == MasterService.RL_PASSIVE:
			log.warn("I'm slave: asking master to engage panic mode...")

			agent=Agent()
			d=agent.panic()
			d.addErrback(panicFailed)
			d.addErrback(log.err)

		else: # RL_ALONE or RL_JOINING or RL_LEAVING
			log.warn("I'm not in a running state (master or slave). Cannot engage panic mode.")
			raise RPCRefusedError("Not in running state")


	# Properties accessors
	###########################################################################

	def getStatus(self):
		return self.status
	
	def getState(self):
		return self.state
	
	def getLocalNode(self):
		return self.localNode

	def getActiveMaster(self):
		return self.master
	
	def getNodesList(self):
		return self.status.keys()

	def isActive(self):
		return self.role == MasterService.RL_ACTIVE

	def isInPanic(self):
		return self.state == MasterService.ST_PANIC

	# Messages handlers
	###########################################################################

	def dispatchMessage(self, data, host):
		dispatcher = {
			"slavehb" : self.updateNodeStatus,
			"masterhb" : self.updateMasterStatus,
			"voterequest" : self.voteForNewMaster,
			"voteresponse" : self.recordVote,
		}

		try:
			msg=MessageHelper.get(data, host)
			log.debugd("Received", msg)
			dispatcher[msg.type()](msg)
		except (MessageError, KeyError), e:
			log.err("Bad message from %s : %s , %s" % (host,data,e))
		except IDontCareException:
			pass # Discard useless messages

	def updateNodeStatus(self, msg):

		if self.role != MasterService.RL_ACTIVE:
			# Some slave HB could reach us during election...
			if self.role == MasterService.RL_PASSIVE:
				log.warn("Received slave heartbeat from %s while we're not master." % (msg.node))
			return

		# Check origin of message
		if msg.node not in self.status:
			log.warn("Received slave heartbeat from unknown node %s." % (msg.node))
			return

		now=int(time.time())
		self.status[msg.node]={'timestamp': now, 'offset': now-msg.ts, 'vms': msg.vms}

	def updateMasterStatus(self, msg):

		if self.master is None:
			self.master=msg.node
			log.info("Found master at %s." % (self.master))
		else:
			# Check origin of message if we known the cluster members
			if msg.node not in self.status:
				log.warn("Received master heartbeat from unknown node %s." % (msg.node))
				return

		# Active master's checks 
		if self.role == MasterService.RL_ACTIVE:
			if self.master == msg.node:
				return		# Discard our own master heartbeat
			else:
				# Usecase #8: partition ended with many master
				log.warn("Received another master's heartbeat from %s ! Trying to recover from partition..." % (msg.node))
				self.triggerElection().addErrback(log.err) 

				# Propagate panic mode from another master
				if msg.state == MasterService.ST_PANIC:
					log.warn("Concurrent master is in panic mode, so we should be too.")
					self.panic()
				return

		# Passive master's checks
		if self.master != msg.node:
			log.warn("Received master heartbeat from a wrong master %s !" % (msg.node))
			return

		# Check error mode change to panic
		if not self.isInPanic() and msg.state == MasterService.ST_PANIC:
			log.emerg("SYSTEM FAILURE: Panic mode has been engaged by master.")

		# Keep a backup of the active master's state and status
		self.status=msg.status
		self.state=msg.state
		self.masterLastSeen=int(time.time())

	def voteForNewMaster(self, msg):
		# Elections accepted even if in panic mode

		def sendVote(result):
			log.info("Sending our vote...")
			result.sendMessage()
			port.stopListening()

		# Check origin of message
		if msg.node not in self.status:
			log.warn("Received vote request from unknown node %s." % (msg.node))
			return

		# Discard current election if there is a new one
		if self.role == MasterService.RL_VOTING:
			log.warn("Previous election aborded: new vote request received.")
			try:
				self.f_tally.cancel()
			except:
				pass

		log.info("Vote request received from %s." % (msg.node))
		self.currentElection=msg.election

		# Discard vote request if we are leaving
		if self.role == MasterService.RL_LEAVING:
			log.info("Vote request ignored: we are leaving this cluster.")
			return

		# Stop heartbeating
		self._stopSlave()
		if self.role == MasterService.RL_ACTIVE:
			self._stopMaster()

		# Prepare election
		self.role=MasterService.RL_VOTING
		self.ballotBox=dict()
		self.f_tally=reactor.callLater(MasterService.TM_TALLY, self.countVotes) # Timout of election stage

		# Send our vote
		d = Deferred()
		port = reactor.listenUDP(0, UDPSender(d, lambda: MessageVoteResponse().forge(self.currentElection)))
		d.addCallback(sendVote)
		d.addErrback(log.err)

	def recordVote(self, msg):
		# Check origin of message
		if msg.node not in self.status:
			log.warn("Vote received from unknown node %s." % (msg.node))
			return

		if self.role != MasterService.RL_VOTING:
			log.warn("Vote received from %s but it's not election time !" % (msg.node))
			return

		if self.currentElection != msg.election:
			log.warn("Vote received for another election from %s. Discarding." % (msg.node))
			return

		self.ballotBox[msg.ballot]=msg.node

	def countVotes(self):
		if self.role != MasterService.RL_VOTING:
			log.warn("Tally triggered but it's not election time !")
			return

		if type(self.ballotBox) != dict or len(self.ballotBox) == 0:
			log.emerg("No vote received ! There is a critical network failure.")
			self.panic(True) # noCheck=True because role is not consistent
			return

		# Select election winner
		self.currentElection=None
		self.lastTallyDate=int(time.time())
		self.master=self.ballotBox[max(self.ballotBox.keys())]
		log.info("New master is %s." % (self.master))
		self._startSlave()

		if self.master == DNSCache.getInstance().name:
			log.info("I'm the new master.")
			self.role=MasterService.RL_ACTIVE
			self._startMaster()
		else:
			self.role=MasterService.RL_PASSIVE
		
		if self.panicRequested:
			log.warn("Engaging panic mode requested during election stage.")
			self.panicRequested=False
			self.panic()
	
	# Passive master's stuff (slave)
	###########################################################################

	def _stopSlave(self):
		self.s_slaveHb.stopService().addErrback(log.err)
		if self.l_slaveDog.running:
			self.l_slaveDog.stop()

	def _startSlave(self):
		def slaveWatchdogFailed(reason):
			log.emerg("Master Heartbeat checks failed: %s." % (reason.getErrorMessage()))
			# Stop slave heartbeat to tell master we have a problem, but if we are here, 
			# there is no more master, and so, we cannot ensure that panic mode will be propagated.
			# Hope that another node will trigger an election... and fence me.
			self.s_slaveHb.stopService()  
			log.emerg("This is an unrecoverable error: FENCE ME !")
			self.panic(True) # noCheck because there is no master

		def startSlaveWatchdog():
			if not self.l_slaveDog.running:
				d=self.l_slaveDog.start(MasterService.TM_WATCHDOG)
				d.addErrback(slaveWatchdogFailed)
				d.addErrback(log.err)

		# Start slave heartbeat
		self.s_slaveHb.startService()

		# Start slave's watchdog for master failover
		reactor.callLater(2, startSlaveWatchdog)


	# Active master's stuff
	###########################################################################

	def _stopMaster(self):

		if self.state == MasterService.ST_RECOVERY:
			# Recovery will be re-run by next master (VM on current host may be lost)
			log.warn("Stopping master during a recovery process !")

		# Send a last heartbeat before stopping
		self.s_masterHb.forcePulse() 
		self.s_masterHb.stopService().addErrback(log.err)
		if self.l_masterDog.running:
			self.l_masterDog.stop()
		# TODO stop LB service

	def _startMaster(self):
		def masterWatchdogFailed(reason):
			log.emerg("Slave heartbeat checks failed: %s." % (reason.getErrorMessage()))
			self.panic()

		def startMasterWatchdog():
			if not self.l_masterDog.running:
				d=self.l_masterDog.start(MasterService.TM_WATCHDOG)
				d.addErrback(masterWatchdogFailed)
				d.addErrback(log.err)

		# Start master heartbeat
		self.s_masterHb.startService()

		# Check state of previous master
		if self.state == MasterService.ST_RECOVERY:
			log.warn("Previous master was recovering something: re-enabling failover.")
			# Force normal mode to re-run failover
			self.state=MasterService.ST_NORMAL

		# Start master's watchdog for slaves failover
		reactor.callLater(2, startMasterWatchdog)
		# TODO start LB service


	def registerNode(self, name):
		def validHostname(result):
			try:
				self.disk.make_slot(name)
			except DiskHeartbeatError, e:
				raise NodeRefusedError("Disk heartbeat failure: %s" % (e))

			self.status[name]={'timestamp': 0, 'offset': 0, 'vms': []}
			log.info("Node %s has joined the cluster." % (name))
			
		def invalidHostname(reason):
			log.warn("Node %s has an invalid name. Refusing." % (name))
			raise NodeRefusedError(reason.getErrorMessage())
		
		if self.isInPanic():
			log.warn("I'm in panic. Cannot register %s." % (name))
			raise RPCRefusedError("Panic mode engaged")

		if self.role != MasterService.RL_ACTIVE:
			log.warn("I'm not master. Cannot register %s." % (name))
			raise RPCRefusedError("Not master")

		if name not in core.cfg['ALLOWED_NODES']:
			log.warn("Node %s not allowed to join this cluster. Refusing." % (name))
			raise NodeRefusedError("Node not allowed to join this cluster.")

		if name in self.status:
			log.warn("None %s is already joined ! Cannot re-join." % (name))
			raise NodeRefusedError("Node already in cluster")

		# Check if hostname is valid
		d=DNSCache.getInstance().add(name)
		d.addCallbacks(validHostname, invalidHostname)
		
		return d
			

	def _unregister(self, name):
		try:
			del self.status[name]
		except:
			pass

		try:
			self.disk.erase_slot(name)
		except DiskHeartbeatError, e:
			log.warn("Cannot erase slot: %s. You may have to reformat hearbeat disk." % (e))
		except Exception, e:
			log.err("Diskheartbeat failure: %s." % (e))
			self.panic()

		DNSCache.getInstance().delete(name)
		log.info("Node %s has been unregistered." % (name))

	def unregisterNode(self, name):
		# Can unregister node even if in panic mode

		if self.role != MasterService.RL_ACTIVE:
			log.warn("I'm not master. Cannot unregister %s." % (name))
			raise RPCRefusedError("Not master")

		if name not in self.status:
			log.warn("Unknown node %s try to quit the cluster." % (name))
			raise NodeRefusedError("Unknown node "+name)

		if name == DNSCache.getInstance().name:
			log.warn("I'm the master. Cannot self unregister.")
			raise NodeRefusedError("Cannot unregister master")

		self._unregister(name)
	

	def triggerElection(self):
		log.info("Asking a new election for cluster %s." % (core.cfg['CLUSTER_NAME']))

		d = Deferred()
		port = reactor.listenUDP(0, UDPSender(d, lambda: MessageVoteRequest().forge()))
		d.addCallback(lambda result: result.sendMessage())
		d.addCallback(lambda _: port.stopListening())

		return d

	def recoverFromPanic(self):
		if not self.isInPanic():
			log.warn("I'm not in panic. Cannot recover anything.")
			raise RPCRefusedError("Not in panic mode")

		# Only master can do recovery
		if self.role != MasterService.RL_ACTIVE:
			log.warn("I'm not master. Cannot recover from panic.")
			raise RPCRefusedError("Not master")

		# Back to normal mode 
		log.info("Recovering from panic mode. Back to normals operations.")
		self.state=MasterService.ST_NORMAL
		self.s_masterHb.forcePulse()
		d=self.triggerElection()

		return d


	# Passive master's stuff
	###########################################################################

	def leaveCluster(self):

		def masterConnected(obj):
			d = obj.callRemote("unregister",DNSCache.getInstance().name)
			d.addErrback(log.err)
			d.addBoth(lambda _: rpcConnector.disconnect())
			return d

		# Stop slave hearbeat and watchdog
		self._stopSlave()

		previousRole=self.role
		self.role=MasterService.RL_LEAVING

		if previousRole == MasterService.RL_ACTIVE:

			# Self-delete our own record 
			self._unregister(DNSCache.getInstance().name)

			if len(self.status) <= 0:
				log.warn("I'm the last node, shutting down cluster.")
				d=defer.succeed(None)
			else:
				# New election only if there is at least one node
				d=self.triggerElection()
				d.addErrback(log.err)

			# Stop master hearbeat when vote request has been sent
			d.addBoth(lambda _: self._stopMaster())
		elif previousRole == MasterService.RL_PASSIVE:
			rpcFactory = pb.PBClientFactory()
			rpcConnector = reactor.connectTCP(self.master, core.cfg['TCP_PORT'], rpcFactory)
			d = rpcFactory.getRootObject()
			d.addCallback(masterConnected)
		else: # RL_ALONE or RL_JOINING or RL_VOTING
			if previousRole == MasterService.RL_VOTING:
				# Others nodes will re-trigger an election if we win this one
				log.warn("Quitting cluster during election stage !")

			d=defer.succeed(None)
		
		return d


	def joinCluster(self):

		def startHeartbeats():
			self._startSlave()
			self.s_rpc.startService()

			if self.role == MasterService.RL_ACTIVE:
				self._startMaster() 

		def joinRefused(reason):
			reason.trap(NodeRefusedError, RPCRefusedError)
			log.err("Join to cluster %s failed: Master %s has refused me: %s" % 
				(core.cfg['CLUSTER_NAME'], self.master, reason.getErrorMessage()))
			self.stopService()

		def joinAccepted(result):
			self.role=MasterService.RL_PASSIVE
			log.info("Join successfull, I'm now part of cluster %s." % (core.cfg['CLUSTER_NAME']))
			startHeartbeats()
			
		def masterConnected(obj):
			d = obj.callRemote("register",DNSCache.getInstance().name)
			d.addCallbacks(joinAccepted,joinRefused)
			d.addErrback(log.err)
			d.addBoth(lambda _: rpcConnector.disconnect())
			return d

		try:
			if self.master is None:
				# New active master
				if DNSCache.getInstance().name not in core.cfg['ALLOWED_NODES']:
					log.warn("I'm not allowed to create a new cluster. Exiting.")
					raise Exception("Cluster creation not allowed")

				if DiskHeartbeat.is_in_use():
					log.err("Heartbeat disk is in use but we are alone !")
					raise Exception("Heartbeat disk already in use")

				log.info("No master found. I'm now the new master of %s." % (core.cfg['CLUSTER_NAME']))
				self.role=MasterService.RL_ACTIVE
				self.master=DNSCache.getInstance().name
				self.status[self.master]={'timestamp': 0, 'offset': 0, 'vms': []}
				self.disk.make_slot(DNSCache.getInstance().name)
				startHeartbeats()

			else:
				# Passive master
				self.role=MasterService.RL_JOINING
				log.info("Trying to join cluster %s..." % (core.cfg['CLUSTER_NAME']))

				factory = pb.PBClientFactory()
				rpcConnector = reactor.connectTCP(self.master, core.cfg['TCP_PORT'], factory)
				d = factory.getRootObject()
				d.addCallback(masterConnected)
				d.addErrback(log.err)
		except Exception, e:
			log.err("Startup failed: %s. Shutting down." % (e))
			self.stopService()
			

	# Failover stuff
	###########################################################################

	def checkMasterHeartbeat(self):
		# Master failover is still possible even if in panic mode

		# Master failover only if we are a slave
		if self.role != MasterService.RL_PASSIVE:
			return 

		# Usecase #7: master lost
		if self.masterLastSeen+MasterService.TM_MASTER <= int(time.time()):
			log.warn("Broadcast heartbeat lost, master has disappeared.")
			return self.triggerElection()


	def checkSlaveHeartbeats(self):
		# Checks slaves timestamps only if we are active master
		if self.role != MasterService.RL_ACTIVE:
			return

		# No failover in panic mode
		if self.state == MasterService.ST_PANIC:
			return

		# No more failover if a recovery is running
		if self.state == MasterService.ST_RECOVERY:
			return

		# No failover if we are alone
		if len(self.status) <= 1:
			return

		# Check net heartbeat
		netFailed=Set()
		for name, values in self.status.items():
			if values['timestamp'] == 0:
				# Do nothing if first heartbeat has not been received yet
				continue

			if values['timestamp']+MasterService.TM_SLAVE <= int(time.time()):
				log.warn("Net heartbeat lost for %s." % (name))
				netFailed.add(name)

		# Get diskhearbeat timestamps
		try:
			tsDisk=self.disk.get_all_ts()
		except Exception, e:
			log.err("Diskheartbeat read failed: %s." % (e))
			raise
			
		# Compare node lists from net and disk hearbeat
		# Use Set's symmetric_difference
		if len(Set(tsDisk.keys()) ^ Set(self.status.keys())) != 0:
			log.err("Node list is inconsistent between net and disk heartbeats !")
			raise Exception("Inconsistent internal data")

		# Check disk heartbeat
		log.debugd("Diskhearbeat status:", tsDisk)
		diskFailed=Set()
		for name, timestamp in tsDisk.items():
			if timestamp == 0:
				# Do nothing if first heartbeat has not been received yet
				continue

			# Timestamp from diskheartbeat is taken from each node, not relative to the master's time
			# so we compute the absolute delta, with the time drift between nodes
			if abs(int(time.time()) - timestamp - self.status[name]['offset']) >= MasterService.TM_SLAVE:
				log.warn("Disk heartbeat lost for %s." % (name))
				diskFailed.add(name)

		# If we loose all heartbeats including master, there is a problem on localhost
		if len(diskFailed) >= len(self.status) or len(netFailed) >= len(self.status):
			log.err("Lost all heartbeats including me ! Maybe a clock screwed up ?")
			raise Exception("Master failure")

		# If there is more than 2 nodes, we can detect self-failure
		if len(self.status) > 2:

			# Usecase #6: lost all diskheartbeats (except me)
			if len(diskFailed-Set([self.localNode.get_hostname()])) >= len(self.status)-1:
				log.err("Lost all diskheartbeats !")
				# Just panic
				raise Exception("Storage failure")

			# Usecase #5: lost all netheartbeats (except me)
			if len(netFailed-Set([self.localNode.get_hostname()])) >= len(self.status)-1:
				log.err("Lost all netheartbeats ! This is a network failure.")
				log.err("I'm isolated, stopping master...")

				# Just stop master: we may be fenced by others node
				self._stopMaster()
				self.role=MasterService.RL_PASSIVE

				# And stop master failover to avoir restarting master...
				# So, there is no more heartbeats, next master will fence me or will panic
				self._stopSlave()
				# TODO: smarter recovery ?
				return

		def recoverFailed(reason):
			log.emerg("Recovery failed:", reason.getErrorMessage())
			self.panic()

		def recoverEnded(results):
			# Panic mode could have been engaged during recovery process
			if self.state != MasterService.ST_PANIC:
				self.state=MasterService.ST_NORMAL

			# Trigger panic mode if a recovery fail
			for success, result in results:
				if not success:
					recoverFailed(result)

		def recoverSucceeded(result, name):
			# result is the return code from XenCluster.recover()
			# If True: success, if False: maybe a partition

			if(result):
				log.info("Successfully recovered node %s." % (name))
				self._unregister(name)
			else:
				log.err("Partial failure, cannot recover", name)

		def instantiationFailed(reason):
			reason.trap(InstantiationError)

			failed=reason.value.value.keys()
			log.warn("Can't connect to", ", ".join(failed))

			# Delete failed nodes from cluster list
			running=self.getNodesList()
			for name in failed:
				running.remove(name)
			
			# Re-instanciate cluster without nodes in error
			d=XenCluster.getDeferInstance(running)
			d.addCallbacks(startRecover)
			return d

		def startRecover(result):
			ds=list()
			for name in netFailed|diskFailed:
				bothFailed=name in netFailed and name in diskFailed
				d=threads.deferToThread(result.recover, name, self.status[name]['vms'], not bothFailed)
				d.addCallback(recoverSucceeded, name)
				ds.append(d)

			dl=defer.DeferredList(ds, consumeErrors=1)
			dl.addCallback(recoverEnded)
			return dl


		# Usecase #4: Start recovery of failed nodes
		if len(netFailed)>0 or len(diskFailed)>0:
			self.state=MasterService.ST_RECOVERY
			log.info("Starting recovery process...")

			d=XenCluster.getDeferInstance(self.getNodesList())
			d.addCallbacks(startRecover, instantiationFailed)
			d.addErrback(recoverFailed)
			d.addErrback(log.err)



# vim: ts=4:sw=4:ai
