#!/usr/bin/python
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


# TODO snapshot
# TODO Add a cache to metrics.get_ram_infos()
# TODO add load balancing in create


"""
This module provides an oriented object API for managing Xen Cluster.

Main classes are :
  - XenCluster : object used to do cluster wide actions
  - Node : object used to manipulate a cluster's node
  - VM : object used to access VM properties and configuration
  - Metrics : object used to get node's metrics

Some method could raise ClusterError and ClusterNodeError exceptions.

This module require Xen's modules xen/xm for XenAPI access 
and paramiko module for SSH links.

Some globals booleans variables are avalaible to change the behavior of this module :

 - DEBUG : Print additionnal information about internals datas
 - QUIET : Just print essentials outpouts (usefull for batch parsing)
 - USESSH : Does'nt use the XenAPI, send (mostly) all command via SSH.

"""

import os


VERSION="0.5.1"

# Global read only variables
DEBUG=False
QUIET=False
USESSH=False

# TODO: Variable de configuration a remplacer par un fichier
cfg = { 'VMCONF_PATH' :"/etc/xen/vm/",
		'PATH': "" }


#@staticmethod
def get_nodes_list():
	"""Return the list of actives nodes' hostname used to instanciate the cluster."""
	for line in os.popen(cfg['PATH'] + "mounted.ocfs2 -f"):
		if "ocfs2" in line:
			nodes=line.replace(","," ").split()
			del nodes[0:2]  # Purge unwanted text
			return nodes

#@staticmethod 
#def get_nodes_list(): # bouchon pour test
#   return ['xen0node03.virt.s1.p.fti.net','xen0node01.virt.s1.p.fti.net','xen0node02.virt.s1.p.fti.net']

def get_api_version():
	return VERSION


if __name__ == "__main__":
	"""Main is used to run test case."""
	pass

# vim: ts=4:sw=4:ai
