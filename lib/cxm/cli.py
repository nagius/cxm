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

# Note that some part of code came from xen/xm

"""
This module is the command line interface of cxm.
"""

import sys, os
from xen.xm.opts import wrap
from optparse import OptionParser
from twisted.internet import reactor, threads, defer
from twisted.internet.error import ConnectError
import core, xencluster, node
from agent import Agent


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
			raise SystemExit(2)

		try:
			node=nodes[0]
		except IndexError:
			print "VM",vm,"not found."
			raise SystemExit(2)
	
	return node

def cxm_create(cluster, options, vm):
	"""Start the specified vm.

	If options.node is not given, vm is started where an autostart link is found.
	"""
	vm=os.path.basename(vm)

	# Check if vm is't already started somewhere on the cluster
	nodes=cluster.search_vm_started(vm)
	if(len(nodes)>0):
		print "** Nothing to do :"
		print "** " + vm + " is running on "+", ".join([n.get_hostname() for n in nodes])
		raise SystemExit(2)

	# Ping check
	print "Checking if VM is already started somewhere else..."
	if cluster.get_local_node().ping(vm):
		print "** Error: got a ping response !"
		raise SystemExit(2)
	
	if options.node:
		node=cluster.get_node(options.node)
	else:
		nodes=cluster.search_vm_autostart(vm)
		if(len(nodes)>1):
			print "** Warning: duplicates autostart links found on :"
			print "**  ->  " + ", ".join([n.get_hostname() for n in nodes])
			print "** Don't know where to start the VM (correct the links or use --force-node)."
			raise SystemExit(2)

		try:
			node=nodes[0]
		except IndexError:
			node=cluster.get_local_node()
			print "** Warning: no autostart link found. Starting VM here."
	
	if not core.cfg['QUIET'] : print "Starting",vm,"on",node.get_hostname(),"..."
	cluster.start_vm(node,vm,options.console)

def cxm_migrate(cluster, options, vm, dest):
	"""Live migrate the vm to the specified dest.

	If options.node is not given, search for the vm over the cluster.
	"""

	vm=os.path.basename(vm)
	node=select_node_by_vm(cluster, vm, options)

	src_hostname=node.get_hostname()
	if not core.cfg['QUIET'] : print "Migrating",vm,"from",src_hostname,"to",dest,"..."
	cluster.migrate(vm, src_hostname, dest)

def cxm_shutdown(cluster, options, vm):
	"""Properly shutdown the specified VM. 

	If options.node is not given, search for the vm over the cluster.
	"""

	vm=os.path.basename(vm)
	node=select_node_by_vm(cluster, vm, options)

	if not core.cfg['QUIET'] : print "Shutting down",vm,"on",node.get_hostname(),"..."
	node.shutdown(vm, True)

def cxm_destroy(cluster, options, vm):
	"""Terminate the specified VM immediately. 

	If options.node is not given, search for the vm over the cluster.
	"""

	vm=os.path.basename(vm)
	node=select_node_by_vm(cluster, vm, options)

	if not core.cfg['QUIET']: 
		print "Destroying",vm,"on",node.get_hostname(),"..."
		if(raw_input("Are you really sure ? [y/N]:").upper() != "Y"):
			print "Aborded by user."
			return

	node.shutdown(vm, False)

def cxm_console(cluster, options, vm):
	"""Attach local console to the given VM."""
	
	vm=os.path.basename(vm)
	node=select_node_by_vm(cluster, vm, options)

	if node.is_local_node():
		node.get_vm(vm).attach_console()
	else:
		print "** ERROR: Cannot attach console on a remote host !"
		print "** You should try on", node.get_hostname()
		raise SystemExit(2)

def cxm_activate(cluster, options, vm):	# Exclusive activation
	"""Activate the logicals volumes of the specified VM.

	If options.node is not given, activate on the local node and deactivate on all others.
	"""
	vm=os.path.basename(vm)

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()
	
	if not core.cfg['QUIET'] : print "Activating LVs of",vm,"on",node.get_hostname(),"..."
	cluster.activate_vm(node,vm)

def cxm_deactivate(cluster, options, vm):
	"""Deactivate the logicals volumes of the specified VM.

	If options.node is not given, use local node.
	"""
	vm=os.path.basename(vm)

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.cfg['QUIET'] : print "Deactivating LVs of",vm,"on",node.get_hostname(),"..."
	node.deactivate_lv(vm)

