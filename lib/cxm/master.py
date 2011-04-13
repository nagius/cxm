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



from pprint import pprint

from twisted.application.service import Service
from twisted.internet import reactor, error
from twisted.internet.defer import Deferred
from twisted.internet import defer
import time
from twisted.spread import pb

from dnscache import DNSCache
from messages import *
import logs as log
from heartbeats import * 
import core
from node import Node
from rpc import RPCService, NodeRefusedError, RPCRefusedError
from diskheartbeat import DiskHeartbeat

# TODO A gérer : perte de connection xenapi / async ?
# TODO système de reload de la conf sur sighup et localrpc reload

# TODO add check disk nr_node
# TODO gérer cas partition + possibilité d'ajout de node pendant partition ?

core.cfg['QUIET']=True

CLUSTER_NAME="cltest" # TODO a passer en fichier
ALLOWED_NODES=['xen0node01.virt.s1.p.fti.net','xen0node02.virt.s1.p.fti.net','xen0node03.virt.s1.p.fti.net','xen0node04.virt.s1.p.fti.net']
PORT=6666


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
	ST_PARTITION = "partition"		# When a network failure separate cluster in two part
	ST_PANIC     = "panic"			# "I don't do anything" mode


	def __init__(self):
		self.role		= MasterService.RL_ALONE		# Current role of this node
		self.state		= MasterService.ST_NORMAL		# Current cluster error status
		self.master		= None							# Name of the active master
		self.status		= dict()						# Whole cluster status
		self.localNode	= Node(DNSCache.getInstance().name)
		self.disk		= DiskHeartbeat()
		self.l_check	= task.LoopingCall(self.checkHeartbeats)
		self.s_slaveHb	= SlaveHearbeatService(self)
		self.s_masterHb	= MasterHeartbeatService(self)
		self.s_rpc		= RPCService(self) 

		# Election Stuff
		self.ballotBox = None
		self.currentElection = None

	def startService(self):
		Service.startService(self)

		self._messagePort=reactor.listenUDP(PORT, UDPListener(self.dispatchMessage))
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

			# Stop slave hearbeats
			self.s_slaveHb.stopService().addErrback(log.err)

			# Cleanly leave cluster
			d = self.leaveCluster()
			d.addCallback(exit)
			d.addErrback(log.err)
			return d
		else:
			return defer.succeed(None)
	
	def panic(self):
		# Engage panic mode
		if self.role != MasterService.RL_ACTIVE:
			log.warn("I'm not master. Cannot engage panic mode.")
			raise RPCRefusedError("Not master")

		log.emerg("SYSTEM FAILURE: Panic mode engaged.")
		log.emerg("This is a critical error. You should bring your ass over here, right now.")
		log.emerg("Please check logs and be sure of what you're doing before re-engaging normal mode.")
		self.state=MasterService.ST_PANIC

		# TODO stop check heartbeat + stop LB


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
			dispatcher[msg.type()](msg)
		except (MessageError, KeyError), e:
			log.err("Bad message from %s : %s , %s" % (host,data,e))
		except IDontCareException:
			pass # Discard useless messages

	def updateNodeStatus(self, msg):
#		print "slave recu " + str(msg)

		if self.role != MasterService.RL_ACTIVE:
			print "Warning: received slave HB alors que pas master"
			return

		if msg.node not in self.status:
			print "Warning: received slave HB from unknown node"
			return
			

		now=int(time.time())
		self.status[msg.node]={'timestamp': now, 'offset': now-msg.ts, 'vms': msg.vms}
		#pprint(self.status)

	def updateMasterStatus(self, msg):

#		print "master recu " + str(msg)

		if self.master is None:
			self.master=msg.node
			log.info("Found master at %s." % (self.master))

		# Active master's checks 
		if self.role == MasterService.RL_ACTIVE:
			if self.master == msg.node:
				return		# Discard our own master heartbeat
			else:
				log.warn("Received another master's heartbeat ! Trying to recover from partition...")
				self.triggerElection().addErrback(log.err) # TODO test collision vote request

				# Propagate panic mode from another master
				if msg.state == MasterService.ST_PANIC:
					log.warn("Concurrent master is in panic mode, so we should be too.")
					self.panic()
				return

		# Passive master's checks
		if self.master != msg.node:
			log.err("Received master heartbeat from a wrong master %s !" % (msg.node))
			return

		# Check error mode change to panic
		if not self.isInPanic() and msg.state == MasterService.ST_PANIC:
			log.emerg("SYSTEM FAILURE: Panic mode has been engaged by master.")

		# Keep a backup of the active master's state and status
		self.status=msg.status
		self.state=msg.state
