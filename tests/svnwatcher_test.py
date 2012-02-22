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

# Use Twisted's trial to run this tests

from cxm.svnwatcher import *
from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.internet import error, reactor, defer
from mocker import *
import cxm

# TODO: rewrite this with another mocking tool

# Argh, multiple inheritance in diamond is really bad ! But there is no other way to mock twisted...
class SvnwatcherTests(unittest.TestCase, MockerTestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True

	def test_startService__notclean(self):
		node_mocker = Mocker()
		node = node_mocker.mock()
		node.run("svn status tests/stubs/cfg/ 2>&1").read()
		node_mocker.result("notclean")
		node_mocker.replay()

		staticnode_mocker = Mocker()
		staticnode = staticnode_mocker.mock()
		staticnode.getLocalInstance()
		staticnode_mocker.result(node)
		staticnode_mocker.replay()
		# Doing mock with this ugly way because mocker can't replace static func	
		cxm.node.Node=staticnode

		a=self.mocker.replace("cxm.agent.Agent.__init__")
		a()
		self.mocker.replay()

		ss=SvnwatcherService()
		self.assertRaises(Exception,ss.startService)

	def test_startService__standalone(self):
		node_mocker = Mocker()
		node = node_mocker.mock()
		node.run("svn status tests/stubs/cfg/ 2>&1").read()
		node_mocker.result("")
		node_mocker.replay()

		staticnode_mocker = Mocker()
		staticnode = staticnode_mocker.mock()
		staticnode.getLocalInstance()
		staticnode_mocker.result(node)
		staticnode_mocker.replay()
		# Doing mock with this ugly way because mocker can't replace static func	
		cxm.node.Node=staticnode

		a=self.mocker.replace("cxm.agent.Agent.__init__")
		a()
		ping=self.mocker.replace("cxm.agent.Agent.ping")
		ping()
		self.mocker.result(defer.fail(Exception()))
		spawnInotify=self.mocker.replace("cxm.svnwatcher.SvnwatcherService.spawnInotify")
		spawnInotify()

		self.mocker.replay()

		ss=SvnwatcherService()
		d=ss.startService()
		self.assertEquals(ss.agent, None)
		return d

	def test_startService__cluster(self):
		node_mocker = Mocker()
		node = node_mocker.mock()
		node.run("svn status tests/stubs/cfg/ 2>&1").read()
		node_mocker.result("")
		node_mocker.replay()

		staticnode_mocker = Mocker()
		staticnode = staticnode_mocker.mock()
		staticnode.getLocalInstance()
		staticnode_mocker.result(node)
		staticnode_mocker.replay()
		# Doing mock with this ugly way because mocker can't replace static func	
		cxm.node.Node=staticnode

		a=self.mocker.replace("cxm.agent.Agent.__init__")
		a()
		ping=self.mocker.replace("cxm.agent.Agent.ping")
		ping()
		self.mocker.result(defer.succeed("ok"))
		spawnInotify=self.mocker.replace("cxm.svnwatcher.SvnwatcherService.spawnInotify")
		spawnInotify()

		self.mocker.replay()

		ss=SvnwatcherService()
		d=ss.startService()
		self.assertIsInstance(ss.agent, cxm.agent.Agent)
		return d

class InotifyTests(unittest.TestCase, MockerTestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True

	def test_outReceived(self):
		pp=InotifyPP(None)

		# Empty line
		pp.outReceived("\n\n\n")
		self.assertEqual(pp.toAdd, [])
		self.assertEqual(pp.toDel, [])

		# Single line
		pp.outReceived("/ DELETE file1\n")
		self.assertEqual(pp.toAdd, [])
		self.assertEqual(pp.toDel, ['file1'])

		# Multiple line
		pp.outReceived("/ CREATE file2\n / DELETE file3\n\n")
		self.assertEqual(pp.toAdd, ['file2'])
		self.assertEqual(pp.toDel, ['file1', 'file3'])

		# Cleanup reactor
		pp._call.cancel()

	def test_doCommit__ok(self):
		
		node=self.mocker.mock()
		node.run("svn add tests/stubs/cfg/file1 tests/stubs/cfg/file2")
		node.run("svn delete tests/stubs/cfg/file3 tests/stubs/cfg/file4")
		node.run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")

		doUpdate=self.mocker.replace("cxm.svnwatcher.InotifyPP.doUpdate")
		doUpdate()

		self.mocker.replay()

		pp=InotifyPP(node)

		pp.toAdd = ['file1', 'file2']
		pp.toDel = ['file3', 'file4']

		pp.doCommit()
		# TODO test with error


	def test_doUpdate__standalone(self):
		node=self.mocker.mock()
		node.run("svn update tests/stubs/cfg/")
		self.mocker.replay()
		
		pp=InotifyPP(node)
		pp.doUpdate()

# Doesn't work with mocker, see svnwatcher_mockito_test.py
#	def test_doUpdate__cluster(self):


# vim: ts=4:sw=4:ai


