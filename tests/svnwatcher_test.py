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
from mockito import *
import cxm

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

		static_mocker = Mocker()
		static = static_mocker.replace("cxm.node.Node")
		static.getLocalInstance()
		static_mocker.result(node)
		static_mocker.replay()

		agent_mocker = Mocker()
		a=agent_mocker.replace("cxm.agent.Agent.__init__")
		a()
		agent_mocker.replay()

		ss=SvnwatcherService()
		self.assertRaises(Exception,ss.startService)

		node_mocker.verify()
		agent_mocker.verify()
		static_mocker.verify()

	def test_startService__standalone(self):
		node_mocker = Mocker()
		node = node_mocker.mock()
		node.run("svn status tests/stubs/cfg/ 2>&1").read()
		node_mocker.result("")
		node_mocker.replay()

		static_mocker = Mocker()
		static = static_mocker.replace("cxm.node.Node")
		static.getLocalInstance()
		static_mocker.result(node)
		static_mocker.replay()

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

		def verifyCalls(dummy):
			self.assertEquals(ss.agent, None)
			node_mocker.verify()
			static_mocker.verify()

		d.addCallback(verifyCalls)
		return d

	def test_startService__cluster(self):
		node_mocker = Mocker()
		node = node_mocker.mock()
		node.run("svn status tests/stubs/cfg/ 2>&1").read()
		node_mocker.result("")
		node_mocker.replay()

		static_mocker = Mocker()
		static = static_mocker.replace("cxm.node.Node")
		static.getLocalInstance()
		static_mocker.result(node)
		static_mocker.replay()

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

		def verifyCalls(dummy):
			self.assertIsInstance(ss.agent, cxm.agent.Agent)
			node_mocker.verify()
			static_mocker.verify()

		d.addCallback(verifyCalls)
		return d

# I've got problems running Mocker with twisted threads, so using Mockito here
class InotifyTests(unittest.TestCase):

	def setUp(self):
		cxm.core.cfg['PATH'] = "tests/stubs/bin/"
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"
		cxm.core.cfg['QUIET']=True

	def test_outReceived__emptyLine(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("\n\n\n")

		def verifyCalls():
			verifyZeroInteractions(node)

		reactor.callLater(0, verifyCalls)
		
	def test_outReceived__delete(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ DELETE file1\n")

		def verifyCalls():
			verify(node).run('svn delete tests/stubs/cfg/file1')
			verify(node).run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")
			verify(node).run('svn update tests/stubs/cfg/')
			verifyNoMoreInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__modify(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ MODIFY file1\n")

		def verifyCalls():
			verify(node).run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")
			verify(node).run('svn update tests/stubs/cfg/')
			verifyNoMoreInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__multipleLine(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ CREATE file2\n / DELETE file3\n\n")

		def verifyCalls():
			verify(node).run('svn delete tests/stubs/cfg/file3')
			verify(node).run('svn add tests/stubs/cfg/file2')
			verify(node).run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")
			verify(node).run('svn update tests/stubs/cfg/')
			verifyNoMoreInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__blacklisted(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ CREATE tempfile.tmp\n")

		def verifyCalls():
			verifyZeroInteractions(node)

		reactor.callLater(0, verifyCalls)
		
	def test_outReceived__createDelete(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ CREATE file4\n / DELETE file4\n")

		def verifyCalls():
			verifyZeroInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__multipleCreateDelete(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ CREATE file4\n / CREATE file4\n / DELETE file4\n")

		def verifyCalls():
			verifyZeroInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__deleteCreate(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ DELETE file4\n / CREATE file4\n")

		def verifyCalls():
			verify(node).run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")
			verify(node).run('svn update tests/stubs/cfg/')
			verifyNoMoreInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__modifyDelete(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ MODIFY file4\n / DELETE file4\n")

		def verifyCalls():
			verify(node).run('svn delete tests/stubs/cfg/file4')
			verify(node).run("svn --non-interactive commit -m 'svnwatcher autocommit' tests/stubs/cfg/")
			verify(node).run('svn update tests/stubs/cfg/')
			verifyNoMoreInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_outReceived__createModifyDelete(self):
		node=mock()
		pp=InotifyPP(node)
		pp.delay=0 # To trigger delayedCall just now

		pp.outReceived("/ CREATE file5\n / MODIFY file5\n / DELETE file5\n")

		def verifyCalls():
			verifyZeroInteractions(node)

		reactor.callLater(0, verifyCalls)

	def test_doUpdate__standalone(self):
		node=mock()
		pp=InotifyPP(node)
		d=pp.doUpdate()

		def verifyCalls(dummy):
			verify(node).run("svn update tests/stubs/cfg/")
			verifyNoMoreInteractions(node)

		d.addCallback(verifyCalls)
		return d

	def test_doUpdate__cluster(self):
		agent=mock()
		when(agent).getNodesList().thenReturn(defer.succeed(["node1", "node2"]))

		n1=mock()
		n2=mock()
		cluster=mock()
		when(cluster).get_nodes().thenReturn([n1, n2])

		when(cxm.xencluster.XenCluster).getDeferInstance(["node1", "node2"]).thenReturn(defer.succeed(cluster))

		pp=InotifyPP(None, agent)
		d=pp.doUpdate()

		def verifyCalls(dummy):
			verify(agent).getNodesList()
			verifyNoMoreInteractions(agent)
			verify(cxm.xencluster.XenCluster).getDeferInstance(["node1", "node2"])
			verify(cluster).get_nodes()
			verifyNoMoreInteractions(cluster)
#			verify(n1).run("svn update tests/stubs/cfg/")
#			verify(n2).run("svn update tests/stubs/cfg/")

		d.addCallback(verifyCalls)
		return d


# vim: ts=4:sw=4:ai


