# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2010-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
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


"""
This module is the command line interface for managing cxm daemon.
"""

import sys, os, time
from optparse import OptionParser, OptionGroup
from twisted.internet import reactor, defer, threads
from twisted.internet.error import ConnectError
import core
from diskheartbeat import DiskHeartbeat
from agent import Agent


def ctl_ping(*args):
	"""Ping local daemon."""
	def success(result):
		if result == 'PONG':
			print "OK"
		else:
			print >>sys.stderr, "Bad response."
			raise SystemExit(2)

	agent=Agent()
	d=agent.ping()
	d.addCallback(success)
	
	return d

def ctl_listnodes(*args):
	"""List current connected nodes."""
	def success(result):
		assert type(result) == list, "Result should be a list"
		for node in sorted(result):
			print node

	agent=Agent()
	d=agent.getNodesList()
	d.addCallback(success)
	
	return d

def ctl_status(*args):
	"""Print status of the local daemon."""
	def success(result):
		print "Role:", result['role']
		print "Master:", result['master']
		print "Since:", time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(result['lastTallyDate']))
		print "State:", result['state']

	agent=Agent()
	d=agent.getState()
	d.addCallback(success)
	
	return d

def ctl_dump(*args):
	"""Dump current internal memory."""
	def success(result):
		import pprint
		pprint.pprint(result)

	agent=Agent()
	d=agent.getDump()
	d.addCallback(success)
	
	return d

def ctl_election(*args):
	"""Force master to do a new election."""
	agent=Agent()

	def printMaster(result):
		print "New master is:", result['master']

	def success(result):
		print "Election started..."
		time.sleep(2)
		d=agent.getState()
		d.addCallback(printMaster)
		return d

	d=agent.forceElection()
	d.addCallback(success)
	
	return d

def ctl_quit(*args):
	"""Shutdown local daemon."""
	agent=Agent()

	def success(result):
		print "Daemon shutdown requested..."

	def checkState(result):
		if result['state']=="recovery" and result['role']=="active":
			print "Warning: Local node is the master and a recovery process is running."
			print "This is not a good idea to shutdown master now. You may loose some VM."
			if(raw_input("Proceed anyway ? [y/N]:").upper() != "Y"):
				print "Aborded by user."
				raise SystemExit(0)

		d=agent.quit()
		d.addCallback(success)
		return d
		
	# Get cluster state
	d=agent.getState()
	d.addCallback(checkState)
	
	return d

def ctl_format(*args):
	"""Format heartbeat device with cxm's filesystem."""
	def format():
		if DiskHeartbeat.is_in_use():
			nodes=DiskHeartbeat().get_all_ts().keys()
			print "Warning: Heartbeat disk is in use by:", ", ".join(nodes)

			if(raw_input("Proceed ? [y/N]:").upper() != "Y"):
				print "Aborded by user."
				raise SystemExit(0)

		DiskHeartbeat.format()
		print "Device", core.cfg['HB_DISK'], "formatted."

	return threads.deferToThread(format)

def ctl_panic(*args):
	"""Ask master to engage panic mode."""
	def success(result):
		print "Panic mode requested..."

	agent=Agent()
	d=agent.panic()
	d.addCallback(success)
	
	return d

def ctl_recover(*args):
	"""Ask master to recover from panic mode."""
	def success(result):
		print "Recovering from panic mode... Please check logs."

	agent=Agent()
	d=agent.recover()
	d.addCallback(success)
	
	return d

def ctl_kill(hostname):
	"""Ask master to kill the specified node."""
	def success(result):
		print "Node", hostname, "successfully killed."

	print "Node", hostname, "will be removed from cluster without care."
	if(raw_input("Are you sure ? [y/N]:").upper() != "Y"):
		print "Aborded by user."
		raise SystemExit(0)

	agent=Agent()
	d=agent.kill(hostname)
	d.addCallback(success)
	
	return d


commands = {
	'ping': ctl_ping,
	'listnodes': ctl_listnodes,
	'status': ctl_status,
	'dump': ctl_dump,
	'election': ctl_election,
	'quit': ctl_quit,
	'format': ctl_format,
	'panic': ctl_panic,
	'recover': ctl_recover,
	'kill': ctl_kill,
}


# Command line parsing
##########################################################

def get_parser():
	"""Parse command line options and return an OptionParser object """

	parser = OptionParser(version="%prog "+core.get_api_version())
	parser.add_option("-p", "--ping",
						action="store_true", dest="ping", default=False,
						help="Ping local daemon.")
	parser.add_option("-l", "--list-nodes",
						action="store_true", dest="listnodes", default=False,
						help="List currents nodes in the cluster.")
	parser.add_option("-s", "--status",
						action="store_true", dest="status", default=False,
						help="Print current daemon status.")
	parser.add_option("-d", "--dump",
						action="store_true", dest="dump", default=False,
						help="Dump current internal memory (usefull for debugging).")
	parser.add_option("-e", "--force-election",
						action="store_true", dest="election", default=False,
						help="Force a new master's election.")
	parser.add_option("-q", "--quit",
						action="store_true", dest="quit", default=False,
						help="Shutdown local daemon.")

	group = OptionGroup(parser, "Dangerous Options",
						"Be sure you understand what you're doing before use.")

	group.add_option("-f", "--format",
						action="store_true", dest="format", default=False,
						help="Format the heartbeat device.")
	group.add_option("--force-panic",
						action="store_true", dest="panic", default=False,
						help="Switch master into panic mode.")
	group.add_option("-r", "--recover",
						action="store_true", dest="recover", default=False,
						help="Recover from panic mode. Should be run on the master's node.")
	group.add_option("-k", "--kill",
						action="store", type="string", dest="kill", metavar="hostname", default=False,
						help="Remove the specified node from the cluster. You can't kill the master.")

	parser.add_option_group(group)

	parser.usage = "%prog option"
	parser.epilog = "For more help on 'cxmd_ctl' see the cxmd_ctl(1) man page."

	return parser

def run():
	"""Run cxmd_ctl command line interface."""

	# Parse command line
	parser=get_parser()
	(options, args) = parser.parse_args()

	def syntax_error(msg):
		print >>sys.stderr, "Syntax error:", msg
		parser.print_help()
		sys.exit(3)

	# Check args
	if(len(args)>0):
		syntax_error("Too many arguments.")

	# Get selected options
	keys=list()
	for key in options.__dict__.keys():
		if options.__dict__[key]:
			keys.append(key)

	# Check options
	if len(keys)>1:
		syntax_error("Too many arguments.")

	def quit(result):
		if not reactor._stopped:
			reactor.stop()

	def exitWithCode(returnCode):
		sys.stdout.flush()
		sys.stderr.flush()
		os._exit(returnCode)

	def fail(reason):
		# Handle exit code
		if reason.check(SystemExit):
			returnCode=int(reason.getErrorMessage())
		else:
			returnCode=1
			if core.cfg['API_DEBUG']:
				reason.printTraceback()
			else:
				if reason.check(ConnectError):
					print "Can't contact cxmd. Is daemon running ?"
				else:
					print >>sys.stderr, "Error:", reason.getErrorMessage()
	
		reactor.addSystemEventTrigger('after', 'shutdown', exitWithCode, returnCode)
	
	# Call specified command
	try:
		d=commands[keys[0]](options.__dict__[keys[0]])
		d.addErrback(fail)
		d.addBoth(quit)
	except IndexError:
		syntax_error("Need at least one argument.")

	reactor.run()

# vim: ts=4:sw=4:ai
