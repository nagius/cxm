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


"""This module hold the XenCluster class."""

import os, platform

import core, node, vm
from node import ClusterNodeError

class XenCluster:

	"""This class is used to perform action on the xen cluster."""

	# Actives Nodes
	nodes = dict()

	def __init__(self, nodeslist=None):
		"""Instanciate a XenCluster object and associated Nodes.

		This constructor open SSH and XenAPI connections to all actives nodes.
		It take a (string) list of node's hostname as optionnal argument, if not given, 
		the list is fetched by get_nodes_list().

		If a node is not online, this will fail with an uncatched exception from paramiko or XenAPI.
		"""
		if not core.cfg['QUIET'] : print "Loading cluster..."

		if not nodeslist:
			nodeslist=core.get_nodes_list()

		for hostname in nodeslist:
			self.nodes[hostname]=node.Node(hostname)

	def __del__(self):
		"""Close connections on exit."""
		for node in self.get_nodes():
			node.__del__()

	def get_nodes(self):
		"""Fetch the current actives nodes.

		Return a list of Node object.
		"""
		return self.nodes.values()

	def get_node(self,hostname):
		"""Return the Node object of the specified hostname.
	
		Raise a ClusterError if the given hostname is not a clusters's node.
		"""
		try:
			return self.nodes[hostname]
		except KeyError:
			raise ClusterError(ClusterError.NOT_IN_CLUSTER,hostname)

	def get_local_node(self):
		"""Return the Node object of the local node."""
		return self.nodes[platform.node()]

	def is_in_cluster(self, hostname):
		"""Return True if the specified hostname is a node of the cluser."""
		return hostname in self.nodes

	def search_vm_started(self,vmname):
		"""Search where the specified vm hostname is running.

		Return a list of Node where the VM is running.
		"""
		started=list()
		for node in self.get_nodes():
			if node.is_vm_started(vmname):
				started.append(node)

		return started

	def search_vm_autostart(self,vmname):
		"""Search where the specified vm hostname has an autostart link.

		Return a list of Node where the autostart link is present.
		"""
		enabled=list()
		for node in self.get_nodes():
			if node.is_vm_autostart_enabled(vmname):
				enabled.append(node)

		return enabled


	def activate_vm(self,selected_node,vmname):
		"""Activate all the LVM logicals volumes of the specified VM exclusively on the selected node.

		selected_node - (Node) Node where to activate the LVs
		vmname - (String) hostname of the vm

		Raise a ClusterNodeError if the VM is running.
		"""
		for node in self.get_nodes():
			if node.is_vm_started(vmname):
				raise ClusterNodeError(node.get_hostname(),ClusterNodeError.VM_RUNNING,vmname) 
			else:
				node.deactivate_lv(vmname)

		selected_node.activate_lv(vmname)
				
	def start_vm(self, node, vmname, console):
		"""Start the specified VM on the given node.

		node - (Node) Selected host
		vmname - (String) VM hostname 
		console - (boolean) Attach console to the domain
		"""

		# Resources checks
		needed_ram=vm.VM(vmname).get_ram()
		free_ram=node.metrics.get_free_ram()
		if needed_ram>free_ram:
			raise ClusterNodeError(node.get_hostname(),ClusterNodeError.NOT_ENOUGH_RAM,"need "+str(needed_ram)+"M, has "+str(free_ram)+"M.")
			# TODO start the vm on another node

		self.activate_vm(node,vmname)
		try:
			node.start_vm(vmname,console)
		except Exception, e:
			node.deactivate_lv(vmname)
			raise e

	def migrate(self, vmname, src_hostname, dst_hostname):
		"""Live migration of specified VM from src to dst.

		All params are strings.

		Raise a ClusterError if src or dst are not part of cluster.
		Raise a ClusterNodeError if vm is not started on src or already started on dst.
		"""

		# Security checks
		if not self.is_in_cluster(src_hostname):
			raise ClusterError(ClusterError.NOT_IN_CLUSTER,src_hostname)

		if not self.is_in_cluster(dst_hostname):
			raise ClusterError(ClusterError.NOT_IN_CLUSTER,dst_hostname)

		dst_node=self.get_node(dst_hostname)
		src_node=self.get_node(src_hostname)

		if not src_node.is_vm_started(vmname):
			raise ClusterNodeError(src_node.get_hostname(),ClusterNodeError.VM_NOT_RUNNING,vmname)
		
		if dst_node.is_vm_started(vmname):
			raise ClusterNodeError(dst_node.get_hostname(),ClusterNodeError.VM_RUNNING,vmname)

		# Resources checks
		used_ram=src_node.get_vm(vmname).get_ram()
		free_ram=dst_node.metrics.get_free_ram()
		if used_ram>free_ram:
			raise ClusterNodeError(dst_node.get_hostname(),ClusterNodeError.NOT_ENOUGH_RAM,"need "+str(used_ram)+"M, has "+str(free_ram)+"M.")

		# Take care of proper migration
		dst_node.activate_lv(vmname)
		src_node.migrate(vmname,dst_node)
		src_node.deactivate_lv(vmname)
		src_node.disable_vm_autostart(vmname)
		dst_node.enable_vm_autostart(vmname)
		
	def emergency_eject(self, ejected_node):
		"""Migrate all running VMs on ejected_node to the others nodes.

		Use best-fit decreasing algorithm to resolve bin packing problem.
		Need Further optimizations when cluster is nearly full.
		"""

		# Get nodes
		pool=self.get_nodes()
		pool.remove(ejected_node)

		# Sort VMs to be ejected by used ram
		vms=ejected_node.get_vms()
		vms.sort(key=lambda x: x.get_ram(), reverse=True)
		
		failed=list()
		for vm in vms:
			selected_node=None
	
			# Sort nodes by free ram
			pool.sort(key=lambda x: x.metrics.get_free_ram())
			for node in pool:
				if node.metrics.get_free_ram() >= vm.get_ram():
					selected_node=node
					break # Select first node with enough space

			if selected_node is None:
				failed.append(vm) # Not enough room for this one
				continue  # Next !

			if not core.cfg['QUIET']: print "Migrating",vm.name,"to",selected_node.get_hostname()
			self.migrate(vm.name,ejected_node.get_hostname(),selected_node.get_hostname())

		if len(failed)>0:
			raise ClusterNodeError(ejected_node.get_hostname(),ClusterNodeError.NOT_ENOUGH_RAM,"Cannot migrate "+", ".join([vm.name for vm in failed]))
	
	def check(self):
		"""Perform a sanity check of the cluster.

		Return a corresponding exit code (0=sucess, 0!=error)
		"""
		if not core.cfg['QUIET']: print "Checking for duplicate VM..."
		safe=True

		# Get cluster wide VM list
		vm_by_node=dict()
		for node in self.get_nodes():
			vm_by_node[node.get_hostname()]=node.get_vms()
	
		if core.cfg['DEBUG']: print "DEBUG vm_by_node=",vm_by_node
	
		# Invert key/value of the dict
		node_by_vm=dict()
		for node, vms in vm_by_node.items():
			for vm in vms:
				try:
					node_by_vm[vm.name].append(node)
				except KeyError:
					node_by_vm[vm.name]=[node]

		if core.cfg['DEBUG']: print "DEBUG node_by_vm =",node_by_vm

		# Check duplicate VM
		for vm, nodes in node_by_vm.items():
			if len(nodes)>1:
				print " ** WARNING : " + vm + " is running on " + " and ".join(nodes)
				safe=False

		# Other checks
		for node in self.get_nodes():
			# Check (non)activation of LVs
			if not node.check_lvs():
				safe=False

			# Check autostart link
			if not node.check_autostart():
				safe=False
				
		return safe

class ClusterError(Exception):

	"""This class is used to raise specials errors relatives to the cluster."""

	# Error codes list
	NOT_IN_CLUSTER=2

	def __init__(self, type, value=""):
		self.type=type
		self.value=value

	def __str__(self):
		if(self.type==self.NOT_IN_CLUSTER):
			msg = "Node "+ self.value + " is not a cluster's member."
		else:
			msg = "Unknown error."
		return "\nCluster error : " + msg



if __name__ == "__main__":
	"""Main is used to run test case."""
	pass


# vim: ts=4:sw=4:ai
