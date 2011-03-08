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
#import time
import logs as log
from twisted.spread import pb
import os

from master import MasterService

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
		log.info("Received local exit query. Exitting...")
		return self._master.stopService()

	def remote_getNodesList(self):
		return self._master.getNodesList()

	def remote_getStatus(self):
		status = dict()
		status['state']=self._master.state
		status['master']=self._master.master

		return status

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

		self.cleanSocket(None)
		self._localPort=reactor.listenUNIX(UNIX_PORT, pb.PBServerFactory(LocalRPC(self._master)))
		if self._master.state is MasterService.ST_ACTIVE:	# Listen for remote RPC only when master is active
			self._remotePort=reactor.listenTCP(8800, pb.PBServerFactory(RemoteRPC(self._master)))

	def stopService(self):
		if self.running:
			Service.stopService(self)
			log.info("Stopping RPC service...")

			if self._master.state is MasterService.ST_ACTIVE:
				d1=defer.maybeDeferred(self._remotePort.stopListening)
			else:
				d1=defer.succeed(None)

			d2=defer.maybeDeferred(self._localPort.stopListening)
			d2.addBoth(self.cleanSocket)
			return defer.DeferredList([d1, d2])
		else:
			return defer.succeed(None)



# vim: ts=4:sw=4:ai
