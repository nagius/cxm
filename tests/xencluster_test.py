#!/usr/bin/env python
# -*- coding:Utf-8 -*-

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

import cxm.core, cxm.xencluster, cxm.node
import unittest, os, socket
from mocker import *

class XenClusterTests(MockerTestCase):

	def setUp(self):

		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True
		cxm.core.cfg['POST_MIGRATION_HOOK']=None

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

	def test_disconnect(self):
		n_mock = Mocker()
		n = n_mock.mock()
		n.disconnect()
		n_mock.replay()

		self.cluster.nodes={socket.gethostname(): n}
		self.cluster.disconnect()

	def test_xencluster(self):
		self.assertNotEqual(self.cluster, None)

	def test_get_nodes(self):
		self.assertEqual(len(self.cluster.get_nodes()),1)

	def test_get_node__ok(self):
		self.assertNotEqual(self.cluster.get_node(socket.gethostname()),None)

	def test_get_node__ko(self):
		self.assertRaises(cxm.xencluster.NotInClusterError,self.cluster.get_node,"non-exist")

	def test_get_local_node__ok(self):
		node = self.mocker.mock()
		node.get_hostname()
		self.mocker.result(socket.gethostname())
		self.mocker.replay()
		self.cluster.nodes={socket.gethostname(): node}

		self.assertEqual(self.cluster.get_local_node().get_hostname(),socket.gethostname())

	def test_get_local_node__ko(self):
		self.cluster.nodes={}

		self.assertRaises(cxm.xencluster.NotInClusterError, self.cluster.get_local_node)

	def test_is_in_cluster(self):
		self.assertEqual(self.cluster.is_in_cluster(socket.gethostname()), True)
		
	def test_search_vm_started(self):
		vmname="test1.home.net"

		node = self.mocker.mock()
		node.is_vm_started(vmname)
		self.mocker.result(True)
		self.mocker.replay()
		self.cluster.nodes={socket.gethostname(): node}

		result=self.cluster.search_vm_started(vmname)
		self.assertEqual(len(result), 1)

	def test_search_vm_autostart(self):
		vmname="test1.home.net"

		node = self.mocker.mock()
		node.is_vm_autostart_enabled(vmname)
		self.mocker.result(True)
		self.mocker.replay()
		self.cluster.nodes={socket.gethostname(): node}

		result=self.cluster.search_vm_autostart(vmname)
		self.assertEqual(len(result), 1)

	def test_activate_vm(self):
		vmname="test1.home.net"

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(False)
		n1.deactivate_lv(vmname)
		n1.activate_lv(vmname)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.is_vm_started(vmname)
		n2_mocker.result(False)
		n2.deactivate_lv(vmname)
		n2_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.cluster.activate_vm(n1,vmname)
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_activate_vm__runing(self):
		vmname="test1.home.net"

		node = self.mocker.mock()
		node.is_vm_started(vmname)
		self.mocker.result(True)
		node.get_hostname()
		self.mocker.result(socket.gethostname())
		self.mocker.replay()
		self.cluster.nodes={socket.gethostname(): node}
	
		self.assertRaises(cxm.node.RunningVmError,self.cluster.activate_vm,node,vmname)

	def test_start_vm(self):
		vmname="test1.home.net"
		
		node = self.mocker.mock()
		node.metrics.get_free_ram()
		self.mocker.result(1024)
		node.is_vm_started(vmname)
		self.mocker.result(False)
		node.deactivate_lv(vmname)
		node.activate_lv(vmname)
		node.start(vmname)
		self.mocker.replay()

		self.cluster.nodes={socket.gethostname(): node}
		
		self.cluster.start_vm(node, vmname, False)

	def test_start_vm__switch_node(self):
		vmname="test1.home.net"
		
		n1_mocker = Mocker()
		node1 = n1_mocker.mock()
		node1.metrics.get_free_ram()
		n1_mocker.result(64)
		n1_mocker.count(1,None)
		node1.is_vm_started(vmname)
		n1_mocker.result(False)
		node1.deactivate_lv(vmname)
		node1.disable_vm_autostart(vmname)
		n1_mocker.replay()

		n2_mocker = Mocker()
		node2 = n2_mocker.mock()
		node2.metrics.get_free_ram()
		n2_mocker.result(1024)
		n2_mocker.count(1,None)
		node2.is_vm_started(vmname)
		n2_mocker.result(False)
		node2.deactivate_lv(vmname)
		node2.activate_lv(vmname)
		node2.start(vmname)
		node2.enable_vm_autostart(vmname)
		node2.get_hostname()
		n2_mocker.result('host2')
		n2_mocker.replay()

		self.cluster.nodes={'host2': node2, 'host1': node1}
		
		self.cluster.start_vm(node1, vmname, False)

		n1_mocker.verify()
		n2_mocker.verify()

	def test_start_vm__ram_error(self):
		vmname="test1.home.net"
		
		node = self.mocker.mock()
		node.metrics.get_free_ram()
		self.mocker.result(64)
		self.mocker.count(1,None)
		node.get_hostname()
		self.mocker.result(socket.gethostname())
		self.mocker.replay()

		self.cluster.nodes={socket.gethostname(): node}
		
		self.assertRaises(cxm.node.NotEnoughRamError,self.cluster.start_vm,node, vmname, False)

	def test_start_vm__error(self):
		vmname="test1.home.net"
		
		node = self.mocker.mock()
		node.metrics.get_free_ram()
		self.mocker.result(1024)
		node.is_vm_started(vmname)
		self.mocker.result(False)
		node.deactivate_lv(vmname)
		node.activate_lv(vmname)
		node.start(vmname)
		self.mocker.throw(Exception)
		node.deactivate_lv(vmname)
		self.mocker.replay()

		self.cluster.nodes={socket.gethostname(): node}
		
		self.assertRaises(Exception,self.cluster.start_vm,node, vmname, False)

	def test_migrate(self):
		vmname="test1.home.net"

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.is_vm_started(vmname)
		n2_mocker.result(False)
		n2.metrics.get_free_ram()
		n2_mocker.result(1024)
		n2.activate_lv(vmname)
		n2.enable_vm_autostart(vmname)
		n2_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(True)
		n1.get_vm(vmname).get_ram()
		n1_mocker.result(512)
		n1.migrate(vmname,n2)
		n1.deactivate_lv(vmname)
		n1.disable_vm_autostart(vmname)
		n1_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.cluster.migrate(vmname, 'host1', 'host2')
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_migrate__hook(self):
		vmname="test1.home.net"
		cxm.core.cfg['POST_MIGRATION_HOOK']="hook"

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.is_vm_started(vmname)
		n2_mocker.result(False)
		n2.metrics.get_free_ram()
		n2_mocker.result(1024)
		n2.activate_lv(vmname)
		n2.enable_vm_autostart(vmname)
		n2.get_hostname()
		n2_mocker.result('host2')
		n2_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(True)
		n1.get_vm(vmname).get_ram()
		n1_mocker.result(512)
		n1.migrate(vmname,n2)
		n1.deactivate_lv(vmname)
		n1.disable_vm_autostart(vmname)
		n1.get_hostname()
		n1_mocker.result('host1')
		n1.run('(hook test1.home.net host1 host2 2>&- >&- <&- &)&')
		n1_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.cluster.migrate(vmname, 'host1', 'host2')
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_migrate__src_error(self):
		vmname="test1.home.net"

		self.cluster.nodes={'host1': None, 'host2': None}

		self.assertRaises(cxm.xencluster.NotInClusterError,self.cluster.migrate,vmname, 'non-exist', 'host2')
		
	def test_migrate__dst_error(self):
		vmname="test1.home.net"

		self.cluster.nodes={'host1': None, 'host2': None}

		self.assertRaises(cxm.xencluster.NotInClusterError,self.cluster.migrate,vmname, 'host1', 'non-exist')

		
	def test_migrate__vm_not_running(self):
		vmname="test1.home.net"

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(False)
		n1.get_hostname()
		n1_mocker.result('host1')
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.assertRaises(cxm.node.NotRunningVmError,self.cluster.migrate,vmname, 'host1', 'host2')
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_migrate__vm_running(self):
		vmname="test1.home.net"

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(True)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.is_vm_started(vmname)
		n2_mocker.result(True)
		n2.get_hostname()
		n2_mocker.result('host2')
		n2_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.assertRaises(cxm.node.RunningVmError,self.cluster.migrate,vmname, 'host1', 'host2')
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_migrate__ram_error(self):
		vmname="test1.home.net"

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.is_vm_started(vmname)
		n1_mocker.result(True)
		n1.get_vm(vmname).get_ram()
		n1_mocker.result(512)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.is_vm_started(vmname)
		n2_mocker.result(False)
		n2.metrics.get_free_ram()
		n2_mocker.result(64)
		n2.get_hostname()
		n2_mocker.result('host2')
		n2_mocker.replay()

		self.cluster.nodes={'host1': n1, 'host2': n2}

		self.assertRaises(cxm.node.NotEnoughRamError,self.cluster.migrate,vmname, 'host1', 'host2')
		
		n1_mocker.verify()
		n2_mocker.verify()

	def test_check(self):

		vm1_mocker = Mocker()
		vm1 = vm1_mocker.mock()
		vm1.name
		vm1_mocker.result('vm1')
		vm1_mocker.count(1,None)
		vm1_mocker.replay()

		vm2_mocker = Mocker()
		vm2 = vm2_mocker.mock()
		vm2.name
		vm2_mocker.result('vm2')
		vm2_mocker.count(1,None)
		vm2_mocker.replay()

		vm3_mocker = Mocker()
		vm3 = vm3_mocker.mock()
		vm3.name
		vm3_mocker.result('vm3')
		vm3_mocker.count(1,None)
		vm3_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(1,None)
		n1.get_vms()
		n1_mocker.result([vm1, vm2])
		n1.check_missing_lvs()
		n1_mocker.result(True)
		n1.check_activated_lvs()
		n1_mocker.result(True)
		n1.check_autostart()
		n1_mocker.result(True)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2_mocker.count(1,None)
		n2.get_vms()
		n2_mocker.result([vm2, vm3])
		n2.check_activated_lvs()
		n2_mocker.result(True)
		n2.check_autostart()
		n2_mocker.result(True)
		n2_mocker.replay()

		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n1)
		check_bridges =  self.mocker.replace(self.cluster.check_bridges)
		check_bridges()
		self.mocker.result(True)
		check_cfg =  self.mocker.replace(self.cluster.check_cfg)
		check_cfg()
		self.mocker.result(True)
		check_cpu =  self.mocker.replace(self.cluster.check_cpu_flags)
		check_cpu()
		self.mocker.result(True)
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check(),False)

	def test_check_bridges__nok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_bridges()
		n1_mocker.result(['xenbr1','xenbr2','xenbr3'])
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_bridges()
		n2_mocker.result(['xenbr4','xenbr2'])
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_bridges(),False)
		
	def test_check_bridges__ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_bridges()
		n1_mocker.result(['xenbr2','xenbr1'])
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_bridges()
		n2_mocker.result(['xenbr1','xenbr2'])
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_bridges(),True)

	def test_check_cfg__nok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_possible_vm_names()
		n1_mocker.result(['vm1','vm2','vm3'])
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_possible_vm_names()
		n2_mocker.result(['vm4','vm2'])
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_cfg(),False)

	def test_check_cfg__ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_possible_vm_names()
		n1_mocker.result(['vm2','vm1'])
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_possible_vm_names()
		n2_mocker.result(['vm1','vm2'])
		n2_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_cfg(),True)

	def test_check_cpu_flags__ok(self):
		
		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_metrics().get_host_hw_caps()
		n1_mocker.result('078bf3ff:e3d3fbff:00000000:00000010:00000001:00000000:00000000:00000000')
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_metrics().get_host_hw_caps()
		n2_mocker.result('078bf3ff:e3d3fbff:00000000:00000010:00000001:00000000:00000000:00000000')
		n2.get_metrics().get_host_hw_caps()
		n2_mocker.result('078bf3ff:e3d3fbff:00000000:00000010:00000001:00000000:00000000:00000000')
		n2_mocker.replay()

		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_cpu_flags(), True)

	def test_check_cpu_flags__nok(self):
		
		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_hostname()
		n1_mocker.result("node1")
		n1.get_metrics().get_host_hw_caps()
		n1_mocker.result('078bf3ff:e3d3fbff:00000000:00000000:00000000:00000000:00000000:00000000')
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_hostname()
		n2_mocker.result('node2')
		n2.get_metrics().get_host_hw_caps()
		n2_mocker.result('078bf3ff:e3d3fbff:00000000:00000010:00000001:00000000:00000000:00000000')
		n2.get_metrics().get_host_hw_caps()
		n2_mocker.result('078bf3ff:e3d3fbff:00000000:00000010:00000001:00000000:00000000:00000000')
		n2_mocker.replay()

		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2}

		self.assertEqual(self.cluster.check_cpu_flags(), False)

	def test_emergency_eject__ok(self):
		migrate = self.mocker.replace(self.cluster.migrate)
		migrate('vm1', 'node1', 'node3')
		migrate('vm2', 'node1', 'node2')
		self.mocker.replay()

		vm1_mocker = Mocker()
		vm1 = vm1_mocker.mock()
		vm1.get_ram()
		vm1_mocker.result(512)
		vm1_mocker.count(1,None)
		vm1.name
		vm1_mocker.result('vm1')
		vm1_mocker.count(1,None)
		vm1_mocker.replay()

		vm2_mocker = Mocker()
		vm2 = vm2_mocker.mock()
		vm2.get_ram()
		vm2_mocker.result(128)
		vm2_mocker.count(1,None)
		vm2.name
		vm2_mocker.result('vm2')
		vm2_mocker.count(1,None)
		vm2_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock(cxm.node.Node)
		n1.get_vms()
		n1_mocker.result([vm1,vm2])
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(1,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(150)
		n2.metrics.get_free_ram()
		n2_mocker.result(150)
		n2.metrics.get_free_ram(False)
		n2_mocker.result(150)
		n2.metrics.get_free_ram()
		n2_mocker.result(150)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(1,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.metrics.get_free_ram(False)
		n3_mocker.result(8)
		n3.metrics.get_free_ram()
		n3_mocker.result(8)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(1,None)
		n3_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.cluster.emergency_eject(n1)

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()
		vm1_mocker.verify()
		vm2_mocker.verify()

	def test_emergency_eject_error(self):
		migrate = self.mocker.replace(self.cluster.migrate)
		migrate('vm2', 'node1', 'node3')
		migrate('vm3', 'node1', 'node2')
		self.mocker.throw(Exception('foobar'))
		self.mocker.replay()

		vm1_mocker = Mocker()
		vm1 = vm1_mocker.mock()
		vm1.get_ram()
		vm1_mocker.result(1024)
		vm1_mocker.count(1,None)
		vm1.name
		vm1_mocker.result('vm1')
		vm1_mocker.count(1,None)
		vm1_mocker.replay()

		vm2_mocker = Mocker()
		vm2 = vm2_mocker.mock()
		vm2.get_ram()
		vm2_mocker.result(510)
		vm2_mocker.count(1,None)
		vm2.name
		vm2_mocker.result('vm2')
		vm2_mocker.count(1,None)
		vm2_mocker.replay()

		vm3_mocker = Mocker()
		vm3 = vm3_mocker.mock()
		vm3.get_ram()
		vm3_mocker.result(128)
		vm3_mocker.count(1,None)
		vm3.name
		vm3_mocker.result('vm3')
		vm3_mocker.count(1,None)
		vm3_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock(cxm.node.Node)
		n1.get_vms()
		n1_mocker.result([vm1,vm2,vm3])
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(1,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(150)
		n2.metrics.get_free_ram()
		n2_mocker.result(150)
		n2.metrics.get_free_ram(False)
		n2_mocker.result(150)
		n2.metrics.get_free_ram()
		n2_mocker.result(150)
		n2.metrics.get_free_ram(False)
		n2_mocker.result(150)
		n2.metrics.get_free_ram()
		n2_mocker.result(150)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(1,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.metrics.get_free_ram(False)
		n3_mocker.result(8)
		n3.metrics.get_free_ram()
		n3_mocker.result(8)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(1,None)
		n3_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		e=self.assertRaises(cxm.xencluster.MultipleError, self.cluster.emergency_eject, n1)
		self.assertEquals(len(e.value), 2)
		self.assertTrue(isinstance(e.value['vm1'], cxm.node.NotEnoughRamError))
		self.assertTrue(isinstance(e.value['vm3'], Exception))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()
		vm1_mocker.verify()
		vm2_mocker.verify()
		vm3_mocker.verify()

	def test_loadbalance(self):
		cxm.core.cfg['LB_MIN_GAIN']=10

		migrate = self.mocker.replace(self.cluster.migrate)
		migrate('vm1', 'node1', 'node3')
		self.mocker.replay()

		vm1_mocker = Mocker()
		vm1 = vm1_mocker.mock()
		vm1.name
		vm1_mocker.result('vm1')
		vm1_mocker.count(1,None)
		vm1.get_ram()
		vm1_mocker.result(128)
		vm1_mocker.replay()

		vm2_mocker = Mocker()
		vm2 = vm2_mocker.mock()
		vm2.name
		vm2_mocker.result('vm2')
		vm2_mocker.count(1,None)
		vm2.get_ram()
		vm2_mocker.result(512)
		vm2_mocker.replay()

		vm3_mocker = Mocker()
		vm3 = vm3_mocker.mock()
		vm3.name
		vm3_mocker.result('vm3')
		vm3_mocker.count(1,None)
		vm3.get_ram()
		vm3_mocker.result(256)
		vm3_mocker.replay()

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.get_vms()
		n1_mocker.result([vm1,vm2])
		n1_mocker.count(1,None)
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(1,None)
		n1.metrics.get_available_ram()
		n1_mocker.result(512)
		n1.metrics.init_cache()
		n1.metrics.get_vms_cpu_usage()
		n1_mocker.result({'vm1': 12.0, 'vm2': 99.0})
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.get_vms()
		n2_mocker.result([vm3])
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(1,None)
		n2.metrics.get_available_ram()
		n2_mocker.result(512)
		n2.metrics.init_cache()
		n2.metrics.get_vms_cpu_usage()
		n2_mocker.result({'vm3': 30.0})
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.get_vms()
		n3_mocker.result([])
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(1,None)
		n3.metrics.get_available_ram()
		n3_mocker.result(512)
		n3.metrics.init_cache()
		n3.metrics.get_vms_cpu_usage()
		n3_mocker.result({})
		n3_mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.cluster.loadbalance()

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()
		vm1_mocker.verify()
		vm2_mocker.verify()
		vm3_mocker.verify()

	def test_start_vms__ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.start('test2.home.net')
		n1.enable_vm_autostart('test2.home.net')
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.start('test1.home.net')
		n3.enable_vm_autostart('test1.home.net')
		n3.metrics.get_free_ram(False)
		n3_mocker.result(8)
		n3.metrics.get_free_ram()
		n3_mocker.result(8)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		search_vm_started('test2.home.net')
		self.mocker.result([])
		search_vm_started('testcfg.home.net')
		self.mocker.result([n2])
		activate_vm = self.mocker.replace(self.cluster.activate_vm)
		activate_vm(n3, 'test1.home.net')
		activate_vm(n1, 'test2.home.net')
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.cluster.start_vms(['test1.home.net', 'test2.home.net', 'testcfg.home.net'])

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_start_vms__fail_noram(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(120)
		n3.metrics.get_free_ram()
		n3_mocker.result(120)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		e=self.assertRaises(cxm.xencluster.MultipleError, self.cluster.start_vms, ['test1.home.net'])
		self.assertTrue(isinstance(e.value['test1.home.net'], cxm.node.NotEnoughRamError))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_start_vms__fail_activate(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		activate_vm = self.mocker.replace(self.cluster.activate_vm)
		activate_vm(n3, 'test1.home.net')
		self.mocker.throw(cxm.node.ShellError('node3',"foobar",1))
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		e=self.assertRaises(cxm.xencluster.MultipleError, self.cluster.start_vms, ['test1.home.net'])
		self.assertTrue(isinstance(e.value['test1.home.net'], cxm.node.ShellError))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_start_vms__fail_multiple(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.start('test2.home.net')
		n1_mocker.throw(IOError("foobar"))
		n1.deactivate_lv('test2.home.net')
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.start('test1.home.net')
		n3_mocker.throw(SystemExit(1))
		n3.deactivate_lv('test1.home.net')
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		search_vm_started('test2.home.net')
		self.mocker.result([])
		activate_vm = self.mocker.replace(self.cluster.activate_vm)
		activate_vm(n3, 'test1.home.net')
		activate_vm(n1, 'test2.home.net')
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		e=self.assertRaises(cxm.xencluster.MultipleError, self.cluster.start_vms, ['test1.home.net', 'test2.home.net'])

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_start_vms__fail_deactivate(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.start('test1.home.net')
		n3_mocker.throw(Exception())
		n3.deactivate_lv('test1.home.net')
		n3_mocker.throw(cxm.node.SSHError('node3',"foobar",1))
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		activate_vm = self.mocker.replace(self.cluster.activate_vm)
		activate_vm(n3, 'test1.home.net')
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		e=self.assertRaises(cxm.xencluster.MultipleError, self.cluster.start_vms, ['test1.home.net'])
		self.assertTrue(isinstance(e.value['test1.home.net'], cxm.node.SSHError))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_start_vms__fail_autostartlink(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.metrics.get_free_ram(False)
		n1_mocker.result(150)
		n1.metrics.get_free_ram()
		n1_mocker.result(150)
		n1.get_hostname()
		n1_mocker.result("node1")
		n1_mocker.count(0,None)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.metrics.get_free_ram(False)
		n2_mocker.result(200)
		n2.metrics.get_free_ram()
		n2_mocker.result(200)
		n2.get_hostname()
		n2_mocker.result("node2")
		n2_mocker.count(0,None)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.metrics.get_free_ram(False)
		n3_mocker.result(520)
		n3.metrics.get_free_ram()
		n3_mocker.result(520)
		n3.start('test1.home.net')
		n3.enable_vm_autostart('test1.home.net')
		n3_mocker.throw(cxm.node.SSHError('node3',"foobar",1))
		n3.get_hostname()
		n3_mocker.result("node3")
		n3_mocker.count(0,None)
		n3_mocker.replay()

		search_vm_started = self.mocker.replace(self.cluster.search_vm_started)
		search_vm_started('test1.home.net')
		self.mocker.result([])
		activate_vm = self.mocker.replace(self.cluster.activate_vm)
		activate_vm(n3, 'test1.home.net')
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.cluster.start_vms(['test1.home.net'])

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.fence('node1')
		n2_mocker.throw(Exception('foobar'))
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertTrue(self.cluster.recover('node1', ['test1.home.net', 'test2.home.net'], False))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_noram(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(cxm.node.NotEnoughRamError('node2','foobar'))
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertRaises(cxm.node.NotEnoughRamError, self.cluster.recover, 'node1', ['test1.home.net', 'test2.home.net'], False)

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_fail_partial(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(Exception('foobar'))
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertFalse(self.cluster.recover('node1', ['test1.home.net', 'test2.home.net'], True))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_fail_ping_ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.ping(['test1.home.net', 'test2.home.net'])
		n1_mocker.result(False)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.ping(['test1.home.net', 'test2.home.net'])
		n2_mocker.result(True)
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.ping(['test1.home.net', 'test2.home.net'])
		n3_mocker.result(False)
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(Exception('foobar'))
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertFalse(self.cluster.recover('node1', ['test1.home.net', 'test2.home.net'], False))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_fail_fence_fail(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.ping(['test1.home.net', 'test2.home.net'])
		n1_mocker.result(False)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.ping(['test1.home.net', 'test2.home.net'])
		n2_mocker.result(False)
		n2.fence('node1')
		n2_mocker.throw(cxm.node.FenceNodeError('node3',"foobar"))
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.ping(['test1.home.net', 'test2.home.net'])
		n3_mocker.result(False)
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(Exception('foobar'))
		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertRaises(cxm.node.FenceNodeError, self.cluster.recover, 'node1', ['test1.home.net', 'test2.home.net'], False)

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_fail_fence_ok_start_ok(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1.ping(['test1.home.net', 'test2.home.net'])
		n1_mocker.result(False)
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.ping(['test1.home.net', 'test2.home.net'])
		n2_mocker.result(False)
		n2.fence('node1')
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3.ping(['test1.home.net', 'test2.home.net'])
		n3_mocker.result(False)
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(Exception('foobar'))
		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		start_vms = self.mocker.replace(self.cluster.start_vms)
		start_vms(['test1.home.net', 'test2.home.net'])
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertTrue(self.cluster.recover('node1', ['test1.home.net', 'test2.home.net'], False))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()

	def test_recover__eject_fail_fence_ok_novm(self):

		n1_mocker = Mocker()
		n1 = n1_mocker.mock()
		n1_mocker.replay()

		n2_mocker = Mocker()
		n2 = n2_mocker.mock()
		n2.fence('node1')
		n2_mocker.replay()

		n3_mocker = Mocker()
		n3 = n3_mocker.mock()
		n3_mocker.replay()

		emergency_eject = self.mocker.replace(self.cluster.emergency_eject)
		emergency_eject(n1)
		self.mocker.throw(Exception('foobar'))
		get_local_node = self.mocker.replace(self.cluster.get_local_node)
		get_local_node()
		self.mocker.result(n2)
		start_vms = self.mocker.replace(self.cluster.start_vms)
		start_vms([])
		self.mocker.replay()

		self.cluster.nodes={'node1': n1, 'node2': n2, 'node3': n3}

		self.assertTrue(self.cluster.recover('node1', [], False))

		n1_mocker.verify()
		n2_mocker.verify()
		n3_mocker.verify()
if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
