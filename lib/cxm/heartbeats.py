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
from twisted.internet import defer, task
from dnscache import DNSCache
import logs as log
from messages import *
from netheartbeat import *
from diskheartbeat import *


class SlaveHearbeatService(Service):

	def __init__(self, master):
		self._master=master

	def forgeSlaveHeartbeat(self):
		return MessageSlaveHB().forge(self._master.getLocalNode())

	def startService(self):
		def heartbeatFailed(reason):
			log.err("Disk heartbeat failure: %s." % (reason.getErrorMessage()))
			self.stopService()  # Stop slave heartbeat to tell master we have a problem

		Service.startService(self)

		log.info("Starting slave heartbeats...")
		self._hb = NetHeartbeat(self.forgeSlaveHeartbeat, self._master.getActiveMaster())
		self._hb.start()
		self._call = task.LoopingCall(self._master.disk.write_ts, DNSCache.getInstance().name)
		self._call.start(1).addErrback(heartbeatFailed)
	
	def stopService(self):
		if self.running:
			Service.stopService(self)
			log.info("Stopping slave heartbeats...")
			if self._call.running:
				self._call.stop()
			return self._hb.stop()
		else:
			return defer.succeed(None)

	def forcePulse(self):
		if self.running:
			self._hb.forcePulse()


class MasterHeartbeatService(Service):

	def __init__(self, master):
		self._master=master

	def forgeMasterHeartbeat(self):
		return MessageMasterHB().forge(self._master.getStatus(), self._master.getState())
	
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
		if self.running:
			self._hb.forcePulse()


# vim: ts=4:sw=4:ai
