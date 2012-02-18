#!/usr/bin/python

# cxm - Clustered Xen Management API and tools
# Copyleft 2010-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>

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

# Use Twisted's trial to run this tests

from cxm.heartbeats import *
from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.internet import error, reactor, defer
from mocker import *

# Argh, multiple inheritance in diamond is really bad ! But there is no other way to mock twisted...
class SlaveHearbeatServiceTests(unittest.TestCase, MockerTestCase):

#    def setUp(self):


	def test_startService(self):
		master=self.mocker.mock()
		master.getActiveMaster()	
		self.mocker.result("master")
		master.disk.write_ts("node-name")
		master.disk.write_ts("node-name")

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		dns.getInstance().name
		self.mocker.result("node-name")
		dns.getInstance().name
		self.mocker.result("node-name")
		dns.getInstance().name
		self.mocker.result("node-name")

		netheartbeat_mock = self.mocker.mock()
		netheartbeat_mock.start()

		netheartbeat = self.mocker.replace("cxm.netheartbeat.NetHeartbeat")
		netheartbeat()
		self.mocker.result(netheartbeat_mock)


		self.mocker.replay()
		slavehb=SlaveHearbeatService(master)

		return slavehb.startService()

# vim: ts=4:sw=4:ai
