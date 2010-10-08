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


"""This module hold the VM class."""

import re
import core

class VM:

	"""This class is used to access VM properties and configuration."""

	def __init__(self,vmname, id=-1, ram=None, vcpu=None):
		"""Instanciate a VM object, with the optional ram and vcpu metrics."""
		self.name=vmname
		self.id=id
		self.__ram=ram
		self.__vcpu=vcpu
		self.config=dict()
		self.metrics=None

		execfile("%s/%s" % (core.cfg['VMCONF_DIR'],vmname) ,dict(),self.config)
		if core.DEBUG: print "DEBUG config",vmname,"=",self.config
		
	def __repr__(self):
		return "<VM Instance: "+ self.name +">"

	def get_lvs(self):
		"""Return the list of logicals volumes used by the vm."""
		lvs=list()
		for disk in self.config['disk']:
			regex = re.compile('^phy:([^,]+).*')
			try:
				lvs.append(regex.search(disk).group(1))
			except:
				pass

		return lvs

	def get_ram(self):
		"""Return the amount of ram allocated to the vm."""
		if self.__ram:
			return int(self.__ram)
		elif self.metrics:
			return int(self.metrics['memory_actual'])/1024/1024
		else:
			return self.get_start_ram()
	
	def get_start_ram(self):
		"""Return the amount of ram configured on startup."""
		return int(self.config['memory'])

	def set_ram(self,ram):
		"""Set the amount of ram allocated to the vm."""
		self.__ram=str(ram)

	def get_vcpu(self):
		"""Return the number of actives vcpu allocated to the vm."""
		if self.__vcpu:
			return int(self.__vcpu)
		else:
			return int(self.metrics['VCPUs_number'])

	def set_vcpu(self, vcpu):
		"""Set the number of vcpu allocated to the vm."""
		self.__vcpu=str(vcpu)

	def get_state(self):
		"""Return the string representing the state of the vm."""
		states = ('running', 'blocked', 'paused', 'shutdown', 'crashed', 'dying')
		if self.metrics:
			def state_on_off(state):
				if state in self.metrics['state']:
					return state[0]
				else:
					return "-"
			return "".join([state_on_off(state) for state in states])
		else:
			return "=" * len(states)

	def attach_console(self):
		"""Attach the local console to this vm."""
		from xen.xm import console
		console.execConsole(self.id)

	# Define accessors 
	ram = property(get_ram, set_ram)
	vcpu = property(get_vcpu, set_vcpu)
	state = property(get_state)




if __name__ == "__main__":
	pass

# vim: ts=4:sw=4:ai
