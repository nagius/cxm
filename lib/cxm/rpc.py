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
from twisted.internet import reactor, error, defer
import logs as log
from twisted.spread import pb
import os


UNIX_PORT="/var/run/cxmd.socket" # TODO a passer dans fichier

class RemoteRPC(pb.Root):

	def __init__(self, master):
		self._master=master

	def remote_register(self, name):
		return self._master.registerNode(name)

	def remote_unregister(self, name):
		return self._master.unregisterNode(name)

class LocalRPC(pb.Root):

	def __init__(self, master):
		self._master=master

	def remote_quit(self):
		log.info("Received local quit query. Leaving cluster...")
		return self._master.stopService()

	def remote_getNodesList(self):
		"""Return the list of actives nodes'hostname."""
		return self._master.getNodesList()

	def remote_ping(self):
		return defer.succeed("PONG") 

	def remote_getState(self):
		status = dict()
		status['state']=self._master.state
		status['role']=self._master.role
		status['master']=self._master.master

		return status

	def remote_forceElection(self):
		return self._master.triggerElection()

	# Only for testing purpose
	def remote_forcePanic(self):
		return self._master.panic()

	def remote_recover(self):
		return self._master.recoverFromPanic()


class RPCService(Service):

	def __init__(self, master):
		self._master=master

	def cleanSocket(self, result):
		try:
			os.remove(UNIX_PORT)
		except OSError:
			pass

	def startService(self):
		Service.startService(self)

		log.info("Starting RPC service...")
		self.cleanSocket(None)
		self._localPort=reactor.listenUNIX(UNIX_PORT, pb.PBServerFactory(LocalRPC(self._master)))
		self._remotePort=reactor.listenTCP(8800, pb.PBServerFactory(RemoteRPC(self._master)))

	def stopService(self):
		if self.running:
			Service.stopService(self)
			log.info("Stopping RPC service...")

			d1=defer.maybeDeferred(self._remotePort.stopListening)
			d2=defer.maybeDeferred(self._localPort.stopListening)
			d2.addBoth(self.cleanSocket)
			return defer.DeferredList([d1, d2])
		else:
			return defer.succeed(None)

class NodeRefusedError(pb.Error):
    pass

class RPCRefusedError(pb.Error):
    pass


# vim: ts=4:sw=4:ai