#		pprint(self.status)

	def voteForNewMaster(self, msg):
		# Elections accepted even if in panic mode

		def sendVote(result):
			log.info("Sending our vote...")
			result.sendMessage()
			port.stopListening()

		log.info("Vote request received from %s." % (msg.node))
		self.currentElection=msg.election

		# Discard vote request if we are leaving
		if self.role == MasterService.RL_LEAVING:
			log.info("Vote request ignored: we are leaving this cluster.")
			return

		# Stop heartbeating
		self.s_slaveHb.stopService().addErrback(log.err)
		if self.role == MasterService.RL_ACTIVE:
			self._stopMaster()

		# Prepare election
		self.role=MasterService.RL_VOTING
		self.ballotBox=dict()
		reactor.callLater(1, self.countVotes) # Timout of election stage

		# Send our vote
		d = Deferred()
		port = reactor.listenUDP(0, UDPSender(d, lambda: MessageVoteResponse().forge(self.currentElection)))
		d.addCallback(sendVote)
		d.addErrback(log.err)

	def recordVote(self, msg):
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
			self.panic()
			return

		self.currentElection=None
		self.master=self.ballotBox[max(self.ballotBox.keys())]
		log.info("New master is %s." % (self.master))
		self.s_slaveHb.startService()

		if self.master == DNSCache.getInstance().name:
			log.info("I'm the new master.")
			self.role=MasterService.RL_ACTIVE
			self._startMaster()
		else:
			self.role=MasterService.RL_PASSIVE
			


	# Active master's stuff
	###########################################################################

	def _stopMaster(self):
		self.s_masterHb.forcePulse() # Send a last hearbeat before stopping
		self.s_masterHb.stopService().addErrback(log.err)
		if self.l_check.running:
			self.l_check.stop()
		# TODO stop LB service

	def _startMaster(self):
		def checkHeartbeatsFailed(reason):
			log.emerg("Heartbeats' checks failed: %s." % (reason.getErrorMessage()))
			self.panic()

		self.s_masterHb.startService()
		d=self.l_check.start(1)
		d.addErrback(checkHeartbeatsFailed)
		d.addErrback(log.err)
		# TODO start LB service


	def registerNode(self, name):
		def validHostname(result):
			try:
				self.disk.make_slot(name)
			except DiskHeartbeatError, e:
				raise NodeRefusedError("Disk heartbeat failure: %s" % (e))

			self.status[name]={}
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

		if name not in ALLOWED_NODES:
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
		log.info("Asking a new election for cluster %s." % (CLUSTER_NAME))

		d = Deferred()
		port = reactor.listenUDP(0, UDPSender(d, lambda: MessageVoteRequest().forge()))
		d.addCallback(lambda result: result.sendMessage())
		d.addCallback(lambda _: port.stopListening())

		return d

	def recoverFromPanic(self):
		if not self.isInPanic():
			log.warn("I'm not in panic. Cannot recover anything.")
			raise RPCRefusedError("Not in panic")

		# Only master can do recovery
		if self.role != MasterService.RL_ACTIVE:
			log.warn("I'm not master. Cannot revover from panic.")
			raise RPCRefusedError("Not master")

		# Back to normal mode 
		log.info("Recovering from panic mode. Back to normals operations.")
		self.state=MasterService.ST_NORMAL
		self.s_masterHb.forcePulse()
		self.triggerElection()


	# Passive master's stuff
	###########################################################################

	def leaveCluster(self):

		def masterConnected(obj):
			d = obj.callRemote("unregister",DNSCache.getInstance().name)
			d.addErrback(log.err)
			d.addBoth(lambda _: rpcConnector.disconnect())
			return d

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

			# Stop master hearbeat when vote request has been sent
			d.addCallback(lambda _: self._stopMaster())
		elif previousRole == MasterService.RL_PASSIVE:
			rpcFactory = pb.PBClientFactory()
			rpcConnector = reactor.connectTCP(self.master, 8800, rpcFactory)
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
			self.s_slaveHb.startService()
			self.s_rpc.startService()

			if self.role == MasterService.RL_ACTIVE:
				self._startMaster() 
		
		def joinRefused(reason):
			reason.trap(NodeRefusedError, RPCRefusedError)
			log.err("Join to cluster %s failed: Master %s has refused me: %s" % 
				(CLUSTER_NAME, self.master, reason.getErrorMessage()))
			self.stopService()

		def joinAccepted(result):
			self.role=MasterService.RL_PASSIVE
			log.info("Join successfull, I'm now part of cluster %s." % (CLUSTER_NAME))
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
				if DNSCache.getInstance().name not in ALLOWED_NODES:
					log.warn("I'm not allowed to create a new cluster. Exiting.")
					raise Exception("Cluster creation not allowed")

				if DiskHeartbeat.is_in_use():
					log.err("Heartbeat disk is in use but we are alone !")
					raise Exception("Heartbeat disk already in use")

				log.info("No master found. I'm now the new master of %s." % (CLUSTER_NAME))
				self.role=MasterService.RL_ACTIVE
				self.master=DNSCache.getInstance().name
				self.status[self.master]={}
				self.disk.make_slot(DNSCache.getInstance().name)
				startHeartbeats()

			else:
				# Passive master
				self.role=MasterService.RL_JOINING
				log.info("Trying to join cluster %s..." % (CLUSTER_NAME))

				factory = pb.PBClientFactory()
				rpcConnector = reactor.connectTCP(self.master, 8800, factory)
				d = factory.getRootObject()
				d.addCallback(masterConnected)
				d.addErrback(log.err)
		except Exception, e:
			log.err("Startup failed: %s. Shutting down." % (e))
			self.stopService()
			

	# TODO 
	def checkHeartbeats(self):
		# Master failover still possible even if in panic mode
		pass


		# TODO comparaison liste node ? cas partition a voir
#		pprint(self.disk.get_all_ts())
		# TODO cas perte baie disque locale
		# TODO cas timestamps à 0


# vim: ts=4:sw=4:ai
