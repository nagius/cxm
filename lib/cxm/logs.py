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

# TODO logrotate ?

from twisted.python import log
import core
import syslog

# Flag to remember if init() was called
open=False

def init(name):
	global open
	syslog.openlog(name, syslog.LOG_PID, syslog.LOG_DAEMON)
	open=True

def info(*args):
	if open:
		log.msg(*args)
	else:
		if not core.cfg['QUIET']:
			print " ".join(map(str, args))

def debugd(*args):
	"""Print or log a debug message from daemon, if DAEMON_DEBUG is true."""
	if core.cfg['DAEMON_DEBUG']:
		msg = "DEBUG: " + " ".join(map(str, args))
		if open:
			log.msg(msg)
		else:
			print msg
		
def debug(*args):
	"""Print or log a debug message, if API_DEBUG is true."""
	if core.cfg['API_DEBUG']:
		msg = "DEBUG: " + " ".join(map(str, args))
		if open:
			log.msg(msg)
		else:
			print msg

def warn(*args):
	msg = "Warning: " + " ".join(map(str, args))
	if open:
		log.msg(msg)
		syslog.syslog(syslog.LOG_WARNING, msg)
	else:
		print msg

def err(*args):
	msg = "Error: " + " ".join(map(str, args))
	if open:
		log.err(msg)
		syslog.syslog(syslog.LOG_ERR, msg)
	else:
		print msg

def emerg(*args):
	msg = "CRITICAL ERROR: " + " ".join(map(str, args))
	if open:
		log.err(msg)
		syslog.syslog(syslog.LOG_EMERG, msg)
	else:
		print msg

# vim: ts=4:sw=4:ai
