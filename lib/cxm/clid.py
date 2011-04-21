#-*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2010 - Nicolas AGIUS <nagius@astek.fr>
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
		print "Actives nodes:", ", ".join(result)

	agent=Agent()
	d=agent.getNodesList()
	d.addCallback(success)
	
	return d

def ctl_status(*args):
	"""Print status of the local daemon."""
	def success(result):
		print "Role:", result['role']
		print "Master:", result['master']
		print "State:", result['state']

	agent=Agent()
	d=agent.getState()
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
	def success(result):
		print "Daemon shutdown requested..."

	agent=Agent()
	d=agent.quit()
	d.addCallback(success)
	
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
	"""Ask master to recover from panic mode."""
	def success(result):
		print "Node", hostname, "successfully killed."

	agent=Agent()
	d=agent.kill(hostname)
	d.addCallback(success)
	
	return d


commands = {
	'ping': ctl_ping,
	'listnodes': ctl_listnodes,
	'status': ctl_status,
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

	parser = OptionParser(version="%prog "+core.VERSION)
	parser.add_option("-p", "--ping",
						action="store_true", dest="ping", default=False,
						help="Ping local daemon.")
	parser.add_option("-l", "--list-nodes",
						action="store_true", dest="listnodes", default=False,
						help="List currents nodes in the cluster.")
	parser.add_option("-s", "--status",
						action="store_true", dest="status", default=False,
						help="Print current daemon's status.")
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

	def fail(reason):
		# Handle exit code
		if reason.check(SystemExit):
			rc=int(reason.getErrorMessage())
		else:
			rc=1
			if core.cfg['DEBUG']:
				reason.printTraceback()
			else:
				print >>sys.stderr, "Error:", reason.getErrorMessage()
	
		reactor.addSystemEventTrigger('after', 'shutdown', os._exit, rc)
	
	# Call specified command
	d=commands[keys[0]](options.__dict__[keys[0]])
	d.addErrback(fail)
	d.addBoth(quit)

	reactor.run()

# vim: ts=4:sw=4:ai
