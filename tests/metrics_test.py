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


class MetricsTests(MockerTestCase):

	def setUp(self):

		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True
	#	cxm.core.cfg['DEBUG']=True

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

		# Mock Legacy XMLRPC
		xenlegacy_mock = Mocker()
		xenlegacy=xenlegacy_mock.mock()
		xenlegacy.xend.domains(True)
		xenlegacy_mock.result(
			[['domain',
			  ['name', 'test15.home.net'],
			  ['cpu_time', 159.379459621]],
			 ['domain',
			  ['name', 'test22.home.net'],
			  ['cpu_time', 146.65212068700001],
			 ]]
		)
		xenlegacy.xend.domains(True)
		xenlegacy_mock.result(
			[['domain',
			  ['name', 'test15.home.net'],
			  ['cpu_time', 159.379459621]],
			 ['domain',
			  ['name', 'test22.home.net'],
			  ['cpu_time', 146.65212068700001],
			 ]]
		)
		xenlegacy_mock.replay()

		# Mock ServerProxy
		proxy_mock = Mocker()
		proxy=proxy_mock.mock()
		proxy("httpu:///var/run/xend/xmlrpc.sock")
		proxy_mock.result(xenlegacy)
		proxy_mock.replay()


		# Override XenAPI
		cxm.node.XenAPI=xenapi
		cxm.node.ServerProxy=proxy


		# Run test
		self.node=cxm.node.Node(platform.node())
		self.metrics=cxm.metrics.Metrics(self.node)

		xenapi_mock.verify()
		xenapi_mock.restore()

	def test_get_host_net_io(self):
		val = {'bridges': {
					'xenbr12': {'Rx': '0', 'Tx': '468'}, 
					'xenbr2004': {'Rx': '0', 'Tx': '468'}, 
					'xenbr123': {'Rx': '4000460532', 'Tx': '2836763015'}
					}, 
				'vlans': {
					'eth2.205': {'Rx': '0', 'Tx': '0'}, 
					'eth1.200': {'Rx': '0', 'Tx': '0'}
					}
				}

		result=self.metrics.get_host_net_io()
		self.assertEqual(result, val)

	def test_get_host_pvs_io(self):
		val = { 'cciss/c0d0p7': {'Read': 3397277, 'Write': 11736}, 
				 'sdc': {'Read': 98544853, 'Write': 964975}, 
				 'sdb': {'Read': 58756867, 'Write': 947286},
				 'sda1': {'Read': 53322250, 'Write': 964286}}

		result=self.metrics.get_host_pvs_io()
		self.assertEqual(result, val)

	def test_get_host_vgs_io(self):
		val =  {'LVM_XEN': {'Read': 3397277, 'Write': 11736}, 
				 'MULTI': {'Read': 157301720, 'Write': 1912261}, 
				 'vgrack': {'Read': 53322250, 'Write': 964286}}

		result=self.metrics.get_host_vgs_io()
		self.assertEqual(result, val)
		
	def test_user_irq(self):
		val=28

		result=self.metrics.get_used_irq()
		self.assertEqual(result, val)
		
	def	test_get_host_nr_cpus(self):
		val=2	

		xs = self.mocker.mock()
		xs.getSession()
		xs.xenapi.session.get_this_host(ANY)
		xs.xenapi.host.get_record(ANY)
		self.mocker.result({'cpu_configuration': {'nr_cpus': 2}})
		self.mocker.replay()
		self.metrics.server=xs

		result=self.metrics.get_host_nr_cpus()
		self.assertEqual(result, val)

	def test_get_vms_disk_io(self):
		vm_records= {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'domid': '73',
				'name_label': 'test1.home.net'},
			 '7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'test2.home.net',
				'domid': '72'}
			}

		val= {  'test1.home.net':{ 'Read': 6, 'Write': 68 }, 
				'test2.home.net': {'Read': 1931, 'Write': 2293}}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		self.mocker.replay()
		self.metrics.server=xs

		result=self.metrics.get_vms_disk_io()
		self.assertEqual(result, val)

	def test_get_vms_net_io(self):
		vm_records= {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'VIFs': [],
				'name_label': 'test1.home.net'},
			 '7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'test2.home.net',
				'VIFs': [ 'a7d7bd0d-8885-6989-53e5-4e56559a286c', 'c31514fb-1471-194b-14eb-3bd54bdbf4cb' ]}
			}

		vif_records = {'a7d7bd0d-8885-6989-53e5-4e56559a286c': {
                                          'io_total_read_kbs': 7714.8544921875,
                                          'io_total_write_kbs': 0.987 },
					 'c31514fb-1471-194b-14eb-3bd54bdbf4cb': {
                                          'io_total_read_kbs': 8331.623046875,
                                          'io_total_write_kbs': 0.375 }}

		val = {'test2.home.net': [{'Rx': 7900011, 'Tx': 1010}, {'Rx': 8531582, 'Tx': 384}], 'test1.home.net': []}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VIF_metrics.get_all_records()
		self.mocker.result(vif_records)
		self.mocker.replay()
		self.metrics.server=xs
		
		result=self.metrics.get_vms_net_io()
		self.assertEqual(result, val)

	def test_get_ram_infos(self):
		host_record = {'memory_free': '900210688', 'memory_total': '4118376448'}

		val = {'total': 3927, 'used': 3069, 'free': 858}
	
		xs = self.mocker.mock()
		xs.getSession()
		xs.xenapi.session.get_this_host(ANY)
		xs.xenapi.host.get_record(ANY)
		self.mocker.result({'metrics': 'dd26c77a-5dfb-f445-0429-a29587ca1822'})
		xs.xenapi.host_metrics.get_record('dd26c77a-5dfb-f445-0429-a29587ca1822')
		self.mocker.result(host_record)
		self.mocker.replay()
		self.metrics.server=xs
		
		result=self.metrics.get_ram_infos()
		self.assertEqual(result, val)

	def test_get_load(self):
		host_record = {'memory_free': '900210688', 'memory_total': '4118376448'}

		xs = self.mocker.mock()
		xs.getSession()
		xs.xenapi.session.get_this_host(ANY)
		xs.xenapi.host.get_record(ANY)
		self.mocker.result({'metrics': 'dd26c77a-5dfb-f445-0429-a29587ca1822'})
		xs.xenapi.host_metrics.get_record('dd26c77a-5dfb-f445-0429-a29587ca1822')
		self.mocker.result(host_record)
		self.mocker.replay()
		self.metrics.server=xs
		
		result=self.metrics.get_load()
		self.assertEqual(result, 78)


	def test_get_vms_cpu_usage(self):
		val = {'test15.home.net': '0.0', 'test22.home.net': '0.0'}

		xenlegacy_mock = Mocker()
		xenlegacy=xenlegacy_mock.mock()
		xenlegacy.xend.domains(True)
		xenlegacy_mock.result(
			[['domain',
			  ['name', 'test15.home.net'],
			  ['cpu_time', 159.379459621]],
			 ['domain',
			  ['name', 'test22.home.net'],
			  ['cpu_time', 146.65212068700001],
			 ]]
		)
		xenlegacy_mock.replay()
		self.node.legacy_server=xenlegacy

		result=self.metrics.get_vms_cpu_usage()
		self.assertEqual(result, val)

	def test_get_vms_record(self):
		val =  {'test15.home.net': 
					{'net': [], 'disk': {'Read': 6, 'Write': 68}, 'cpu': '0.0'}, 
				'test22.home.net': 
					{'net': [
						{'Rx': 7900011, 'Tx': 1010}, 
						{'Rx': 8531582, 'Tx': 384}], 
					'disk': {'Read': 1931, 'Write': 2293}, 'cpu': '0.0'}}

		# Mock for get_vms_cpu_usage
		xenlegacy_mock = Mocker()
		xenlegacy=xenlegacy_mock.mock()
		xenlegacy.xend.domains(True)
		xenlegacy_mock.result(
			[['domain',
			  ['name', 'test15.home.net'],
			  ['cpu_time', 159.379459621]],
			 ['domain',
			  ['name', 'test22.home.net'],
			  ['cpu_time', 146.65212068700001],
			 ]]
		)
		xenlegacy_mock.replay()
		self.node.legacy_server=xenlegacy

		# Mock for get_vms_net_io and get_vms_disk_io
		vm_records= {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'VIFs': [],
				'domid': '73',
				'name_label': 'test15.home.net'},
			 '7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'test22.home.net',
				'domid': '72',
				'VIFs': [ 'a7d7bd0d-8885-6989-53e5-4e56559a286c', 'c31514fb-1471-194b-14eb-3bd54bdbf4cb' ]}
			}

		vif_records = {'a7d7bd0d-8885-6989-53e5-4e56559a286c': {
                                          'io_total_read_kbs': 7714.8544921875,
                                          'io_total_write_kbs': 0.987 },
					 'c31514fb-1471-194b-14eb-3bd54bdbf4cb': {
                                          'io_total_read_kbs': 8331.623046875,
                                          'io_total_write_kbs': 0.375 }}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VIF_metrics.get_all_records()
		self.mocker.result(vif_records)
		self.mocker.replay()
		self.metrics.server=xs

		result=self.metrics.get_vms_record()
		self.assertEqual(result, val)

	def test_get_lvs_size__empty(self):
		self.assertEqual(self.metrics.get_lvs_size([]), dict())
		
	def test_get_lvs_size(self):
		lvs=['/dev/vgrack/root-test1.home.net','/dev/LVM_XEN/usr-test1.home.net','/dev/vgrack/WOO-test1.home.net']
		val={'/dev/LVM_XEN/usr-test1.home.net': 524288.0, 
			'/dev/vgrack/WOO-test1.home.net': 1048576.0, 
			'/dev/vgrack/root-test1.home.net': 4194304.0}

		self.assertEqual(self.metrics.get_lvs_size(lvs), val)
		
	def test_get_available_ram(self):
		val=2432
		vm_records = {
			'6ab3fd4c-d1d3-158e-d72d-3fc4831ae1e5': {
				'domid': '73',
				'metrics': '237f589-e62b-5573-915b-51117c9eb52e',
				'name_label': 'test1.home.net'},
			'a7d7bd0d-8885-6989-53e5-4e56559a286c': {
				'name_label': 'test2.home.net',
				'metrics': 'c31514fb-1471-194b-14eb-3bd54bdbf4cb',
				'domid': '74'},
			'7efcbac8-4714-88ee-007c-0246a3cb52b8': {
				'name_label': 'Domain-0',
				'metrics': '0208f543-e60b-5622-839b-51080c9eb63e',
				'domid': '72'}
		}
		metrics_records = { 
			'237f589-e62b-5573-915b-51117c9eb52e': {'memory_actual': "268435456"}, 
			'c31514fb-1471-194b-14eb-3bd54bdbf4cb': {'memory_actual': "134217728"}, 
			'0208f543-e60b-5622-839b-51080c9eb63e': {'memory_actual': "1073741824"}
		}
		host_record = {'memory_free': '2147483648', 'memory_total': '4118376448'}

		xs = self.mocker.mock()
		xs.xenapi.VM.get_all_records()
		self.mocker.result(vm_records)
		xs.xenapi.VM_metrics.get_all_records()
		self.mocker.result(metrics_records)
		xs.getSession()
		xs.xenapi.session.get_this_host(ANY)
		xs.xenapi.host.get_record(ANY)
		self.mocker.result({'metrics': 'dd26c77a-5dfb-f445-0429-a29587ca1822'})
		xs.xenapi.host_metrics.get_record('dd26c77a-5dfb-f445-0429-a29587ca1822')
		self.mocker.result(host_record)
		self.mocker.replay()
		self.node.server=xs
		self.metrics.server=xs

		self.assertEqual(self.metrics.get_available_ram(), val)


if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
