#!/usr/bin/python

# cxm - Clustered Xen Management API and tools
# Copyleft 2010 - Nicolas AGIUS <nagius@astek.fr>

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

import cxm.core, cxm.loadbalancer
import unittest



class LoadBalancerTests(unittest.TestCase):


	def setUp(self):
		self.vm_metrics = {
			'vm1': { 'io':120 , 'cpu':10 , 'ram':1024 },
			'vm2': { 'io':100 , 'cpu':20 , 'ram':256 }, 
			'vm3': { 'io':900 , 'cpu':10 , 'ram':512 },
			'vm4': { 'io':0 , 'cpu':0 , 'ram':1024 },
			'vm5': { 'io':90 , 'cpu':0 , 'ram':512 },
			'vm6': { 'io':0 , 'cpu':20 , 'ram':2048 },
		}
		state = {
			'node1': ['vm1'],
			'node2': ['vm2','vm3','vm4'],
			'node3': ['vm5','vm6'],
		}
		self.lb=cxm.loadbalancer.LoadBalancer(state)

	def test_set_metrics(self):
		val=82.262661852077585

		self.lb.set_metrics(self.vm_metrics,{})
		self.assertEquals(self.lb.root.score,val)
	
	def test_create_layer(self):
		node_metrics = {
			'node1': { 'ram' : 4096 },
			'node2': { 'ram' : 4096 },
			'node3': { 'ram' : 3000 },
		}
		sol={0: [cxm.loadbalancer.Solution({'node1': ['vm1'], 'node3': ['vm5', 'vm6'], 'node2': ['vm2', 'vm3', 'vm4']})],
		 1: [cxm.loadbalancer.Solution({'node1': [], 'node3': ['vm5', 'vm6'], 'node2': ['vm2', 'vm3', 'vm4', 'vm1']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1', 'vm5'], 'node3': ['vm6'], 'node2': ['vm2', 'vm3', 'vm4']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1'], 'node3': ['vm6'], 'node2': ['vm2', 'vm3', 'vm4', 'vm5']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1', 'vm6'], 'node3': ['vm5'], 'node2': ['vm2', 'vm3', 'vm4']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1'], 'node3': ['vm5'], 'node2': ['vm2', 'vm3', 'vm4', 'vm6']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1', 'vm2'], 'node3': ['vm5', 'vm6'], 'node2': ['vm3', 'vm4']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1'], 'node3': ['vm5', 'vm6', 'vm2'], 'node2': ['vm3', 'vm4']}),
			 cxm.loadbalancer.Solution({'node1': ['vm1', 'vm3'], 'node3': ['vm5', 'vm6'], 'node2': ['vm2', 'vm4']})]}
		
		map(lambda x: x.compute_score(self.vm_metrics),[ item for sublist in sol.values() for item in sublist ])

		self.lb.set_metrics(self.vm_metrics,node_metrics)
		self.lb.create_layer(self.lb.root,1)

		self.assertEquals(self.lb.solutions,sol)

	def test_get_solution__1mig(self):
		cxm.core.cfg['LB_MIN_GAIN']=1
		node_metrics = {
			'node1': { 'ram' : 4096 },
			'node2': { 'ram' : 4096 },
			'node3': { 'ram' : 3000 },
		}
		
		self.lb.set_metrics(self.vm_metrics,node_metrics)
		val=cxm.loadbalancer.Solution({'node1': ['vm1', 'vm2'], 'node3': ['vm5', 'vm6'], 'node2': ['vm3', 'vm4']})
		val.compute_score(self.vm_metrics)
		
		sol=self.lb.get_solution()
		self.assertEquals(sol,val)
		self.assertEquals(len(sol.get_path()),1)

	def test_get_solution__2mig(self):
		cxm.core.cfg['LB_MIN_GAIN']=10
		cxm.core.cfg['LB_MAX_LAYER']=50
		node_metrics = {
			'node1': { 'ram' : 4096 },
			'node2': { 'ram' : 4096 },
			'node3': { 'ram' : 3000 },
		}
		
		self.lb.set_metrics(self.vm_metrics,node_metrics)
		val=cxm.loadbalancer.Solution({'node1': ['vm1', 'vm6'], 'node3': ['vm5', 'vm2'], 'node2': ['vm3', 'vm4']})
		val.compute_score(self.vm_metrics)
		
		sol=self.lb.get_solution()
		self.assertEquals(sol,val)
		self.assertEquals(len(sol.get_path()),2)

	def test_get_solution__none(self):
		cxm.core.cfg['LB_MIN_GAIN']=50
		cxm.core.cfg['LB_MAX_LAYER']=50
		node_metrics = {
			'node1': { 'ram' : 4096 },
			'node2': { 'ram' : 4096 },
			'node3': { 'ram' : 3000 },
		}
		
		self.lb.set_metrics(self.vm_metrics,node_metrics)
		
		sol=self.lb.get_solution()
		self.assertEquals(sol,None)
	

class SolutionTests(unittest.TestCase):

	def setUp(self):
		cxm.core.cfg['LB_MAX_VM_PER_NODE']=10
		state = {
			'node1': ['vm1'],
			'node2': ['vm2','vm3'],
		}
	
		self.s=cxm.loadbalancer.Solution(state)	

	def test_compute_score(self):
		val=96.280427996998981
		metrics = {
                'vm1': { 'io':120, 'cpu':20},
                'vm2': { 'io':100, 'cpu':12}, 
                'vm3': { 'io':500, 'cpu':99}, 
		}

		self.s.compute_score(metrics)
		self.assertEqual(self.s.score, val)

	def test_migrate(self):
		state = {
			'node1': ['vm1','vm2'],
			'node2': ['vm3'],
		}
		path = [{'src': 'node2', 'dst': 'node1', 'vm': 'vm2'}]

		self.s.migrate('vm2','node2','node1')
		self.assertEqual(self.s.state, state)
		self.assertEqual(self.s.get_path(), path)

	def test_is_constraints_ok__True(self):
		vm_metrics = {
			'vm1': { 'ram':512 },
			'vm2': { 'ram':1024 }, 
			'vm3': { 'ram':1024 }, 
		}
		node_metrics = {
			'node1': { 'ram':2048 },
			'node2': { 'ram':2048 }, 
		}
	
		self.assertTrue(self.s.is_constraints_ok(vm_metrics, node_metrics))

	def test_is_constraints_ok__noknbvm(self):
		cxm.core.cfg['LB_MAX_VM_PER_NODE']=1
		vm_metrics = {
			'vm1': { 'ram':512 },
			'vm2': { 'ram':1024 }, 
			'vm3': { 'ram':1024 }, 
		}
		node_metrics = {
			'node1': { 'ram':2048 },
			'node2': { 'ram':2048 }, 
		}
	
		self.assertFalse(self.s.is_constraints_ok(vm_metrics, node_metrics))

	def test_is_constraints_ok__nokram(self):
		vm_metrics = {
			'vm1': { 'ram':512 },
			'vm2': { 'ram':1024 }, 
			'vm3': { 'ram':1024 }, 
		}
		node_metrics = {
			'node1': { 'ram':2048 },
			'node2': { 'ram':2000 }, 
		}
	
		self.assertFalse(self.s.is_constraints_ok(vm_metrics, node_metrics))

	def test_eq(self):
		state = {
			'node1': ['vm3','vm2'],
			'node2': ['vm1'],
		}

		self.assertEqual(self.s,cxm.loadbalancer.Solution(state))
	

if __name__ == "__main__":
	unittest.main()   

# vim: ts=4:sw=4:ai
