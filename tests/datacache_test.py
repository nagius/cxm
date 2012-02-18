#!/usr/bin/python

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

import cxm.datacache
import unittest
from mocker import *

class DataCacheTests(MockerTestCase):

	def setUp(self):
		self.cache=cxm.datacache.DataCache()

	def test_get_ok(self):
		value = "bla"
		self.cache.add("test", 5, value)
		self.assertEqual(self.cache.get("test"), value)
		
	def test_get_missing(self):
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test")
	
	def test_get_outdated(self):
		self.cache.add("test", -5, "value")
		self.assertRaises(cxm.datacache.CacheExpiredException, self.cache.get,"test")
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test")

	def test_delete(self):
		value = "bla"
		self.cache.add("test1", 5, value)
		self.cache.add("test2", 5, value)
		self.cache.delete("test1")
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test1")
		self.assertEqual(self.cache.get("test2"), value)

	def test_clear(self):
		value = "bla"
		self.cache.add("test1", 5, value)
		self.cache.add("test2", 5, value)
		self.cache.clear()
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test1")
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test2")
	
	def test_cleanup(self):
		value = "bla"
		self.cache.add("test1", -5, value)
		self.cache.add("test2", 5, value)
		self.cache.cleanup()
		self.assertRaises(cxm.datacache.CacheMissingException, self.cache.get,"test1")
		self.assertEqual(self.cache.get("test2"), value)

	def test_cache_miss(self):
		value = 26

		obj = self.mocker.mock()
		obj.callback.__name__
		self.mocker.result("myfunc")
		obj.callback("26")
		self.mocker.result(value)
		obj.callback.__name__
		self.mocker.result("myfunc")
		self.mocker.replay()

		self.assertEqual(self.cache.cache(5, False, obj.callback, "26"), value)

	def test_cache_hit(self):
		value = 26

		obj = self.mocker.mock()
		obj.callback.__name__
		self.mocker.result("myfunc")
		self.mocker.replay()

		self.cache.add("myfunc", 5, value)
		self.assertEqual(self.cache.cache(5, False, obj.callback, "26"), value)

	def test_cache_nocache(self):
		value = 26

		obj = self.mocker.mock()
		obj.callback.__name__
		self.mocker.result("myfunc")
		obj.callback("26")
		self.mocker.result(value)
		self.mocker.replay()

		self.assertEqual(self.cache.cache(5, True, obj.callback, "26"), value)

if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
