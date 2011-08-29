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

# Note that some part of code came from xen/xm

# TODO snapshot
# Formaliser documentation des fonctions
# TODO adaptation puor xenbaloond dans VM.get_ram() get_real_ram() ?


"""
This package provides an oriented object API for managing Xen Cluster.

Main classes are :
  - XenCluster : object used to do cluster wide actions
  - Node : object used to manipulate a cluster's node
  - VM : object used to access VM properties and configuration
  - Metrics : object used to get node's metrics
  - Agent : object used to call daemon's RPC

Some method could raise ClusterError and ClusterNodeError exceptions.
Other classes are for internal purpose.

This package require Xen's modules xen/xm for XenAPI access 
and paramiko module for SSH links.

Some globals variables are avalaibles in the configuration file "/etc/xen/cxm.conf" 
to change the behavior of this package. Only 'CLUSTER_NAME' and 'HB_DISK' are 
mandatory in order to start cxmd daemon. See example file 'cxm.conf' for more
informations.

"""

import os, sys
import meta

# Default configuration
cfg = { 
	'VMCONF_DIR': "/etc/xen/vm/",
	'PATH': "",					# Only usefull for testing
	'NOREFRESH': False,
	'DEBUG': False,
	'DAEMON_DEBUG': False,		# For cxmd
	'QUIET': False,
	'USESSH': False,
	'LB_MAX_VM_PER_NODE': 20,
	'LB_MAX_LAYER': 4,
	'LB_MIN_GAIN': 5,
	'FENCE_CMD': "cxm_fence",	# Take the node's name as first param
	'DISABLE_FENCING': False,
	'CLUSTER_NAME': None,		# (string) Mandatory for cxmd
	'ALLOWED_NODES': [],
	'UDP_PORT': 1255,
	'TCP_PORT': 1255,
	'UNIX_PORT': "/var/run/cxmd.socket",
	'HB_DISK': None,			# (string) Mandatory for cxmd
	}


def get_api_version():
	"""Return the version number of this API."""
	return meta.version

def load_cfg():
	"""Load the global configuration file into the cfg dict."""
	try:
		execfile("/etc/xen/cxm.conf",dict(),cfg)
	except Exception,e:
		print "Configuration file error: %s" % e
		sys.exit(3)

	if not cfg['VMCONF_DIR'].endswith("/"):
		cfg['VMCONF_DIR']+="/"

def debug(*args):
	"""Print a debug message, if DEBUG is true."""
	if cfg['DEBUG']:
		print "DEBUG", " ".join(map(str,args))

# vim: ts=4:sw=4:ai
