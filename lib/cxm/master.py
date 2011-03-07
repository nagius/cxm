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
from twisted.python import log
from twisted.spread import pb

from dnscache import DNSCache
from messages import *
from heartbeats import * 
import core
from node import Node

# TODO revoir log twisted + log syslog (surcharge log?) (function log() err() debug() )
# TODO A gérer : perte de connection xenapi / async ?
# TODO système de reload de la conf sur sighup et localrpc reload

core.cfg['QUIET']=True

CLUSTER_NAME="cltest" # TODO a passer en fichier
ALLOWED_NODES=['xen0node01.virt.s1.p.fti.net','xen0node02.virt.s1.p.fti.net']
PORT=6666


class MasterService(Service):

	# Possible master states (for self.state)
	ST_ACTIVE="active"
	ST_PASSIVE="passive"
	ST_JOINING= "joining"
	ST_ALONE="alone"

	def __init__(self):
		from rpc import RPCService # Here because of a cross-import conflict
		self.state=MasterService.ST_ALONE
		self.master=None		
		self.status=dict()	# Hold the whole cluster status
		self.localNode=Node(DNSCache.getInstance().name)
		self.s_slaveHb=SlaveHearbeatService(self)
		self.s_masterHb=MasterHeartbeatService(self.getStatus)
		self.s_rpc=RPCService(self) 

	def startService(self):
		Service.startService(self)

		self._messagePort=reactor.listenUDP(PORT, UDPListener(self.dispatchMessage))
		reactor.callLater(2, self.joinCluster)

	def stopService(self):
		def exit(result):
			log.msg("Stopping daemon...")
			if not reactor._stopped:
				reactor.stop()

		if self.running:
			Service.stopService(self)

			# Stop receiving cluster messages
			self._messagePort.stopListening()
			self.s_rpc.stopService().addErrback(log.err)

			# Cleanly leave cluster
			d = self.leaveCluster()
			# And then stop slave hearbeat
			d.addCallback(lambda _: self.s_slaveHb.stopService())
			d.addCallback(exit)
			d.addErrback(log.err)
			return d
		else:
			return defer.succeed(None)

	# Properties accessors
	def getStatus(self):
		return self.status
	
	def getLocalNode(self):
		return self.localNode

	def getActiveHostname(self):
		return self.master

	# Messages handlers
	def dispatchMessage(self, data, host):
		dispatcher = {
			"slavehb" : self.updateNodeStatus,
			"masterhb" : self.updateMasterStatus,
		}

		try:
			msg=MessageHelper.get(data, host)
			dispatcher[msg.type()](msg)
		except MessageError, e:
			print "Bad message from %s : %s , %s" % (host,data,e)
			pprint(e)
		except IDontCareException:
			pass # Discard useless messages

	def updateNodeStatus(self, msg):
		print "slave recu " + str(msg)

		if self.state is not MasterService.ST_ACTIVE:
			print "Warning: received slave HB alors que pas master"
			return

		if msg.node not in self.status:
			print "Warning: received slave HB from unknown node"
			return
			

		now=int(time.time())
		self.status[msg.node]={'timestamp': now, 'offset': now-msg.ts, 'vms': msg.vms}
		#pprint(self.status)

	def updateMasterStatus(self, msg):

		print "master recu " + str(msg)

		if self.master is None:
			self.master=msg.node
			print "New master at "+ self.master

		# Active master's checks 
		if self.state is MasterService.ST_ACTIVE:
			if self.master == msg.node:
				return		# Discard our own master heartbeat
			else:
				print "erruer deux master !" # TODO

		# Passive master's checks
		if self.master != msg.node:
			log.err("Error: received master heartbeat from a wrong master %s !" % (msg.node))
			return

		# Keep a backup of the active master's status
		self.status=msg.status
		pprint(self.status)


	# Active master's stuff
	def registerNode(self, name):
		if name not in ALLOWED_NODES:
			log.msg("Node %s not allowed to join this cluster. Refusing." % (name))
			raise NodeRefusedError("Node "+name+" not allowed to join this cluster.")

		if name in self.status:
			log.msg("None %s is already joined ! Cannot re-join." % (name))
			raise NodeRefusedError("Node "+name+" already in cluster.")

		try:
			DNSCache.getInstance().add(name)  # Check if hostname is valid
		except Exception, e:
			log.msg("Node %s has an invalid name. Refusing." % (name))
			raise NodeRefusedError(e)
			
		self.status[name]={}
		log.msg("Node %s has joined the cluster." % (name))

	def unregisterNode(self, name):
		if name not in self.status:
			log.msg("Unknown node %s try to quit the cluster." % (name))
			raise NodeRefusedError("Unknown node "+name)

		# TODO suppression HB disk
		del self.status[name]
		DNSCache.getInstance().delete(name)
		log.msg("Node %s has quit the cluster." % (name))
			

	# Passive master's stuff
	def leaveCluster(self):

		def masterConnected(obj):
			d = obj.callRemote("unregister",DNSCache.getInstance().name)
			d.addCallback(lambda _: rpcConnector.disconnect())
			d.addErrback(log.err)
			return d
			

		if self.state is MasterService.ST_ACTIVE:
			# TODO gestion election new master
			self.s_masterHb.stopService().addErrback(log.err)
			return defer.succeed(None)
		elif self.state is MasterService.ST_PASSIVE:
			factory = pb.PBClientFactory()
			rpcConnector = reactor.connectTCP(self.master, 8800, factory)
			d = factory.getRootObject()
			d.addCallback(masterConnected)
			d.addErrback(log.err)
			return d
		
		return defer.succeed(None)


	def joinCluster(self):
		def startHeartbeats():
			self.s_slaveHb.startService()
			self.s_rpc.startService()

			if self.state is MasterService.ST_ACTIVE:
				reactor.callLater(1,self.s_masterHb.startService) 
				# TODO service HB disk ici + init + check si utilisé
		
		def joinRefused(reason):
			reason.trap(NodeRefusedError)
			log.err("Join to cluster %s failed : Master %s has refused me: %s" % (CLUSTER_NAME, self.master, reason.getErrorMessage()))
			reactor.stop()

		def joinAccepted(result):
			self.state=MasterService.ST_PASSIVE
			log.msg("Join successfull, I'm now part of cluster %s." % (CLUSTER_NAME))
			startHeartbeats()
			
		def masterConnected(obj):
			d = obj.callRemote("register",DNSCache.getInstance().name)
			d.addCallbacks(joinAccepted,joinRefused)
			d.addErrback(log.err)
			d.addBoth(lambda _: rpcConnector.disconnect())
			return d


		if self.master is None:
			# New active master
			print " I am the new master"
			self.state=MasterService.ST_ACTIVE
			self.master=DNSCache.getInstance().name
			self.status[self.master]={}
			startHeartbeats()

		else:
			# Passive master
			self.state=MasterService.ST_JOINING
			print "joining cluster"

			factory = pb.PBClientFactory()
			rpcConnector = reactor.connectTCP(self.master, 8800, factory)
			d = factory.getRootObject()
			d.addCallback(masterConnected)
			d.addErrback(log.err)

	# TODO 
	def heartbeatsCheck(self):
		pass


class NodeRefusedError(pb.Error):
	pass


# vim: ts=4:sw=4:ai
