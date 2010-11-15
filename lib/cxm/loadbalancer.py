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


import math
from copy import deepcopy, copy
import core


class LoadBalancer:
	"""
	This class is a loadbalancer used to distribute load on a cluster doing live-migrations.

	It use an heuristic, based on it's own layered algorithm and inspired by tabu search, to 
	resolve this multi-objectives bin-packing problem. It's classified as a partial-exact 
	algorithm (can be see like an approximate algo)
	The goal is to seek for the first better solution that satisfy all constraints.

	Example of usage :

	lb=LoadBalancer(current_state)
	lb.set_metrics(vm_metrics, node_metrics) 
	solution=lb.get_solution()
	print solution.get_path()
	"""

	def __init__(self, current_state):
		"""
		Instanciate a new LoadBalancer.

		current_state is a dict containing lists of vm (as strings), on each node.
		Example:
		current_state = {
				'node1': ['vm1'],
				'node3': ['vm5','vm6'],
				}

		"""
		self.solutions = {}		# Hold the solutions' tree (a bit flattened, yep)
		self.root = Solution(current_state)  # Current solution, root of the solutions' tree

		# Set the initial state : layer 0
		self.solutions[0] = [self.root]


	def set_metrics(self, vm_metrics, node_metrics):
		"""
		Initialize a loadbalancer with metrics informations.

		Example of metrics' dict:
		vm_metrics = {
				'vm1': { 'io':120  , 'cpu':10 , 'ram':1024 },
				'vm2': { 'io':1280 , 'cpu':23 , 'ram':512 },
				'vm3': { 'io':10   , 'cpu':0  , 'ram':128 },
			}
		
		node_metrics = {
			   'node1': { 'ram' : 1024 },
			   'node2': { 'ram' : 2048 },
		   }
		"""

		self.vm_metrics=vm_metrics
		self.node_metrics=node_metrics
		
		# Finalize initialisation
		self.root.compute_score(self.vm_metrics)

		if core.cfg['DEBUG']: 
			print "DEBUG [LB]: vm_metrics=",vm_metrics
			print "DEBUG [LB]: node_metrics=",node_metrics
			print "DEBUG [LB]: current_state=",self.root


	def create_layer(self, root, layer):
		"""Create a new layer with all possible solutions.

		root is the starting solution used to find next solutions.
		layer is the number of this layer :
			Layer 0 is the current situation
			Layer 1 means solutions with one migration
			Layer n means solutions with n migrations
		"""

		# Tabu list: already found solutions
		tabu = [ item for sublist in self.solutions.values() for item in sublist ]
		
		for node in root.state.keys():
			target_nodes = root.state.keys()
			target_nodes.remove(node) # In-place migration useless
			
			for vm in root.state[node]:
				for target in target_nodes:
					# Create a possible solution
					solution = Solution(root.state)
					solution.set_path(root.path)
					solution.migrate(vm, node, target)
					solution.compute_score(self.vm_metrics)

					# Don't keep existing or permutable solutions.
					#   No tabu search in current layer's solutions because permutations
					#   are not possible in the same layer.
					if solution in tabu:
						continue

					# Add this solution to the pool if constraints are respected
					if solution.is_constraints_ok(self.vm_metrics, self.node_metrics):
						self.solutions.setdefault(layer,[]).append(solution)
					
	def get_solution(self):
		"""Get the best solution at the minimal cost.

		Return the choosen solution, or None if there's no solution.
		"""
		layer=1 # Layer 0 is filled with the initial solution
		while layer <= core.cfg['LB_MAX_LAYER']:
			# Create current layer's solutions from previous layer
			for previous_solution in self.solutions[layer-1]:
				self.create_layer(previous_solution, layer)

			try:
				if not len(self.solutions[layer]) > 0:
					return None
			except KeyError:
				return None # No more solutions, giving up.

			# Get the best solution of this layer
			#   best_solution = min(self.solutions[layer],key=lambda x: x.score) # Only with python >= 2.5
			#   with python 2.4, need to:
			# Sort the solutions by score, the better is the lower, and take the first
			self.solutions[layer].sort(key=lambda x: x.score)
			best_solution = self.solutions[layer][0]

			# Compare initial solution to the best solution of this layer
			if best_solution.score < self.root.score:
				if core.cfg['DEBUG']: print "DEBUG [LB]: Found %s" % best_solution

				# Compute the gain (in percetage) of this solution
				gain = ((self.root.score-best_solution.score)*100)/self.root.score
				if gain >= core.cfg['LB_MIN_GAIN']:
					if core.cfg['DEBUG']: print "DEBUG [LB]: Pickup this one, migration plan: %s" % best_solution.path
					return best_solution
			
			layer+=1 # No better solution found in this layer, going a step further.


		return None # No better solution found at all, giving up.