def cxm_infos(cluster, options):
	"""Print the status of the cluster."""
	def fail(reason):
		if options.debug:
			reason.printTraceback()
		else:
			print >>sys.stderr, "Error:", reason.getErrorMessage()

	def printTotals(results):
		for success, result in results:
			if not success:
				raise result

		vm=results[0][1]
		ram=sum(results[1][1]['free'])
		load=results[2][1]
		print '=' * 65
		print '%-40s %3d    -  %8d  %3d%%' % ('Total :', vm, ram, load)

	def getTotals(result):
		d1=cluster.get_vm_started()
		d2=cluster.get_ram_details()
		d3=cluster.get_load()

		dl=defer.DeferredList([d1,d2,d3])
		dl.addCallback(printTotals)
		return dl

	def printNodeMetrics(node):
		metrics=node.get_metrics()
		print '%-40s %3d  %3d  %8d  %3d%%' % (node.get_hostname(),node.get_vm_started(),
			metrics.get_used_irq(),metrics.get_free_ram(),metrics.get_load())

	if not core.cfg['QUIET']:
		print '\n%-40s %3s  %3s  %8s  %4s' % ("Node name","VM", "IRQ","Free-RAM","Load")
		print '=' * 65

	ds=list()
	for node in cluster.get_nodes():
		d=threads.deferToThread(printNodeMetrics, node)
		d.addErrback(fail)
		ds.append(d)

	dl=defer.DeferredList(ds)
	if not core.cfg['QUIET']:
		dl.addCallback(getTotals)

	return dl

def cxm_search(cluster, options, vm):
	"""Search the specified vm on the cluster."""

	# Strip vm name
	vm=os.path.basename(vm)

	try:
		names = cluster.get_local_node().get_possible_vm_names(vm)
		vm=names[0] # Should have at least one value, if not, it's a ShellError

		if(len(names)>1):
			print "Possible names are %s: be more specific." % (", ".join(names))
			return
	except node.ShellError, IndexError:
		print "** WARNING: configuration file not found for %s" % (vm)
	
	if not core.cfg['QUIET'] : print "Searching", vm, "..."

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

	def getList(node):
		if core.cfg['QUIET']: 
			msg = ""
			for vm in sorted(node.get_vms(),key=lambda x: x.name):
				msg += vm.name + "\n"
		else:
			msg = "\nOn %s :\n" % (node.get_hostname())
			msg += "-----" + "-" * len(node.get_hostname()) + '\n'
			msg += '\n    %-40s %4s  %5s  %6s\n' % ("Name","Mem", "VCPUs","State")
			for vm in sorted(node.get_vms(),key=lambda x: x.name):
				msg += '    %-40s %4d  %5d  %6s\n' % (vm.name, vm.ram, vm.vcpu, vm.state)

		return msg

	def printList(results):
		for success, result in results:
			if success:
				print result, # No carriage return
			else:
				if options.debug:
					result.printTraceback()
				else:
					print >>sys.stderr, "Error:", result.getErrorMessage()
				
	if options.node:
		nodes=[cluster.get_node(options.node)]
	else:
		nodes=cluster.get_nodes()

	ds=list()
	for node in nodes:
		d=threads.deferToThread(getList, node)
		ds.append(d)

	dl=defer.DeferredList(ds, consumeErrors=True)
	dl.addCallback(printList)
	return dl
		
def cxm_check(cluster, options):
	"""Run a cluster-wide sanity check."""
	if not cluster.check():
		print " -> Errors has been found. You should correct it."
		raise SystemExit(2)

def cxm_init(cluster, options):
	"""Initialize the cluster at startup."""

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.cfg['QUIET'] : print "Initialize cluster on",node.get_hostname(),"..."
	node.deactivate_all_lv()

def cxm_eject(cluster, options):
	"""Eject local node from cluster."""

	if options.node:
		node=cluster.get_node(options.node)
	else:
		node=cluster.get_local_node()

	if not core.cfg['QUIET'] : print "Ejecting all running VM from",node.get_hostname(),"..."
	cluster.emergency_eject(node)

def cxm_fence(cluster, options, node_name):
	"""Fence node from cluster."""

	def fence(result):
		cluster.get_local_node().fence(node_name)
		if not core.cfg['QUIET']: 
			print "Node", node_name, "successfully fenced."

	# Flag use to kill node if it belong to the cluster
	in_cluster=True

	if not core.cfg['QUIET']: print "Fencing", node_name ,"..."

	try:
		node=cluster.get_node(node_name)
		vms=node.get_vms_names()
		if(len(vms)>0):
			print "** WARNING : Some VM are running on this node :"
			print "**  ->  " + ", ".join(vms)
	except xencluster.NotInClusterError:
		if not core.cfg['QUIET']: print "Node not found in cluster."
		in_cluster=False

	# No confirm if quiet is on.
	if not core.cfg['QUIET']: 
		if(raw_input("Are you really sure ? [y/N]:").upper() != "Y"):
			print "Aborded by user."
			return

	if in_cluster:
		# Remove node from cluster (kill) before fencing it to avoid failover
		agent=Agent()
		d=agent.kill(node_name)
		# Fence only in case of kill success, that way, you can't fence master
		d.addCallback(fence)
		return d
	else:
		fence(None)

