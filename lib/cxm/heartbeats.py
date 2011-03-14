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
import logs as log
from twisted.internet import defer
from messages import *
from netheartbeat import *


class SlaveHearbeatService(Service):

	def __init__(self, master):
		self._master=master

	def forgeSlaveHeartbeat(self):
		return MessageSlaveHB().forge(self._master.getLocalNode())

	def startService(self):
		Service.startService(self)

		log.info("Starting slave heartbeat...")
		self._hb = NetHeartbeat(self.forgeSlaveHeartbeat, self._master.getActiveHostname())
		self._hb.start()
	
	def stopService(self):
		if self.running:
			Service.stopService(self)
			log.info("Stopping slave heartbeat service...")
			return self._hb.stop()
		else:
			return defer.succeed(None)

	def forcePulse(self):
		self._hb.forcePulse()


class MasterHeartbeatService(Service):

	def __init__(self, getStatus):
		self.c_getStatus=getStatus

	def forgeMasterHeartbeat(self):
		return MessageMasterHB().forge(self.c_getStatus())
	
	def startService(self):
		Service.startService(self)

		log.info("Starting master heartbeat...")
		self._hb = NetHeartbeat(self.forgeMasterHeartbeat)
		self._hb.start()

	def stopService(self):
		if self.running:
			Service.stopService(self)
			log.info("Stopping master heartbeat service...")
			return self._hb.stop()
		else:
			return defer.succeed(None)

	def forcePulse(self):
		self._hb.forcePulse()

# vim: ts=4:sw=4:ai
