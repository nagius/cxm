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


import cxm.core
import unittest, os, sys


class CoreTests(unittest.TestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"

	def test_get_nodes_list(self):
		values = ['xen0node01.home.net','xen0node02.home.net','xen0node03.home.net']

		result=cxm.core.get_nodes_list()
		self.assertEqual(result, values)

	def test_api_version(self):
		version = "0.6.1"

		result=cxm.core.get_api_version()
		self.assertEqual(result, version)
		

if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