def cxm_loadbalance(cluster, options):
	"""Trigger the loadbalancer."""

	if not core.cfg['QUIET'] : print "Starting loadbalancer..."
	cluster.loadbalance()


# Command line parsing
##########################################################

def get_parser():
	"""Parse command line options and return an OptionParser object """

	parser = OptionParser(version="%prog "+core.get_api_version())
	parser.add_option("-d", "--debug",
					  action="store_true", dest="debug", default=core.cfg['API_DEBUG'],
					  help="Enable debug mode")
	parser.add_option("-f", "--force-node", dest="node", metavar="hostname", default=None,
					  help="Specify the node to operate with")
	parser.add_option("-q", "--quiet",
					  action="store_true", dest="quiet", default=core.cfg['QUIET'],
					  help="Quiet mode: suppress extra outputs")
	parser.add_option("-n", "--no-refresh",
					  action="store_true", dest="norefresh", default=core.cfg['NOREFRESH'],
					  help="Don't refresh LVM metadatas (DANGEROUS)")
	parser.add_option("-s", "--use-ssh",
					  action="store_true", dest="usessh", default=core.cfg['USESSH'],
					  help="Use SSH instead of Xen-API")
	parser.add_option("-c", "--console",
					  action="store_true", dest="console", default=False,
					  help="Attach console to the domain as soon as it has started.")

	parser.usage = "%prog <subcommand> [args] [options]\n\n"
	parser.usage += get_help()
	
	parser.epilog = "For more help on 'cxm' see the cxm(1) man page."

	return parser


commands = {
    "infos": cxm_infos,
    "list": cxm_list,
    "create": cxm_create,
    "shutdown": cxm_shutdown,
    "destroy": cxm_destroy,
    "migrate": cxm_migrate,
    "loadbalance": cxm_loadbalance,
    "search": cxm_search,
    "console": cxm_console,
    "activate": cxm_activate,
    "deactivate": cxm_deactivate,
    "check": cxm_check,
    "eject": cxm_eject,
    "fence": cxm_fence,
    "init": cxm_init,
}

# Help strings are indexed by subcommand name in this way:
# 'subcommand': (argstring, description)
SUBCOMMAND_HELP = {
	'infos'			: ('', 
		'Show the state of the cluster.',
		'Also print each active node and their load.'),
	'list'			: ('', 
		'Display the list of started VM for eath nodes.',
		'If --force-node is given, show only or the specified node.'),
	'create'		: ('<fqdn>', 
		'Start the virtual machine.',
		'If --force-node is not given, the vm will be starting on the node holding the ’auto’ symlink.'),
	'shutdown'		: ('<fqdn>', 
		'Shutdown the virtual machine.',
		'If --force-node is not given, the vm will be search on the cluster.'),
	'destroy'		: ('<fqdn>', 
		'Immediately terminate the virtual machine.',
		'If --force-node is not given, the vm will be search on the cluster.'),
	'migrate'		: ('<fqdn> <dest_node>', 
		'Live migrate the virtual machine.',
		'If --force-node is not given, the vm will be search on the cluster.'),
	'loadbalance'	: ('', 
		'Run the loadbalancer to equilibrate load.'),
	'search'		: ('<fqdn>', 
		'Search the cluster for the VM. You can use globbing to match vm name.',
		'’auto’ symlinks founds are also reported.'),
	'console'		: ('<fqdn>', 
		'Attach console to the virtual machine.',
		'This command work only on localhost.'),
	'activate'		: ('<fqdn>', 
		'Activate all the Logicals Volumes of the VM.',
		'If --force-node is not given, operation is done on localhost.'),
	'deactivate'	: ('<fqdn>', 
		'Dectivate all the Logicals Volumes of the VM.',
		'If --force-node is not given, operation is done on localhost.'),
	'check'			: ('', 
		'Perform a sanity check of the cluster.',
		'Miss-activation or missing VM are reported.'),
	'eject'			: ('', 
		'Migrate all running VM on this node to others nodes.'),
	'fence'			: ('<node>', 
		'Fence the specified node from the cluster.',
		'If VM are running on this node, they will be killed.'),
}


