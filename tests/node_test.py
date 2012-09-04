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

import cxm.core, cxm.node, cxm.metrics, cxm.vm
import unittest, os, socket
from mocker import *

class NodeTests(MockerTestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['DISABLE_FENCING'] = False
		cxm.core.cfg['QUIET']=True
		cxm.core.cfg['API_DEBUG']=False
		cxm.core.cfg['SHUTDOWN_TIMEOUT']=1

		# Mock xen session object
		xs_mock = Mocker()
		xs = xs_mock.mock()
		xs.login_with_password("root", "")
		xs_mock.replay()

		# Mock XenAPI Server
		xenapi_mock = Mocker()
		xenapi=xenapi_mock.mock()
		xenapi.Session("httpu:///var/run/xend/xen-api.sock")
		xenapi_mock.result(xs)
		xenapi_mock.replay()

		# Mock ServerProxy
		proxy_mock = Mocker()
		proxy=proxy_mock.mock()
		proxy("httpu:///var/run/xend/xmlrpc.sock")
		proxy_mock.result(None)
		proxy_mock.replay()

		# Override XenAPI
		cxm.node.XenAPI=xenapi
		cxm.node.ServerProxy=proxy

		# Run test
		self.node=cxm.node.Node.getLocalInstance()

		xenapi_mock.verify()
		xenapi_mock.restore()

	def test_disconnect(self):
		xs = self.mocker.mock()
		xs.xenapi.session.logout()
		self.mocker.result(None)
		self.mocker.replay()
		self.node.server=xs

		self.assertEqual(self.node.disconnect(), None)

	def test_node(self):
		self.assertNotEqual(self.node, None)

	def test_getLocalInstance(self):
		self.assertTrue(isinstance(self.node, cxm.node.Node))

	def test_get_bridges(self):
		val = ['xenbr123', 'xenbr2004', 'xenbr12']

		result=self.node.get_bridges()
		self.assertEqual(result, val)

	def test_get_vlans(self):
		val = ['eth1.200', 'eth2.205']

		result=self.node.get_vlans()
		self.assertEqual(result, val)
		
	def test_get_vgs_map(self):
		val = { 'LVM_XEN': ['cciss/c0d0p7'], 
				 'MULTI': ['sdb', 'sdc'],
				 'DRBD': ['drbd0'],
				 'vgrack': ['sda1'] }

		result=self.node.get_vgs_map()
		self.assertEqual(result, val)

	def test_is_local_node(self):
		self.assertEqual(self.node.is_local_node(), True)

	def test_is_vm_started_true(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.get_power_state('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.result("Running")
		self.mocker.replay()
		self.node.server=xs

		result=self.node.is_vm_started(vmname)
		self.assertEqual(result, True)
	
	def test_is_vm_started_false(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		xs.xenapi.VM.get_power_state()
		self.mocker.count(0)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.is_vm_started(vmname)
		self.assertEqual(result, False)

	def test_is_vm_started__not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.get_power_state('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.result("Halted")
		self.mocker.replay()
		self.node.server=xs

		result=self.node.is_vm_started(vmname)
		self.assertEqual(result, False)

	def test_is_vm_autostart_enabled_true(self):
		self.assertEqual(self.node.is_vm_autostart_enabled("test2.home.net"), True)
		
	def test_is_vm_autostart_enabled_false(self):
		self.assertEqual(self.node.is_vm_autostart_enabled("nonexist"), False)
		
	def test_get_hostname(self):
		self.assertEqual(self.node.get_hostname(), socket.gethostname())

	def test_get_vm_started(self):
		vm_records = {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'name_label': 'test1.home.net',
				'power_state': 'Running'},
			'9875358c-a6d7-1864-d878-afc4831aef41': {
				'name_label': 'test2.home.net',
				'power_state': 'Running'},
			'ab22fd4c-d7d1-112e-d90d-3f8a81ae1e23': {
				'name_label': 'test3.home.net',
				'power_state': 'Halted'},
			'11ab12fd4c-d1d3-153e-d75d1fc4841ae1e7': {
				'name_label': 'migrating-test1.home.net',
				'power_state': 'Running'},
			'7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'Domain-0',
				'power_state': 'Running'}
		}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.get_vm_started()
		self.assertEqual(result, 2)
		
	def test_get_vgs(self):
		val=['LVM_XEN', 'vgrack']
		lvs = ['/dev/LVM_XEN/usr-test1.home.net', '/dev/vgrack/WOO-test1.home.net', '/dev/vgrack/root-test1.home.net']

		vgs=self.node.get_vgs(lvs)
		self.assertEqual(vgs, val)

	def test_refresh_lvm(self):
		vgs=['LVM_XEN', 'vgrack']
		cxm.core.cfg['NOREFRESH']=False
		self.node.refresh_lvm(vgs) # No return value 

	def test_refresh_lvm_bad_input(self):
		cxm.core.cfg['NOREFRESH']=False
		self.assertRaises(cxm.node.ShellError,self.node.refresh_lvm, []) 

	def test_deactivate_lv(self):
		vmname="test1.home.net"

		n = self.mocker.mock()
		n.is_vm_started(ANY)
		self.mocker.result(False)
		self.mocker.replay()
		self.node.is_vm_started=n.is_vm_started

		self.node.deactivate_lv(vmname)

	def test_deactivate_lv_vm_running(self):
		vmname="test1.home.net"

		is_vm_started = self.mocker.replace(self.node.is_vm_started)
		is_vm_started(vmname)
		self.mocker.result(True)
		self.mocker.replay()

		self.assertRaises(cxm.node.RunningVmError,self.node.deactivate_lv,vmname) 

	def test_deactivate_lv_bad_input(self):

		n = self.mocker.mock()
		is_vm_started = self.mocker.replace(self.node.is_vm_started)
		is_vm_started(ANY)
		self.mocker.result(False)
		self.mocker.replay()

		self.assertRaises(IOError,self.node.deactivate_lv,"nonexist") 

	def test_deactivate_all_lv(self):
		names=['test1.home.net', 'test2.home.net', 'testcfg.home.net']

		is_vm_started = self.mocker.replace(self.node.is_vm_started)
		deactivate_lv = self.mocker.replace(self.node.deactivate_lv)
		for name in names:
			is_vm_started(name)
			self.mocker.result(False)
			deactivate_lv(name)
		self.mocker.replay()

		self.node.deactivate_all_lv()
		
	def test_activate_lv(self):
		self.node.activate_lv("test1.home.net")

	def test_start_vm(self):
		vmname="test1.home.net"

		xm = self.mocker.mock()
		xm.server = ANY
		bidon = xm.SERVER_LEGACY_XMLRPC
		xm.serverType=None
		xm.xm_importcommand('create', [cxm.core.cfg['VMCONF_DIR'] + vmname])
		self.mocker.replay()

		cxm.node.main=xm
		self.node.start_vm(vmname)
	
	def test_reboot_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.clean_reboot('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.replay()
		self.node.server=xs
		
		self.node.reboot(vmname)		

	def test_reboot_not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.assertRaises(cxm.node.NotRunningVmError,self.node.reboot,vmname) 

	def test_migrate_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.migrate('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8', socket.gethostname(), True, {'node': -1, 'ssl': None, 'port': 0})
		self.mocker.replay()
		self.node.server=xs
		
		self.node.migrate(vmname,self.node)		

	def test_migrate_not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.assertRaises(cxm.node.NotRunningVmError,self.node.migrate,vmname, self.node) 
		
	def test_shutdown__running(self):
		vmname="test1.home.net"

		n_mocker = Mocker()
		is_vm_started = n_mocker.replace(self.node.is_vm_started)
		is_vm_started(vmname)
		n_mocker.result(False)
		n_mocker.count(2)
		deactivate_lv = n_mocker.replace(self.node.deactivate_lv)
		deactivate_lv(vmname)
		n_mocker.replay()

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.clean_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.replay()
		self.node.server=xs

		self.node.shutdown(vmname)		

		n_mocker.verify()

	def test_shutdown__hard_running(self):
		vmname="test1.home.net"

		n_mocker = Mocker()
		is_vm_started = n_mocker.replace(self.node.is_vm_started)
		is_vm_started(vmname)
		n_mocker.result(False)
		n_mocker.count(2)
		deactivate_lv = n_mocker.replace(self.node.deactivate_lv)
		deactivate_lv(vmname)
		n_mocker.replay()

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.hard_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.replay()
		self.node.server=xs
		
		self.node.shutdown(vmname, True)		

		n_mocker.verify()

	def test_shutdown__freezed(self):
		vmname="test1.home.net"

		n_mocker = Mocker()
		is_vm_started = n_mocker.replace(self.node.is_vm_started)
		is_vm_started(vmname)
		n_mocker.result(True)
		n_mocker.count(4)
		deactivate_lv = n_mocker.replace(self.node.deactivate_lv)
		deactivate_lv(vmname)
		n_mocker.replay()

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.clean_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		xs.xenapi.VM.hard_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.replay()
		self.node.server=xs

		self.node.shutdown(vmname)		

		n_mocker.verify()

	def test_shutdown__not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs

		self.assertRaises(cxm.node.NotRunningVmError,self.node.shutdown,vmname) 

	def test_get_vm_running(self):
		vmname="test1.home.net"
		vm_record= { 
			'domid': '4',
			'metrics': '0208f543-e60b-5622-839b-51080c9eb63e',
			'name_label': vmname }

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.get_record('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		self.mocker.result(vm_record)
		xs.xenapi.VM_metrics.get_record('0208f543-e60b-5622-839b-51080c9eb63e')
		self.mocker.result({})
		self.mocker.replay()
		self.node.server=xs
		
		result=self.node.get_vm(vmname)

	def test_get_vm_not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.assertRaises(cxm.node.NotRunningVmError,self.node.get_vm,vmname) 
		
	def test_get_vms(self):	
		vm_records = {
            '6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
                'domid': '73',
				'metrics': '237f589-e62b-5573-915b-51117c9eb52e',
				'power_state': 'Running',
                'name_label': 'test1.home.net'},
            'ab22fd4c-d7d1-112e-d90d-3f8a81ae1e23': {
                'domid': '74',
				'metrics': '330f626-e98b-5266-867b-50968c1eb62e',
				'power_state': 'Halted',
                'name_label': 'test2.home.net'},
            '11ab12fd4c-d1d3-153e-d75d1fc4841ae1e7': {
                'domid': '73',
				'metrics': '248f596-e71b-5494-876b-50973c20eb72e',
				'power_state': 'Running',
                'name_label': 'migrating-test1.home.net'},
             '7efcbac8-4714-88ee-007c-0246a3cb52b8': {
                'name_label': 'Domain-0',
				'power_state': 'Running',
				'metrics': '0208f543-e60b-5622-839b-51080c9eb63e',
                'domid': '72'}
            }

		metrics_records = { '237f589-e62b-5573-915b-51117c9eb52e': {}, 
							'0208f543-e60b-5622-839b-51080c9eb63e': {},
							'330f626-e98b-5266-867b-50968c1eb62e': {},
							'248f596-e71b-5494-876b-50973c20eb72e': {} 
				}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VM_metrics.get_all_records()
		self.mocker.result(metrics_records)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.get_vms()
		self.assertEqual(isinstance(result[0], cxm.vm.VM),True)
		self.assertEqual(len(result),1)

	def test_get_vms_names(self):	
		vm_records = {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'name_label': 'test1.home.net',
				'power_state': 'Running'},
			'ab22fd4c-d7d1-112e-d90d-3f8a81ae1e23': {
				'name_label': 'test3.home.net',
				'power_state': 'Halted'},
			'11ab12fd4c-d1d3-153e-d75d1fc4841ae1e7': {
				'name_label': 'migrating-test1.home.net',
				'power_state': 'Running'},
			'7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'Domain-0',
				'power_state': 'Running'}
		}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.get_vms_names()
		self.assertEqual(result,['test1.home.net'])

	def test_get_possible_vm_names__all(self):
		names=['test1.home.net', 'test2.home.net', 'testcfg.home.net']

		result=self.node.get_possible_vm_names()
		self.assertEqual(result, names)

	def test_get_possible_vm_names__one(self):
		names=['testcfg.home.net']

		result=self.node.get_possible_vm_names("*tcfg")
		self.assertEqual(result, names)

	def test_get_possible_vm_names__none(self):
		result=self.node.get_possible_vm_names("non-exist")
		self.assertEqual(result, list())

	def test_check_activated_lvs_ok(self):

		get_vms = self.mocker.replace(self.node.get_vms)
		get_vms()
		self.mocker.result([cxm.vm.VM("test1.home.net")])
		self.mocker.replay()
		
		result=self.node.check_activated_lvs()
		self.assertEqual(result,False)

	def test_check_missing_lvs__ok(self):

		get_possible_vm_names = self.mocker.replace(self.node.get_possible_vm_names)
		get_possible_vm_names()
		self.mocker.result(["test1.home.net"])
		self.mocker.replay()
		
		result=self.node.check_missing_lvs()
		self.assertEqual(result,True)

	def test_check_missing_lvs__nok(self):

		get_possible_vm_names = self.mocker.replace(self.node.get_possible_vm_names)
		get_possible_vm_names()
		self.mocker.result(["test1.home.net","test2.home.net"])
		self.mocker.replay()
		
		result=self.node.check_missing_lvs()
		self.assertEqual(result,False)

	def test_check_autostart(self):

		get_vms = self.mocker.replace(self.node.get_vms)
		get_vms()
		self.mocker.result([cxm.vm.VM("test1.home.net")])
		self.mocker.replay()

		result=self.node.check_autostart()	
		self.assertEqual(result,False)

	def test_run_ok(self):
		result=self.node.run("run success")
		self.assertEqual(result.read(),"OK\n")

	def test_run_error(self):
		self.assertRaises(cxm.node.ShellError,self.node.run,"run failure")

	def test_ping__ok(self):
		self.assertTrue(self.node.ping(["test1.home.net", "test2.home.net", "test3.home.net"]))

	def test_ping__norunning(self):
		self.assertFalse(self.node.ping("test4.home.net"))

	def test_ping__baddns(self):
		self.assertFalse(self.node.ping("non-exist"))

	def test_ping__empty(self):
		self.assertFalse(self.node.ping([]))

	def test_fence_ok(self):
		self.assertEqual(self.node.fence("node1"),None)

	def test_fence_error(self):
		self.assertRaises(cxm.node.FenceNodeError,self.node.fence, "node2")

	def test_fence_disabled(self):
		cxm.core.cfg['DISABLE_FENCING'] = True

		self.assertRaises(cxm.node.FenceNodeError,self.node.fence, "dummy-input")


if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
