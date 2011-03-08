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

	def __del__(self):
		self._factory.getRootObject().addCallback(lambda _: self._rpcConnector.disconnect())

	def _call(self, obj, action):
		d = obj.callRemote(action)
		return d
		
	def quit(self):
		d = self._factory.getRootObject()
		d.addCallback(self._call, "quit")
		return d

	def getNodesList(self):
		d = self._factory.getRootObject()
		d.addCallback(self._call, "getNodesList")
		return d

	def getStatus(self):
		d = self._factory.getRootObject()
		d.addCallback(self._call, "getStatus")
		return d

# vim: ts=4:sw=4:ai
