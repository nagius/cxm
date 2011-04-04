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

from twisted.spread import pb
from twisted.internet import reactor

UNIX_PORT="/var/run/cxmd.socket" # TODO a passer dans fichier

class Agent(object):

	def __init__(self):
		self._factory = pb.PBClientFactory()
		self._rpcConnector = reactor.connectUNIX(UNIX_PORT, self._factory)

	def _call(self, action):
		def remoteCall(obj, action):
			d = obj.callRemote(action)
			return d

		d = self._factory.getRootObject()
		d.addCallback(remoteCall, action)
		return d
	

	# External API for command line RPC
	#############################################################

	def quit(self):
		return self._call("quit")

	def getNodesList(self):
		return self._call("getNodesList")
		
	def ping(self):
		return self._call("ping")
		
	def getState(self):
		return self._call("getState")

	def forceElection(self):
		return self._call("forceElection")

	def forcePanic(self):
		return self._call("forcePanic")

	def recover(self):
		return self._call("recover")

	def kill(self, name):
		def connectMaster(result):
			def masterConnected(obj):
				d = obj.callRemote("unregister",name)
				d.addCallback(lambda _: rpcConnector.disconnect())
				return d

			rpcFactory = pb.PBClientFactory()
			rpcConnector = reactor.connectTCP(result['master'], 8800, rpcFactory)
			d = rpcFactory.getRootObject()
			d.addCallback(masterConnected)
			return d

		d=self.getState()
		d.addCallback(connectMaster)

		return d

# vim: ts=4:sw=4:ai