def get_help(cmd=None):
	"""Return the detailled help message, for all subcommands if no one is specified."""

	def wrapped_help(command):
		wrapped_desc = wrap(SUBCOMMAND_HELP[command][1], 50)
		help = ' %-28s %-50s\n' % (command+" "+SUBCOMMAND_HELP[command][0], wrapped_desc[0])
		for line in wrapped_desc[1:]:
			help +=' ' * 30 + line+'\n'
		return help

	if cmd:
		if not SUBCOMMAND_HELP.has_key(cmd):
			for fc in SUBCOMMAND_HELP.keys():
				if fc[:len(cmd)] == cmd:
					cmd = fc
					break

		try:
			return wrapped_help(cmd)
		except KeyError:
			print >>sys.stderr, "Unknown subcommand:", cmd
			return ""
	else:
		help = 'cxm full list of subcommands:\n\n'

		for command in commands:
			try:
				help += wrapped_help(command)
			except KeyError:
				continue

	return help

def cxm_lookup_cmd(cmd):
	"""Return the function associated with the given subcommand."""

	if commands.has_key(cmd):
		return commands[cmd] 
	elif cmd == 'help':
		get_parser().print_help()
		sys.exit(0)
	else:
        # simulate getopt's prefix matching behaviour
		if len(cmd) > 1:
			same_prefix_cmds = [commands[c] for c in commands.keys() if c[:len(cmd)] == cmd]
			# only execute if there is only 1 match
			if len(same_prefix_cmds) == 1:
				return same_prefix_cmds[0]
		return None

def run():
	"""Run cxm command line interface."""

	# Parse command line
	parser=get_parser()
	(options, args) = parser.parse_args()

	def syntax_error(msg):
		print >>sys.stderr, "Syntax error:", msg
		parser.print_help()
		sys.exit(3)

	# Check args
	if(len(args)<1):
		syntax_error("Missing argument.")

	# Override default behavior
	core.cfg['API_DEBUG']=options.debug
	core.cfg['QUIET']=options.quiet
	core.cfg['USESSH']=options.usessh
	core.cfg['NOREFRESH']=options.norefresh

	# Get the subcommand
	cmd = cxm_lookup_cmd(args[0])

	def fail(reason):
		# Handle exit code
		if reason.check(SystemExit):
			rc=int(reason.getErrorMessage())
		else:
			rc=1
			if options.debug:
				reason.printTraceback()
			else:
				if reason.check(ConnectError):
					print "Can't contact cxmd. Is daemon running ?"
				else:
					print >>sys.stderr, "Error:", reason.getErrorMessage()
	
		# Check argument length according to subcommand
		if reason.check(TypeError):
			print "Usage :"
			print get_help(args[0]),
			rc=3 

		reactor.addSystemEventTrigger('after', 'shutdown', os._exit, rc)
		if not reactor._stopped:
			reactor.stop()

	def runCmd(result):
		# result is a cluster instance
		d=defer.maybeDeferred(cmd, result, options, *args[1::])
		d.addCallback(lambda _: result.disconnect())
		return d

	def getCluster(result):
		# result is the list of nodes
		d=xencluster.XenCluster.getDeferInstance(result)
		d.addCallback(runCmd)
		d.addCallback(lambda _: reactor.stop())
		d.addErrback(fail)

	def checkState(result):
		if result['state']=="panic":
			print """
                ** 
              ******
             ***  ***
            ***    ***        
           ***  **  ***                   WARNING    
          ***   **   *** 
         ***    **    ***          **********************
        ***     **     ***         * PANIC MODE ENGAGED *
       ***      **      ***        **********************
      ***                ***   
     ***        **        ***
    ***         **         ***          Be careful !
   ***                      ***
    **************************  
      **********************
		  """

		if result['state']=="recovery":
			print """
                ** 
              ******
             ***  ***
            ***    ***        
           ***  **  ***                    WARNING    
          ***   **   *** 
         ***    **    ***          ************************
        ***     **     ***         * RECOVERY IN PROGRESS *
       ***      **      ***        ************************
      ***                ***     
     ***        **        ***   You should watch logs and wait
    ***         **         ***    the end of process before 
   ***                      ***        doing someting.
    **************************  
      **********************
		  """

	if cmd:
		agent=Agent()

		# Get cluster state
		d=agent.getState()
		d.addCallback(checkState)
		d.addErrback(fail)

		# Get nodes list to instantiate cluster
		d=agent.getNodesList()
		d.addCallback(getCluster)
		d.addErrback(fail)

		reactor.run()
	else:
		syntax_error('Subcommand %s not found!' % args[0])

# vim: ts=4:sw=4:ai
