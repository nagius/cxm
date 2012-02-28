# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
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

from twisted.internet import protocol, reactor, threads, defer
from twisted.application.service import Service
from twisted.internet.base import DelayedCall

from agent import Agent
from xencluster import XenCluster
import node, core
import logs as log

class InotifyPP(protocol.ProcessProtocol):
	
	# List of filenames ignored by commit
	blacklist=['tempfile.tmp']

	# Name of the global lock
	LOCK="SVNWATCHER"

	def __init__(self, node, agent=None):
		self.added=list()
		self.deleted=list()
		self.updated=list()
		self._call=None
		self.node=node
		self.agent=agent
		self.commitRunning=False   # Local lock system

		if self.agent:
			# Short delay to quickly propagate modifications to others nodes (in seconds)
			self.delay=0.5
		else:
			# We wait more longer before autocommit if we are standalone
			self.delay=5     

	def connectionMade(self):
		log.info("Inotify started.")

	def outReceived(self, data):
		log.debugd("Received:", data)

		for line in data.split('\n'):
			if len(line) <= 0:
				continue

			(path, action, file)=line.split()

			if file in self.blacklist:
				continue

			if action == "CREATE":
				if file in self.deleted:		# Usecase DELETE+CREATE
					self.deleted.remove(file)
					self.updated.append(file)
				else:
					self.added.append(file)
			elif action == "DELETE":
				if file in self.added: 			# Usecase CREATE+DELETE
					self.added.remove(file)
				else:
					self.deleted.append(file)
				if file in self.updated:		# Usecase MODIFY+DELETE
					self.updated.remove(file)
			elif action == "MODIFY":
				self.updated.append(file)

			# Remove duplicate entries
			self.added=list(set(self.added))
			self.deleted=list(set(self.deleted))
			self.updated=list(set(self.updated))

		self.rescheduleCommit()

	def rescheduleCommit(self):
		if isinstance(self._call, DelayedCall) and self._call.active():
			self._call.reset(self.delay)
		else:
			self._call=reactor.callLater(self.delay, self.doCommit)

	def doCommit(self):
		# Semi-global variables used by inner functions
		added=list()
		deleted=list()
		updated=list()

		def commit():
			if len(added) > 0:
				self.node.run("svn add " + " ".join(map(lambda x: core.cfg['VMCONF_DIR']+x, added)))
			if len(deleted) > 0:
				self.node.run("svn delete " + " ".join(map(lambda x: core.cfg['VMCONF_DIR']+x, deleted)))
			self.node.run("svn --non-interactive commit -m 'svnwatcher autocommit' "+core.cfg['VMCONF_DIR'])

		def commitEnded(result):
			if self.agent:
				log.info("Cluster updated.")
			else:
				log.info("Local node updated.")
				
		def commitFailed(reason):
			log.err("SVN failed: %s" % reason.getErrorMessage())

		def releaseLock(result):
			self.commitRunning=False
			if self.agent:
				self.agent.releaseLock(self.LOCK)	

		def checkLock(result):
			# If result is true, no commit running (lock successfully grabbed)
			if result:
				# Get a local copy for thread's work
				# Use .extend insted of = due to scope restriction (vars are in the parent function)
				added.extend(self.added)
				deleted.extend(self.deleted)
				updated.extend(self.updated)
				self.added=list()
				self.deleted=list()
				self.updated=list()

				log.info("Committing for "+", ".join(set(added+deleted+updated)))
				self.commitRunning=True

				d=threads.deferToThread(commit)
				d.addCallback(lambda _: self.doUpdate())
				d.addCallbacks(commitEnded, commitFailed)
				d.addCallback(releaseLock)
				return d
			else:
				log.debugd("Commit already running: rescheduling.")
				self.rescheduleCommit()
				return defer.succeed(None)

		# Don't commit if there is no updates
		log.debugd("Trigger commit: ADD%s DEL%s UP%s" % (self.added, self.deleted, self.updated))
		if len(self.added+self.deleted+self.updated) <= 0:
			return defer.succeed(None)

		# Check for locks of a previous commit still running
		if self.agent:
			# Cluster mode 
			d=self.agent.grabLock(self.LOCK)
			d.addCallback(checkLock)
		else:
			# Standalone mode
			d=checkLock(not self.commitRunning)

		d.addErrback(log.err)
		return d
		
	def doUpdate(self):
		def doNodeUpdate(node):
			d=threads.deferToThread(node.run, "svn update "+ core.cfg['VMCONF_DIR'])
			return d

		# This is used to fire a mono-Failure in the parent deferred
		def checkErrors(results):
			for result in results:
				if not result[0]:
					raise Exception(result[1].getErrorMessage())

		def doClusterUpdate(result):
			ds=list()
			for node in result.get_nodes():
				d=doNodeUpdate(node)
				ds.append(d)

			dl=defer.DeferredList(ds, consumeErrors=1)
			dl.addCallback(checkErrors)
			return dl

		def getCluster(result):
			d=XenCluster.getDeferInstance(result)
			d.addCallback(doClusterUpdate)
			return d

		# Use local agent to avoir opening a new connection
		if self.agent:
			d=self.agent.getNodesList()
			d.addCallback(getCluster)
			return d
		else:
			d=doNodeUpdate(self.node)
			return d
			
	def processEnded(self, reason):
		log.warn("Inotify has died: %s" % (reason.value))
		try:
			reactor.stop()
		except:
			pass


class SvnwatcherService(Service):

	def __init__(self):
		self.node=node.Node.getLocalInstance() # Local node, always connected
		self.agent=Agent()		# Factory will be stopped if cxmd does'nt respond

	def startService(self):
		def standalone(reason):
			log.info("Starting in standalone mode.")
			self.agent=None
			
		def cluster(result):
			log.info("Starting in cluster mode.")

		Service.startService(self)

		msg=self.node.run("svn status "+core.cfg['VMCONF_DIR'] +" 2>&1").read()
		if len(msg)>0:
			log.err("Your repo is not clean. Please check it : %s" % (msg))
			raise Exception("SVN repo not clean")

		d=self.agent.ping()
		d.addCallbacks(cluster, standalone)
		d.addBoth(lambda _: self.spawnInotify())
		d.addErrback(log.err)
		return d
	
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

	def forceUpdate(self):
		log.info("SIGHUP received: updating all repos.")

		def commitEnded(result):
			if self.agent:
				log.info("Cluster updated.")
			else:
				log.info("Local node updated.")
				
		def commitFailed(reason):
			log.err("SVN failed: %s" % reason.getErrorMessage())

		# This is a manual entry-point for recovery : no locks handled
		d=self.pp.doUpdate()
		d.addCallbacks(commitEnded, commitFailed)

	def spawnInotify(self):
		# We use this ugly way because Pyinotify and Twisted's INotify require Python 2.6
		argv=["inotifywait", "-e", "create", "-e", "modify", "-e", "delete", "-m", core.cfg['VMCONF_DIR'], "--exclude", "/\.|~$|[0-9]+$"]
		self.pp = InotifyPP(self.node, self.agent)
		self._process=reactor.spawnProcess(self.pp, argv[0], argv, {})


# vim: ts=4:sw=4:ai
