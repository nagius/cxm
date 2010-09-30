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


"""
This module is the command line interface of cxm.
"""


import sys, os
import atexit
from optparse import OptionParser
import core, xencluster, node


def select_node_by_vm(cluster, vm, options):
	"""
	Search the node where the given is running VM.

	Return the selected node for operation.
	If options.node is specified, return the coresponding node.
	"""
	if options.node:
		node=cluster.get_node(options.node)
	else:
		nodes=cluster.search_vm_started(vm)
		if(len(nodes)>1):
			print "** ERROR : Multiples instances found on :"
			print "**  ->  " + ", ".join([n.get_hostname() for n in nodes])
			print "** You may try --force-node, but your VM is probably already dead..."
			sys.exit(2)

		try:
			node=nodes[0]
		except IndexError:
			print "VM",vm,"not found."
			sys.exit(2)
	
	return node

def cxm_create(cluster, vm, options):
	"""Start the specified vm.

	If options.node is not given, vm is started where an autostart link is found.
	"""

	# Check if vm is't already started somewhere
	nodes=cluster.search_vm_started(vm)
	if(len(nodes)>0):
		print "** Nothing to do :"
		print "** " + vm + " is running on "+", ".join([n.get_hostname() for n in nodes])
		sys.exit(2)

	if options.node:
		node=cluster.get_node(options.node)
	else:
		nodes=cluster.search_vm_autostart(vm)
		if(len(nodes)>1):
			print "** Warning: duplicates autostart links found on :"
			print "**  ->  " + ", ".join([n.get_hostname() for n in nodes])
			print "** Don't know where to start the VM (correct the links or use --force-node)."
			sys.exit(2)

		try:
			node=nodes[0]
		except IndexError:
			node=cluster.get_local_node()
			print "** Warning: no autostart link found. Starting VM here."
	
	if not core.QUIET : print "Starting",vm,"on",node.get_hostname(),"..."
	cluster.start_vm(node,vm,options.console)

def cxm_migrate(cluster, vm, dest, options):
	"""Live migrate the vm to the specified dest.

	If options.node is not given, search for the vm over the cluster.
	"""
	node=select_node_by_vm(cluster, vm, options)

	src_hostname=node.get_hostname()
	if not core.QUIET : print "Migrating",vm,"from",src_hostname,"to",dest,"..."
	cluster.migrate(vm, src_hostname, dest)

def cxm_shutdown(cluster, vm, options):
	"""Shutdown the specified VM. 

	If options.node is not given, search for the vm over the cluster.
	"""

	node=select_node_by_vm(cluster, vm, options)

	if not core.QUIET : print "Shutting down",vm,"on",node.get_hostname(),"..."
	node.shutdown(vm)

def cxm_console(cluster, vm, options):
	"""Attach local console to the given VM."""
	
	node=select_node_by_vm(cluster, vm, options)

	if node.is_local_node():
		node.get_vm(vm).attach_console()
	else:
		print "** ERROR: Cannot attach console on a remote host !"
		print "** You should try on", node.get_hostname()

def cxm_activate(cluster, vm, options):	# Exclusive activation
	"""Activate the logicals volumes of the specified VM.

	If options.node is not given, activate on the local node and deactivate on all others.
	"""
	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()
	
	if not core.QUIET : print "Activating LVs of",vm,"on",node.get_hostname(),"..."
	cluster.activate_vm(node,vm)

def cxm_deactivate(cluster, vm, options):
	"""Deactivate the logicals volumes of the specified VM.

	If options.node is not given, use local node.
	"""
	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.QUIET : print "Deactivating LVs of",vm,"on",node.get_hostname(),"..."
	node.deactivate_lv(vm)

def cxm_infos(cluster):
	"""Print the status of the cluster."""
	print '%-40s %3s  %3s  %8s  %4s' % ("Node name","VM", "IRQ","Free-RAM","Load")
	for node in cluster.get_nodes():
		metrics=node.get_metrics()
		print '%-40s %3d  %3d  %8d  %3d%%' % (node.get_hostname(),node.get_vm_started(),
			metrics.get_used_irq(),metrics.get_free_ram(),metrics.get_load())

def cxm_search(cluster,vm):
	"""Search the specified vm on the cluster."""
	if not core.QUIET : print "Searching", vm, "..."

	# Search started vm
	found=cluster.search_vm_started(vm)
	if(len(found)==0):
		print " -> VM is not started."
	else:
		if(len(found)>1):
			print "** WARNING : MULTIPLES INSTANCES FOUND !!!"
		print " -> Instance found on: " + ", ".join([n.get_hostname() for n in found])

	# Search autostart enabled
	found=cluster.search_vm_autostart(vm)
	if(len(found)==0):
		print " -> Autostart link not found."
	else:
		print " -> Autostart link found on: " + ", ".join([n.get_hostname() for n in found])
		
