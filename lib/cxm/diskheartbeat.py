# -*- coding:Utf-8 -*-

# cxm - Clustered Xen Management API and tools
# Copyleft 2011-2012 - Nicolas AGIUS <nicolas.agius@lps-it.fr>
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

import sys, time, os
import core


class DiskHeartbeat(object):

	BS = 4096			# Block size
	MAX_SLOT = 16		# Maximum number of slots. File size must be at least (MAX_SLOT+1)*2*BS Bytes
						# Redhat Cluster Suite has a maximum of 16 nodes.
	MAGIC = "CXMHBv1-%s-%s" % (BS, MAX_SLOT)	# Magic number for heartbeat disk

	def __init__(self):
		# Just for checking magic number
		self._open()
		self._close()

	@staticmethod
	def format():
		f=open(core.cfg['HB_DISK'], "wb",0) # No buffer

		try:
			# Erase each slot
			f.write("\x00"*2*DiskHeartbeat.BS)
			for i in range(DiskHeartbeat.MAX_SLOT):
				f.write("\x00"*DiskHeartbeat.BS)
				f.write("0"*DiskHeartbeat.BS)

			# Set header
			f.seek(0)
			f.write(DiskHeartbeat.MAGIC)
			f.seek(DiskHeartbeat.BS)
			f.write("0"*DiskHeartbeat.BS) # Set number of node to 0
		finally:
			f.close()

	@staticmethod
	def is_in_use():
		try:
			nr_node=DiskHeartbeat().get_nr_node()
		except DiskHeartbeatError:
			return False

		return nr_node != 0
	
	def _open(self):
		self.f=open(core.cfg['HB_DISK'], "r+b",0) # No buffer
		if self.f.read(DiskHeartbeat.BS).strip("\x00") != DiskHeartbeat.MAGIC:
			self.f.close()
			raise DiskHeartbeatError("%s is not and CXM Heartbeat disk !" % (core.cfg['HB_DISK']))

	def _rewind(self):
		"""Rewind to the start of the table, just after header."""
		self.f.seek(2*DiskHeartbeat.BS) 
	
	def _close(self):
		if not self.f.closed:
			self.f.flush()
			os.fsync(self.f.fileno())
			self.f.close()
		
	def _update_nr_node(self, step):
		"""Update number of node"""
		self.f.seek(DiskHeartbeat.BS)
		nr_node=int(self.f.read(DiskHeartbeat.BS).strip("\x00"))
		nr_node += step
		if(nr_node<0):
			nr_node=0	
		
		if(nr_node>DiskHeartbeat.MAX_SLOT):
			raise DiskHeartbeatError("Maximum number of node reached !")

		self.f.seek(DiskHeartbeat.BS)
		self.f.write(("%0"+str(DiskHeartbeat.BS)+"d") % nr_node) # Right-justified integer

	def _seek_slot(self, name):
		"""Seek for this node's slot"""
		self._rewind()
		pos=0
		found=False
		while pos < DiskHeartbeat.MAX_SLOT:
			slot=self.f.read(DiskHeartbeat.BS).strip("\x00")
			if(slot == name):
				found=True
				break;
			self.f.seek(DiskHeartbeat.BS,1) # Next block (jump over timestamp)
			pos += 1

		return found

	def get_nr_node(self):
		self._open()

		try:
			self.f.seek(DiskHeartbeat.BS)
			nr_node=int(self.f.read(DiskHeartbeat.BS).strip("\x00"))
		finally:
			self._close()

		return nr_node

	def make_slot(self, name):
		self._open()
		try:
			if len(name) >= DiskHeartbeat.BS:
				raise DiskHeartbeatError("Name %s is too long for block size %s." % (name, DiskHeartbeat.BS))

			if self._seek_slot(name):
				raise DiskHeartbeatError('Slot already registered')

			self._update_nr_node(1)	

			# Seek for an empty slot
			self._rewind()
			while True:
				slot=self.f.read(DiskHeartbeat.BS).strip("\x00")
				if(len(slot)<=0):
					break;
				self.f.seek(DiskHeartbeat.BS,1) # Next block (jump over timestamp)

			# Reserve slot for this new node
			self.f.seek(-DiskHeartbeat.BS,1)
			self.f.write(name)
		finally:
			self._close()
	
	def erase_slot(self, name):
		self._open()

		try:
			if not self._seek_slot(name):
				raise DiskHeartbeatError('Slot not found')
				
			# Erase selected slot
			self.f.seek(-DiskHeartbeat.BS,1)
			self.f.write("\x00"*DiskHeartbeat.BS)
			self.f.write("0"*DiskHeartbeat.BS)

			self._update_nr_node(-1)
		finally:
			self._close()
	
	def write_ts(self, name):
		self._open()

		try:
			if not self._seek_slot(name):
				raise DiskHeartbeatError('Slot not found')

			self.f.write(("%0"+str(DiskHeartbeat.BS)+"d") % int(time.time()))
		finally:
			self._close()

	def get_ts(self, name):
		self._open()

		try:
			if not self._seek_slot(name):
				raise DiskHeartbeatError('Slot not found')

			ts=int(self.f.read(DiskHeartbeat.BS).strip("\x00"))
		finally:
			self._close()

		return ts

	def get_all_ts(self):
		ts=dict()
		self._open()
		try:
			self._rewind()
			for i in range(DiskHeartbeat.MAX_SLOT):
				name=self.f.read(DiskHeartbeat.BS).strip("\x00")
				if(len(name)<=0):
					self.f.seek(DiskHeartbeat.BS,1) # Next block (jump over timestamp)
				else:
					ts[name]=int(self.f.read(DiskHeartbeat.BS).strip("\x00"))
		finally:
			self._close()

		return ts

class DiskHeartbeatError(Exception):
	"""This class is used to raise errors relatives to the disk hearbeat system."""
	pass


# vim: ts=4:sw=4:ai 
