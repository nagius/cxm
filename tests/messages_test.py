#!/usr/bin/python

# cxm - Clustered Xen Management API and tools
# Copyleft 2011 - Nicolas AGIUS <nagius@astek.fr>

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

from cxm.messages import *
from cxm.master import *
import cxm
import unittest
from mocker import *

class MessagesTests(MockerTestCase):

	def setUp(self):
		cxm.core.cfg['CLUSTER_NAME']="mycluster"

	def test_MessageSlaveHB_forge(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'ts': 1325845000, 
				'vms': ['vm1', 'vm2']
			}, 
			'type': 'slavehb'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")

		time = self.mocker.replace("time.time")
		time()
		self.mocker.count(1,None)
		self.mocker.result(1325845000)

		node = self.mocker.mock()
		node.get_vms_names(True)
		self.mocker.result(['vm1','vm2'])
		self.mocker.replay()

		m=MessageSlaveHB().forge(node)
		self.assertEquals(m.value(), msg)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'slavehb')

	def test_MessageMasterHB_forge(self):
		msg = {
			'type': 'masterhb',
			'data': {
				'status': dict(), 
				'cluster': 'mycluster', 
				'state': MasterService.ST_NORMAL 
			}, 
		}
		
		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		m=MessageMasterHB().forge(dict(), MasterService.ST_NORMAL)
		self.assertEquals(m.value(), msg)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'masterhb')

	def test_MessageVoteRequest_forge(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'election': 12345
			}, 
			'type': 'voterequest'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")

		rand = self.mocker.mock()
		rand()
		self.mocker.result(12345)
		self.mocker.replay()

		# Can't use mocker.replace with static function
		cxm.messages.MessageHelper.rand=rand

		m=MessageVoteRequest().forge()
		self.assertEquals(m.value(), msg)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'voterequest')

	def test_MessageVoteResponse_forge(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'ballot': 67890, 
				'election': 12345
			}, 
			'type': 'voteresponse'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")

		rand = self.mocker.mock()
		rand()
		self.mocker.result(67890)
		self.mocker.replay()

		# Can't use mocker.replace with static function
		cxm.messages.MessageHelper.rand=rand
		
		m=MessageVoteResponse().forge(12345)
		self.assertEquals(m.value(), msg)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'voteresponse')

	def test_forge__withnode(self):
		msg = {
			'type': 'masterhb',
			'data': {
				'status': dict(), 
				'cluster': 'mycluster', 
				'state': MasterService.ST_NORMAL 
			}, 
		}
		
		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().get_by_ip("1.1.1.1")
		self.mocker.result("node1")
		self.mocker.replay()

		m=MessageMasterHB("1.1.1.1").forge(dict(), MasterService.ST_NORMAL)
		self.assertEquals(m.value(), msg)
		self.assertEquals(m.node, "node1")
		self.assertEquals(m.type(), 'masterhb')

	def test_get__MessageSlaveHB(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'ts': 1325845000, 
				'vms': ['vm1', 'vm2']
			}, 
			'type': 'slavehb'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		m = MessageHelper.get(msg, None)
		self.assertIsInstance(m, MessageSlaveHB)
		self.assertEquals(m.ts, 1325845000)
		self.assertEquals(m.vms, ['vm1', 'vm2'])
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'slavehb')

	def test_get__MessageMasterHB(self):
		msg = {
			'data': {
				'status': dict(), 
				'cluster': 'mycluster', 
				'state': MasterService.ST_NORMAL
			}, 
			'type': 'masterhb'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		m = MessageHelper.get(msg, None)
		self.assertIsInstance(m, MessageMasterHB)
		self.assertEquals(m.status, dict())
		self.assertEquals(m.state, MasterService.ST_NORMAL)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'masterhb')

	def test_get__MessageVoteRequest(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'election': 12345
			}, 
			'type': 'voterequest'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()
		
		m = MessageHelper.get(msg, None)
		self.assertIsInstance(m, MessageVoteRequest)
		self.assertEquals(m.election, 12345)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'voterequest')

	def test_get__MessageVoteResponse(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'ballot': 67890, 
				'election': 12345
			}, 
			'type': 'voteresponse'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		m = MessageHelper.get(msg, None)
		self.assertIsInstance(m, MessageVoteResponse)
		self.assertEquals(m.election, 12345)
		self.assertEquals(m.ballot, 67890)
		self.assertEquals(m.node, "node-name")
		self.assertEquals(m.type(), 'voteresponse')

	def test_get__withnode(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
				'ballot': 67890, 
				'election': 12345
			}, 
			'type': 'voteresponse'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().get_by_ip("1.1.1.1")
		self.mocker.result("node1")
		self.mocker.replay()

		m = MessageHelper.get(msg, "1.1.1.1")
		self.assertIsInstance(m, MessageVoteResponse)
		self.assertEquals(m.election, 12345)
		self.assertEquals(m.ballot, 67890)
		self.assertEquals(m.node, "node1")
		self.assertEquals(m.type(), 'voteresponse')

	def test_get__bad_type(self):
		msg = {
			'data': dict(),
			'type': 'non-exist'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		self.mocker.replay()

		self.assertRaises(MessageError, MessageHelper.get, msg, None)

	def test_get__bad_cluster(self):
		msg = {
			'data': {
				'cluster': 'non-exist', 
				'ballot': 67890, 
				'election': 12345
			}, 
			'type': 'voteresponse'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		self.assertRaises(IDontCareException, MessageHelper.get, msg, None)

	def test_get__bad_message(self):
		msg = {
			'data': {
				'cluster': 'mycluster', 
			}, 
			'type': 'voteresponse'
		}

		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().name
		self.mocker.result("node-name")
		self.mocker.replay()

		self.assertRaises(MessageError, MessageHelper.get, msg, None)

	def test_MessageHelper_type__ok(self):
		msg = {'type': 'voteresponse'}
		self.assertEquals(MessageHelper.type(msg), "voteresponse")

	def test_MessageHelper_type__nok(self):
		msg = {'type': 'non-exist'}
		self.assertRaises(MessageError, MessageHelper.type, msg)

	def test_MessageHelper_rand(self):
		dns = self.mocker.replace("cxm.dnscache.DNSCache")
		dns.getInstance().ip
		self.mocker.result("1.1.1.1")
		self.mocker.replay()

		self.assertEquals(type(MessageHelper.rand()), int)


if __name__ == "__main__":
    unittest.main()

# vim: ts=4:sw=4:ai

