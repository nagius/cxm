# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011 - Nicolas AGIUS <nagius@astek.fr>
# $Id:$

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

from twisted.internet import protocol, reactor
from twisted.application.service import Service
from twisted.internet.base import DelayedCall

from copy import deepcopy
import platform

import node, core
import logs as log

class InotifyPP(protocol.ProcessProtocol):
	
	def __init__(self, localNode, nodes=None):
		self.toAdd=list()
		self.toDel=list()
		self._call=None
		self.node=localNode
		self.nodes=nodes

	def connectionMade(self):
		log.info("Inotify started.")

	def outReceived(self, data):
		for line in data.split('\n'):
			if len(line) <= 0:
				continue
			info=line.split()
			if info[1] == "CREATE":
				self.toAdd.append(info[2])
			elif info[1] == "DELETE":
				self.toDel.append(info[2])
		
		if isinstance(self._call, DelayedCall) and self._call.active():
			self._call.reset(0.5)
		else:
			self._call=reactor.callLater(0.5, self.doCommit)

	def doCommit(self):
		toAdd=deepcopy(self.toAdd)
		self.toAdd=list()
		toDel=deepcopy(self.toDel)
		self.toDel=list()

		try:
			if len(toAdd) > 0:
				self.node.run("svn add " + " ".join(map(lambda x: core.cfg['VMCONF_DIR']+x, toAdd)))
			if len(toDel) > 0:
				self.node.run("svn delete " + " ".join(map(lambda x: core.cfg['VMCONF_DIR']+x, toDel)))
			self.node.run("svn --non-interactive commit -m 'svnwatcher autocommit' "+core.cfg['VMCONF_DIR'])
			self.doUpdate()
		except Exception, e:
			print "SVN failed: " + str(e)
			reactor.stop()
		
	def doUpdate(self):
		self.node.run("svn update "+ core.cfg['VMCONF_DIR'])

	def processEnded(self, reason):
		log.warn("Inotify has died: %s" % (reason.value))
		try:
			reactor.stop()
		except:
			pass


class SvnwatcherService(Service):

	def __init__(self):
		pass

	def startService(self):
		Service.startService(self)

		self.node=node.Node(platform.node())

		msg=self.node.run("svn status "+core.cfg['VMCONF_DIR'] +" 2>&1").read()
		if len(msg)>0:
			log.err("Your repo is not clean. Please check it : %s" % (msg))
			raise Exception("SVN repo not clean")

		reactor.callWhenRunning(self.spawnInotify)
	
	def stopService(self):
		if self.running:
			Service.stopService(self)

			try:
				self._process.signalProcess('TERM')
			except:
				pass

			try:
				reactor.stop()
			except:
				pass

	def spawnInotify(self):
		argv=["inotifywait", "-e", "create", "-e", "modify", "-e", "delete", "-m", core.cfg['VMCONF_DIR'], "--exclude", "/\.|~$|[0-9]+$"]
		pp = InotifyPP(self.node)
		self._process=reactor.spawnProcess(pp, argv[0], argv, {})


# vim: ts=4:sw=4:ai
