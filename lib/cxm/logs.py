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

# TODO logrotate ?

from twisted.python import log
import core
import syslog

def init(name):
	syslog.openlog(name, syslog.LOG_PID, syslog.LOG_DAEMON)

def info(*args):
	log.msg(*args)

def debug(*args):
	if core.cfg['DAEMON_DEBUG']:
		log.msg("DEBUG:", *args)
		
def warn(*args):
	message = " ".join(map(str, args))
	log.msg("Warning: %s" % (message))
	syslog.syslog(syslog.LOG_WARNING, message)

def err(*args):
	message = " ".join(map(str, args))
	log.err("Error: %s" % (message))
	syslog.syslog(syslog.LOG_ERR, message)

def emerg(*args):
	message = " ".join(map(str, args))
	log.err("CRITICAL ERROR: %s" % (message))
	syslog.syslog(syslog.LOG_EMERG, message)

# vim: ts=4:sw=4:ai
