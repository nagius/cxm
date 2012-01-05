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

# Use Twisted's trial to run this tests

from cxm.xencluster import XenCluster
import cxm, socket
from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.internet import error, reactor, defer
from mocker import *

# Argh, multiple inheritance in diamond is really bad ! But there is no other way to mock twisted...
class XenClusterTrialTests(unittest.TestCase, MockerTestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True

		# Dummy mocker
		dummy_mock = Mocker()
		dummy = dummy_mock.mock()
		dummy_mock.replay()

		# Mock node class
		node_mock = Mocker()
		node = node_mock.mock()
		node.Node(socket.gethostname())
		node_mock.result(dummy)
		node_mock.replay()

		cxm.xencluster.node=node

		# Run test
		name=socket.gethostname()
		self.cluster=cxm.xencluster.XenCluster({name: node.Node(name)})

		node_mock.verify()
		node_mock.restore()


	def test_getDeferInstance__listok(self):
		n=self.mocker.replace("cxm.node.Node.__init__")
		n("node1")
		n("node2")
		self.mocker.replay()

		d=XenCluster.getDeferInstance(["node1","node2"])
		d.addCallback(self.assertIsInstance, XenCluster)
		return d

	def test_getDeferInstance__listfail(self):
		n=self.mocker.replace("cxm.node.Node.__init__")
		n("node1")
		n("node2")
		self.mocker.throw(Exception())
		self.mocker.replay()

		d=XenCluster.getDeferInstance(["node1","node2"])
		return self.assertFailure(d, cxm.xencluster.InstantiationError)

	def test_getDeferInstance__agentok(self):
		a=self.mocker.replace("cxm.agent.Agent.__init__")
		a()
		getNodesList=self.mocker.replace("cxm.agent.Agent.getNodesList")
		getNodesList()
		self.mocker.result(defer.succeed(["node1","node2"]))
		n=self.mocker.replace("cxm.node.Node.__init__")
		n("node1")
		n("node2")
		self.mocker.replay()

		d=XenCluster.getDeferInstance()
		d.addCallback(self.assertIsInstance, XenCluster)
		return d

	def test_getDeferInstance__agentfail(self):
		a=self.mocker.replace("cxm.agent.Agent.__init__")
		a()
		getNodesList=self.mocker.replace("cxm.agent.Agent.getNodesList")
		getNodesList()
		self.mocker.result(defer.fail(Failure("some error",Exception)))
		self.mocker.replay()

		d=XenCluster.getDeferInstance()
		return self.assertFailure(d, Exception)

	def test_get_load__many(self):
		get_ram_details=self.mocker.replace("cxm.xencluster.XenCluster.get_ram_details")
		get_ram_details()
		self.mocker.result(defer.succeed({'total': [3927,4012], 'used': [2660,369], 'free': [1267,3643]}))
		self.mocker.replay()

		d=self.cluster.get_load()
		d.addCallback(self.assertEquals, 77)
		return d

	def test_get_load__one(self):
		get_ram_details=self.mocker.replace("cxm.xencluster.XenCluster.get_ram_details")
		get_ram_details()
		self.mocker.result(defer.succeed({'total': [3927], 'used': [2660], 'free': [1267]}))
		self.mocker.replay()

		d=self.cluster.get_load()
		d.addCallback(self.assertEquals, 100)
		return d

	def test_get_ram_details__ok(self):
		def check(result):
			self.assertEquals(type(result), dict)

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_metrics().get_ram_infos()
		n1_mocker.result({'total': 3927, 'used': 3069, 'free': 858})
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_metrics().get_ram_infos()
		n2_mocker.result({'total': 4012, 'used': 369, 'free': 3643})
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		d=self.cluster.get_ram_details()
		d.addCallback(check)
		return d
		
	def test_get_ram_details__fail(self):
		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_metrics().get_ram_infos()
		n1_mocker.result({'total': 3927, 'used': 3069, 'free': 858})
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_metrics().get_ram_infos()
		n2_mocker.throw(Exception())
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		d=self.cluster.get_ram_details()
		return self.assertFailure(d, Exception)
		
	def test_get_vm_started__ok(self):
		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_vm_started()
		n1_mocker.result(28)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_vm_started()
		n2_mocker.result(12)
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		d=self.cluster.get_vm_started()
		d.addCallback(self.assertEquals, 40)
		return d

	def test_get_vm_started__fail(self):
		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_vm_started()
		n1_mocker.result(28)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_vm_started()
		n2_mocker.throw(Exception())
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		d=self.cluster.get_vm_started()
		return self.assertFailure(d, Exception)

# vim: ts=4:sw=4:ai