class Solution:
	"""This class represent a solution for the loadbalancer, ie. a state of the cluster and a path to reach it.

	The path is the succession of needed vm's migration from the current state to the state of this solution.
	"""

	def __init__(self, state):
		"""Instanciate a new solution with the given state.

		state is a dict containing lists of vm (as strings), on each node.
		Example :
			state = {
				'node1': ['vm1'],
				'node3': ['vm5','vm6'],
				}

		"""
		# TODO: optimize ram usage with only 2 level deepcopy
		self.state = deepcopy(state) 	# State of this solution (which vm is on which node)
		self.score = None  				# Should be a float for precision
		self.path = [] 					# Complete path (details of migrations) from the start solution to this solution

	def compute_score(self,metrics):
		"""Compute the score of this solution, from the given metrics.

		This score is a float used to compare the quality of this solution; the better is the lower.
		It take in account CPU and IO usage of all vm. 

		metrics is a dict containing informations about cpu and io used by VMs.
		Example:
			metrics = {
				'vm1': { 'io':120, 'cpu':0},
				'vm2': { 'io':120, 'cpu':0}, 
				}
		"""
		# Compute IO/CPU sums of each vm, on each node
		IOs = [ sum([ metrics[vm]['io'] for vm in self.state[node] ]) for node in self.state ]
		CPUs = [ sum([ metrics[vm]['cpu'] for vm in self.state[node] ]) for node in self.state ]

		# Compute load deviation between the node with the highest load and the node with the lower load.
		# delta_* are percentages relatives to the current cluster (total) load.
		try:
			delta_IOs= float((max(IOs)-min(IOs))*100)/sum(IOs)
		except ZeroDivisionError:
			delta_IOs=0

		try:
			delta_CPUs= float((max(CPUs)-min(CPUs))*100)/sum(CPUs)
		except ZeroDivisionError:
			delta_CPUs=0

		# The score is the Euclidean distance between the symbolic point (delta_IO,delta_CPU) 
		# reflecting the solution, and the origin (0,0).
		#
		# (delta IO)
		#      100% |
		#           |
		#           |   + (score)
		#           |
		#         0 |_ _ _ _ _ 
		#	        0         100% (delta CPU)
		#
		# Within a cartesian plane, the Euclidean distance between two points is given by this formula:
		#        ________________________
		# AB = \/ ( Xb-Xa )² + ( Yb-Ya )²
		#
		self.score=math.sqrt(math.pow(delta_IOs,2)+math.pow(delta_CPUs,2))
	
	def set_path(self,path):
		"""Set the current path to this solution."""
		self.path=copy(path)  # Shallow copy is sufficient and avoid ram explosion

	def get_path(self):
		"""
		Return the full path from the current state to this solution.

		Returned value is a list of dicts like this:
			[{'vm':'vm1', 'src':'node1', 'dst':'node3'},
			 {'vm':'vm2', 'src':'node3', 'dst':'node2'}]
		"""
		return self.path

	def migrate(self, vm_name, source, destination):
		"""
		Update the solution to a new position.

		This change the state of this solution and update the path: the vm named 'vm_name' 
		is marked to be migrated from 'source' to 'destination'.
		"""

		self.path.append({'vm':vm_name, 'src':source, 'dst':destination})
		self.state[source].remove(vm_name)
		self.state[destination].append(vm_name)
		
	def is_constraints_ok(self, vm_metrics, node_metrics):
		"""
		Check if the builtin constraints are respected, according to the given metrics.

		For now, two constraints are checked : 
		  - The maximum number of vm per node should not exceed LB_MAX_VM_PER_NODE.
		  - Sum of vm's ram should not exceed node's ram.
		
		vm_metrics and node_metrics are dicts containing informations about ram usage.
		Units have to be the same across dicts (in MB, most in time).
		Example:
			vm_metrics = {
				'vm1': { 'ram':512 },
				'vm2': { 'ram':1024 }, 
				}
			node_metrics = {
				'node1': { 'ram':2048 },
				'node2': { 'ram':2048 }, 
				}

		Return a boolean.
		"""
		for node in self.state:
			# Constraint 1: Maximum number of vm per node
			if len(self.state[node]) > core.cfg['LB_MAX_VM_PER_NODE']:
				return False

			# Constraint 2: Sum of vm's ram is not greater than node's ram
			total_ram = sum([ vm_metrics[vm]['ram'] for vm in self.state[node] ])
			if total_ram > node_metrics[node]['ram']: 
				return False
		
		return True

	def __eq__(self, other):
		"""Compare Solution's instances by score."""
		if not isinstance(other, Solution):
			return False

		# Match permutables (and useless) solutions
		return self.score == other.score

	def __repr__(self):
		return "<Solution: state=%s,score=%s>" % (self.state, self.score)


if __name__ == "__main__":
    pass

# vim: ts=4:sw=4:ai
