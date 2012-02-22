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
import cxm
from mockito import mock, when, verify

# TODO: rewrite this with another mocking tool

class SvnwatcherTests(unittest.TestCase):
	def setUp(self):
		cxm.core.cfg['VMCONF_DIR'] = "tests/stubs/cfg/"

	def test_doUpdate__cluster(self):

		agent=mock()
		when(agent).getNodesList().thenReturn(defer.succeed(["node1", "node2"]))

		n1=mock()
		n1.run("svn update tests/stubs/cfg/")
		n2=mock()
		n2.run("svn update tests/stubs/cfg/")

		cluster=mock()
		when(cluster).get_nodes().thenReturn([n1, n2])
		
		when(cxm.xencluster.XenCluster).getDeferInstance(["node1", "node2"]).thenReturn(defer.succeed(cluster))

		pp=InotifyPP(None, agent)
		d=pp.doUpdate()
	
		verify(agent).getNodesList()
		verify(cxm.xencluster.XenCluster).getDeferInstance(["node1", "node2"])
		verify(cluster).get_nodes()
		verify(n1).run("svn update tests/stubs/cfg/")
		verify(n2).run("svn update tests/stubs/cfg/")

		return d

	


