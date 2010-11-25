#!/usr/bin/python

# cxm - Clustered Xen Management API and tools
# Copyleft 2010 - Nicolas AGIUS <nagius@astek.fr>

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

import cxm.core, cxm.node, cxm.metrics
import unittest, os, platform
from mocker import *

class NodeTests(MockerTestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True
		#cxm.core.cfg['DEBUG']=True

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
		self.node=cxm.node.Node(platform.node())

		xenapi_mock.verify()
		xenapi_mock.restore()

	def test_node(self):
		self.assertNotEqual(self.node, None)

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
				 'vgrack': ['sda1'] }

		result=self.node.get_vgs_map()
		self.assertEqual(result, val)

	def test_is_local_node(self):
		self.assertEqual(self.node.is_local_node(), True)

	def test_is_vm_started_true(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(vmname)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.is_vm_started(vmname)
		self.assertEqual(result, True)
	
	def test_is_vm_started_false(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result("")
		self.mocker.replay()
		self.node.server=xs

		result=self.node.is_vm_started(vmname)
		self.assertEqual(result, False)

	def test_is_vm_autostart_enabled_true(self):
		self.assertEqual(self.node.is_vm_autostart_enabled("test2.home.net"), True)
		
	def test_is_vm_autostart_enabled_false(self):
		self.assertEqual(self.node.is_vm_autostart_enabled("nonexist"), False)
		
	def test_get_hostname(self):
		self.assertEqual(self.node.get_hostname(), platform.node())

	def test_get_vm_started(self):
		vm_records= ['00000000-0000-0000-0000-000000000000',
			'faaa6580-7336-ab25-866c-db5f02b92047',
			'39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8']

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all()
		self.mocker.result(vm_records)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.get_vm_started()
		self.assertEqual(result, 2)
		
	def test_get_vgs(self):
		val=['LVM_XEN', 'vgrack']
		lvs = ['/dev/vgrack/root-test1.home.net', '/dev/LVM_XEN/usr-test1.home.net', '/dev/vgrack/WOO-test1.home.net']

		vgs=self.node.get_vgs(lvs)
		self.assertEqual(vgs, val)

	def test_refresh_lvm(self):
		vgs=['LVM_XEN', 'vgrack']
		self.node.refresh_lvm(vgs) # No return value 

	def test_refresh_lvm_bad_input(self):
		self.assertRaises(cxm.node.ClusterNodeError,self.node.refresh_lvm, []) 

	def test_deactivate_lv(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result("")
		self.mocker.replay()
		self.node.server=xs

		self.node.deactivate_lv(vmname)

	def test_deactivate_lv_vm_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result("not-empty")
		self.mocker.replay()
		self.node.server=xs

		self.assertRaises(cxm.node.ClusterNodeError,self.node.deactivate_lv,vmname) 

	def test_deactivate_lv_bad_input(self):
		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(ANY)
		self.mocker.result("")
		self.mocker.replay()
		self.node.server=xs

		self.assertRaises(IOError,self.node.deactivate_lv,"nonexist") 

	def test_deacticvate_all_lv(self):
		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(ANY)
		self.mocker.count(2)
		self.mocker.result("")
		self.mocker.replay()
		self.node.server=xs

		self.node.deactivate_all_lv()
		
	def test_activate_lv(self):
		self.node.activate_lv("test1.home.net")

	def test_start_vm(self):
		vmname="test1.home.net"

		xm = self.mocker.mock()
		xm.server = ANY
		bidon = xm.SERVER_XEN_API
		xm.serverType=None
		xm.xm_importcommand('create', [cxm.core.cfg['VMCONF_DIR'] + vmname, '--skipdtd'])
		self.mocker.replay()

		cxm.node.main=xm
		self.node.start_vm(vmname)
	
	def test_migrate_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.migrate('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8', platform.node(), True, {'node': -1, 'ssl': None, 'port': 0})
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
		
		self.assertRaises(cxm.node.ClusterNodeError,self.node.migrate,vmname, self.node) 
		
	def test_shutdown__running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.clean_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.count(2)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.node.shutdown(vmname)		

	def test_shutdown__hard_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result(['39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8'])
		xs.xenapi.VM.hard_shutdown('39cb706a-eae1-b5cd-2ed0-fbbd7cbb8ee8')
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.count(2)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.node.shutdown(vmname, False)		

	def test_shutdown__not_running(self):
		vmname="test1.home.net"

		xs = self.mocker.mock()
		xs.xenapi.VM.get_by_name_label(vmname)
		self.mocker.result([])
		self.mocker.replay()
		self.node.server=xs
		
		self.assertRaises(cxm.node.ClusterNodeError,self.node.shutdown,vmname) 

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
		
		self.assertRaises(cxm.node.ClusterNodeError,self.node.get_vm,vmname) 
		
	def test_get_vms(self):	
		vm_records = {
            '6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
                'domid': '73',
				'metrics': '237f589-e62b-5573-915b-51117c9eb52e',
                'name_label': 'test1.home.net'},
             '7efcbac8-4714-88ee-007c-0246a3cb52b8': {
                'name_label': 'Domain-0',
				'metrics': '0208f543-e60b-5622-839b-51080c9eb63e',
                'domid': '72'}
            }

		metrics_records = { '237f589-e62b-5573-915b-51117c9eb52e': {}, '0208f543-e60b-5622-839b-51080c9eb63e': {} }

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VM_metrics.get_all_records()
		self.mocker.result(metrics_records)
		self.mocker.replay()
		self.node.server=xs

		self.assertEqual(isinstance(self.node.get_vms()[0], cxm.vm.VM),True)

	def test_check_lvs_ok(self):
		vm_records = {
            '6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
                'domid': '73',
				'metrics': '237f589-e62b-5573-915b-51117c9eb52e',
                'name_label': 'test1.home.net'}
            }

		metrics_records = { '237f589-e62b-5573-915b-51117c9eb52e': {}}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VM_metrics.get_all_records()
		self.mocker.result(metrics_records)
		self.mocker.replay()
		self.node.server=xs
		
		result=self.node.check_lvs()
		self.assertEqual(result,False)

	def test_check_autostart(self):
		vm_records = {
            '6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
                'domid': '73',
				'metrics': '237f589-e62b-5573-915b-51117c9eb52e',
                'name_label': 'test1.home.net'}
            }

		metrics_records = { '237f589-e62b-5573-915b-51117c9eb52e': {}}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VM_metrics.get_all_records()
		self.mocker.result(metrics_records)
		self.mocker.replay()
		self.node.server=xs

		result=self.node.check_autostart()	
		self.assertEqual(result,False)

	def test_run_ok(self):
		result=self.node.run("run success")
		self.assertEqual(result.read(),"OK\n")

	def test_run_error(self):
		self.assertRaises(cxm.node.ClusterNodeError,self.node.run,"run failure")


if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