def cxm_list(cluster, options):
	"""List started VM on all nodes."""
	if options.node:
		nodes=[cluster.get_node(options.node)]
	else:
		nodes=cluster.get_nodes()
	
	for node in nodes:
		print "\nOn", node.get_hostname(), ":"
		if not core.QUIET: 
			print "-----" + "-" * len(node.get_hostname())
			print '\n    %-40s %4s  %5s  %6s' % ("Name","Mem", "VCPUs","State")
		for vm in node.get_vms():
			print '    %-40s %4d  %5d  %6s' % (vm.name, vm.ram, vm.vcpu, vm.state)
		
def cxm_check(cluster):
	"""Run a cluster-wide sanity check."""
	if not cluster.check():
		print " -> Errors has been found. You should correct it."
		sys.exit(1)

def cxm_start(cluster, options):
	"""Initialize the cluster at startup."""

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.QUIET : print "Initialize cluster on",node.get_hostname(),"..."
	node.deactivate_all_lv()

def cxm_eject(cluster, options):
	"""Eject local node from cluster."""

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.QUIET : print "Ejecting all running VM from",node.get_hostname(),"..."
	cluster.emergency_eject(node)

def main():
	"""Run cxm command line interface."""
	parser = OptionParser(version="%prog "+core.VERSION)
	parser.add_option("-d", "--debug",
					  action="store_true", dest="debug", default=False,
					  help="Enable debug mode")
	parser.add_option("-f", "--force-node", dest="node", metavar="hostname", default=None,
					  help="Specify the node to operate with")
	parser.add_option("-q", "--quiet",
					  action="store_true", dest="quiet", default=False,
					  help="Quiet mode: suppress extra outputs")
	parser.add_option("-s", "--use-ssh",
					  action="store_true", dest="usessh", default=False,
					  help="Use SSH instead of Xen-API")
	parser.add_option("-c", "--console",
					  action="store_true", dest="console", default=False,
					  help="Attach console to the domain as soon as it has started.")

	parser.usage = "%prog create <vm>|shutdown <vm>|migrate <vm> <dest>|search <vm>|console <vm>|activate <vm>|deactivate <vm>|infos|list|check|eject [option] "

	(options, args) = parser.parse_args()

	core.DEBUG=options.debug
	core.QUIET=options.quiet
	core.USESSH=options.usessh

	# Command-line parsing similar to 'xm'
	try:
		cluster=xencluster.XenCluster()
		atexit.register(cluster.__del__) # Workaround bug thread on exit

		if args[0].startswith("cr"):	# create
			# Start a new vm
			cxm_create(cluster,os.path.basename(args[1]),options)
		elif args[0].startswith("mi"):	# migrate
			# Live migration
			cxm_migrate(cluster, os.path.basename(args[1]), args[2], options)
		elif args[0].startswith("co"):	# console
			# Open the xen console on the vm
			cxm_console(cluster, os.path.basename(args[1]),options)
		elif args[0].startswith("ac"):	# activate
			# Activate LVs of a VM
			cxm_activate(cluster, os.path.basename(args[1]), options)
		elif args[0].startswith("de"):	# deactivate
			# Desactivate LVs of a VM
			cxm_deactivate(cluster, os.path.basename(args[1]), options)
		elif args[0].startswith("in"):	# infos
			# Display cluster infos
			cxm_infos(cluster)
		elif args[0].startswith("se"):	# search
			# Search a VM on the cluster
			cxm_search(cluster, os.path.basename(args[1]))
		elif args[0].startswith("sh"):	# shutdown
			# Cleanly shutdown the VM
			cxm_shutdown(cluster, os.path.basename(args[1]), options)
		elif args[0].startswith("li"):	# list
			# List all VM
			cxm_list(cluster, options)
		elif args[0].startswith("ch"):	# check
			# Check integrity of cluster
			cxm_check(cluster)
		elif args[0].startswith("ej"):	# eject
			# Migrate all vm to others nodes
			cxm_eject(cluster,options)
		elif args[0].startswith("start"):	# start
			# Initiate the cluster
			cxm_start(cluster, options)		# TODO a deplacer dans cxm-manager
		else:
			parser.print_help()
	except IndexError:
		parser.print_help()
		if options.debug:
			raise
	except (xencluster.ClusterError, node.ClusterNodeError), e:
		if options.debug:
			raise
		else:
			print e
			sys.exit(2)
		
	

if __name__ == "__main__":
	main()

# vim: ts=4:sw=4:ai
