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

# Use Twisted's trial to run this tests

import cxm.dnscache
from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.internet import error, reactor, defer
from mocker import *
import socket

# Argh, multiple inheritance in diamond is really bad ! But there is no other way to mock twisted...
class DNSCacheTests(unittest.TestCase, MockerTestCase):

	def setUp(self):
		self.dc=cxm.dnscache.DNSCache()

	def test_getinstance(self):
		self.assertIs(
			cxm.dnscache.DNSCache.getInstance(),
			cxm.dnscache.DNSCache.getInstance()
			)

	def test_add__ok(self):
		resolve = self.mocker.replace(reactor.resolve)
		resolve("good.dns.name")
		self.mocker.result(defer.succeed("1.1.1.1"))
		self.mocker.replay()

		d=self.dc.add("good.dns.name")
		return d

	def test_add__fail(self):
		resolve = self.mocker.replace(reactor.resolve)
		resolve("bad.dns.name")
		self.mocker.result(defer.fail(Failure("bad name", error.DNSLookupError)))
		self.mocker.replay()

		d=self.dc.add("bad.dns.name")
		return self.assertFailure(d, error.DNSLookupError)

	def test_get_by_name__incache(self):
		def get_by_name(result):
			return self.dc.get_by_name("good.dns.name")
			
		d=self.test_add__ok()
		d.addCallback(get_by_name)
		d.addCallback(self.assertEqual, "1.1.1.1")
		return d

	def test_get_by_name__notincache(self):
		resolve = self.mocker.replace(reactor.resolve)
		resolve("good.dns.name")
		self.mocker.result(defer.succeed("1.1.1.1"))
		self.mocker.replay()
		
		d=self.dc.get_by_name("good.dns.name")
		d.addCallback(self.assertEqual, "1.1.1.1")
		return d

	def test_get_by_ip__incache(self):
		def get_by_ip(result):
			return self.dc.get_by_ip("1.1.1.1")
			
		d=self.test_add__ok()
		d.addCallback(get_by_ip)
		d.addCallback(self.assertEqual, "good.dns.name")
		return d
	
	def test_get_by_ip__notincache(self):
		ghba = self.mocker.replace(socket.gethostbyaddr)
		ghba("1.1.1.1")
		self.mocker.result(["good.dns.name"])
		self.mocker.replay()
		
		self.assertEqual(self.dc.get_by_ip("1.1.1.1"), "good.dns.name")

# vim: ts=4:sw=4:ai

