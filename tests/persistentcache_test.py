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

from cxm.persistentcache import *
import cxm
import unittest
from mocker import *
import os

class PersistentCacheTests(MockerTestCase):

	def setUp(self):
		self.cachefile="/tmp/unittest.cache"

	def tearDown(self):
		try:
			os.unlink(self.cachefile)
			os.unlink(self.cachefile+".lock")
		except OSError:
			pass

	def test_ok(self):
		func=self.mocker.mock()
		func()
		self.mocker.count(1)
		self.mocker.result("returnvalue")
		self.mocker.replay()

		cache=PersistentCache(self.cachefile, 1, 1)
		decorator=cache.__call__(func)

		self.assertEquals(decorator(), "returnvalue")
		
	def test_badinput(self):
		func=self.mocker.mock()
		func()
		self.mocker.count(1)
		self.mocker.result("returnvalue")
		self.mocker.replay()

		f=open(self.cachefile, 'w')
		f.write("some bad data")
		f.close()

		cache=PersistentCache(self.cachefile, 1, 1)
		decorator=cache.__call__(func)

		self.assertEquals(decorator(), "returnvalue")
		
	def test_missing(self):
		func=self.mocker.mock()
		func()
		self.mocker.count(1)
		self.mocker.result("returnvalue")

		openmock=self.mocker.replace("__builtin__.open")
		openmock(self.cachefile, "r")
		self.mocker.throw(IOError())

		self.mocker.replay()

		cache=PersistentCache(self.cachefile, 1, 1)
		decorator=cache.__call__(func)

		self.assertEquals(decorator(), "returnvalue")

	def test_locked(self):
		func=self.mocker.mock()
		func()
		self.mocker.count(1)
		self.mocker.result("returnvalue")
		self.mocker.replay()

		open(self.cachefile+".lock", 'w').close()

		cache=PersistentCache(self.cachefile, 1, 0)
		decorator=cache.__call__(func)

		self.assertEquals(decorator(), "returnvalue")

	def test_expired(self):
		func=self.mocker.mock()
		func()
		self.mocker.count(2)
		self.mocker.result("returnvalue")
		self.mocker.replay()

		cache=PersistentCache(self.cachefile, -1, 1)
		decorator=cache.__call__(func)

		# Missing file
		self.assertEquals(decorator(), "returnvalue")
		# Expired cache
		self.assertEquals(decorator(), "returnvalue")

	def test_params_with_bug(self):
		func=self.mocker.mock()
		func("param1")
		self.mocker.count(1)
		self.mocker.result("returnvalue")
		self.mocker.replay()

		cache=PersistentCache(self.cachefile, 1, 1)
		decorator=cache.__call__(func)

		# Missing file
		self.assertEquals(decorator("param1"), "returnvalue")
		# Hit cache with previous parameter
		self.assertEquals(decorator("param2"), "returnvalue")

if __name__ == "__main__":
    unittest.main()

# vim: ts=4:sw=4:ai

