# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2010-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
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
import logs as log
from xen.util.blkif import blkdev_name_to_number

class VM:

	"""This class is used to access VM properties and configuration."""

	# Tis is static because it the same for all VM
	diskre = re.compile('^phy:([^,]+),([^,]+),.+')

	def __init__(self,vmname, id=-1, ram=None, vcpu=None):
		"""Instanciate a VM object, with the optional ram and vcpu metrics."""
		self.name=vmname
		self.id=id
		self.__ram=ram
		self.__vcpu=vcpu
		self.config=dict()
		self.metrics=None
		self.devices=dict()

		try:
			try:
				execfile("%s/%s" % (core.cfg['VMCONF_DIR'],vmname) ,dict(),self.config)
			except IOError:
				execfile("%s/%s.cfg" % (core.cfg['VMCONF_DIR'],vmname) ,dict(),self.config)
		except IOError:
			if not core.cfg['QUIET']:
				log.warn("Missing configuration file: %s" % (vmname))
			
		log.debug("[VM]", vmname, self.config)

		# Get devices from config file
		try:
			for disk in self.config['disk']:
				try:
					self.devices[self.diskre.search(disk).group(1)]=self.diskre.search(disk).group(2)
				except:
					if not core.cfg['QUIET']:
						log.warn("Bad disk input for %s: %s" % (self.name, disk))
		except KeyError:
			pass
		
	def __repr__(self):
		return "<VM Instance: "+ self.name +">"

	def get_lvs(self):
		"""Return the list of logicals volumes used by the vm."""
		return self.devices.keys()

	def get_device(self, lv):
		"""
		Return the device name of the specified LV, from the VM's point of view.
		Raise a KeyError if the given LV is invalid.
		"""
		return self.devices[lv]

	def get_devnum(self, lv):
		"""
		Return the device number internaly used by xen for the specified LV.
		(This is usefull for xm block-detach ...)
		Raise a KeyError if the given LV is invalid.
		"""
		return blkdev_name_to_number(self.devices[lv])[1]

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
	
	def get_metrics(self):
		return self.metrics

	def attach_console(self):
		"""Attach the local console to this vm."""
		from xen.xm import console
		console.execConsole(self.id)

	# Define accessors 
	ram = property(get_ram, set_ram)
	vcpu = property(get_vcpu, set_vcpu)
	state = property(get_state)

# vim: ts=4:sw=4:ai
