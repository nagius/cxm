#!/usr/bin/env python
# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>

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

from cxm.diskheartbeat import *
import cxm
import unittest
from mocker import *

class DiskHeartbeatTests(MockerTestCase):

	def setUp(self):
		cxm.core.cfg['HB_DISK']="hbdisk"

	def test_format(self):
		file=self.mocker.mock()
		file.write(ANY)
		self.mocker.count(35, None)
		file.seek(0)
		file.seek(4096)
		file.close()

		openmock=self.mocker.replace("__builtin__.open")
		openmock("hbdisk", "wb", 0)
		self.mocker.result(file)

		self.mocker.replay()

		DiskHeartbeat.format()

	def test_is_in_use__ok(self):
		diskheartbeat=self.mocker.replace("cxm.diskheartbeat.DiskHeartbeat")
		diskheartbeat().get_nr_node()
		self.mocker.result(2)
		self.mocker.replay()
		
		self.assertEquals(DiskHeartbeat.is_in_use(), True)
		
	def test_is_in_use__fail(self):
		diskheartbeat=self.mocker.replace("cxm.diskheartbeat.DiskHeartbeat")
		diskheartbeat().get_nr_node()
		self.mocker.throw(DiskHeartbeatError())
		self.mocker.replay()
		
		self.assertEquals(DiskHeartbeat.is_in_use(), False)

	def test_get_nr_node(self):
		file=self.mocker.mock()
#		file.write(ANY)
#		self.mocker.count(35, None)
#		file.seek(0)
#		file.seek(4096)
		file.close()

		openmock=self.mocker.replace("__builtin__.open")
		openmock()
		#openmock("hbdisk", "wb", 0)
		self.mocker.result(file)

		self.mocker.replay()
		
		ds=DiskHeartbeat()

		self.assertEquals(ds.get_nr_node(), 3)

if __name__ == "__main__":
    unittest.main()

# vim: ts=4:sw=4:ai

