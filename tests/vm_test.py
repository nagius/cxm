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

import cxm.core, cxm.vm
import unittest, os

class VMTests(unittest.TestCase):

	def setUp(self):
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"

	def test_get_lvs(self):
		lvs = ['/dev/vgrack/root-test1.home.net', '/dev/LVM_XEN/usr-test1.home.net', '/dev/vgrack/WOO-test1.home.net']

		vm=cxm.vm.VM("test1.home.net")
		result=vm.get_lvs()
		self.assertEqual(result, lvs)

	def test_get_ram_via_metrics(self):
		vm=cxm.vm.VM("test1.home.net")
		vm.metrics={'memory_actual': "268435456"}
		self.assertEqual(vm.ram, 256)
		
	def test_get_ram_via_cfg(self):
		vm=cxm.vm.VM("test1.home.net")
		self.assertEqual(vm.ram, 512)

	def test_get_ram_via_params(self):
		vm=cxm.vm.VM("test1.home.net", ram=123)
		self.assertEqual(vm.ram, 123)

	def test_get_ram_via_members(self):
		vm=cxm.vm.VM("test1.home.net")
		vm.ram=456
		self.assertEqual(vm.ram, 456)

	def test_get_start_ram(self):
		vm=cxm.vm.VM("test1.home.net")
		self.assertEqual(vm.ram, 512)

	def test_get_vcpu_via_metrics(self):
		vm=cxm.vm.VM("test1.home.net")
		vm.metrics={'VCPUs_number': "5"}
		self.assertEqual(vm.vcpu, 5)
		
	def test_get_vcpu_via_params(self):
		vm=cxm.vm.VM("test1.home.net", vcpu=2)
		self.assertEqual(vm.vcpu, 2)

	def test_get_vcpu_via_members(self):
		vm=cxm.vm.VM("test1.home.net")
		vm.vcpu=4
		self.assertEqual(vm.vcpu, 4)

	def test_get_state_empty(self):
		vm=cxm.vm.VM("test1.home.net")
		self.assertEqual(vm.state, "======")

	def test_get_state(self):
		vm=cxm.vm.VM("test1.home.net")
		vm.metrics= {'state' : ['blocked','dying'] }
		self.assertEqual(vm.state, "-b---d")

if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
