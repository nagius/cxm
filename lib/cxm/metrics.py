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


import time
from xen.xm import main
import node, core, datacache
import logs as log

class Metrics:

	"""This class is used to retrieve metrics of its node and vms."""

	def __init__(self, node):
		"""Instanciate new metrics associated with the given node."""
		self.node=node
		self.server=node.server
		self._cache=datacache.DataCache()

		# Initialize cpu_cache
		self.cpu_cache={'timestamp': time.time()}

		# Initialize io_cache
		self.io_cache={'timestamp': time.time()}

	def init_cache(self):
		"""
		Initialize the cache for rate computation.

		If you don't call this function, the first call of get_vms_cpu_usage() and 
		get_vms_disk_io_rate() will return dict with zero values.
		"""
		# First call to feed cache with current value
		self.get_vms_cpu_usage(True) 
		self.get_vms_disk_io_rate()

	def __repr__(self):
		return "<Metrics Instance : "+ self.node.hostname +">"

	def get_dom_records(self, nocache=False):
		"""
		Return a dict with complete dom records from API.
		Only usefull for internal use.

		Result will be cached for 5 seconds, unless 'nocache' is True.
		"""

		def _get_dom_records():
			dom_recs = self.server.xenapi.VM.get_all_records()
			log.debug("[API]", self.node.get_hostname(), "dom_recs=", dom_recs)
			return dom_recs

		return self._cache.cache(5, nocache, _get_dom_records)

	def get_host_nr_cpus(self):
		"""Return the number (int) of CPU on the host."""
		host_record = self.server.xenapi.host.get_record(self.server.xenapi.session.get_this_host(self.server.getSession()))
		log.debug("[API]", self.node.get_hostname(), "host_record=", host_record)
		return int(host_record['cpu_configuration']['nr_cpus'])

	def get_dom0_nr_cpus(self):
		"""Return the number (int) of VCPU for the Domain-0."""
		dom0_record = self.server.xenapi.VM.get_record('00000000-0000-0000-0000-000000000000')
		log.debug("[API]", self.node.get_hostname(), "dom0_record=", dom0_record)
		return int(dom0_record['VCPUs_max'])

	def get_vms_cpu_usage(self, nocache=False):
		"""
		Return a dict with the computed CPU usage for all runing VMs.
		Result will be cached for 5 seconds, unless 'nocache' is True.

		The result is a percetage relative to one CPU (eg. 2 fully-used CPU -> 200%)
		Warning: paused VM will be reported with zero values. 

		Values are floats with 16 digit of precision (python standard's binary float)
		If you want a string with less precision, you can use "%.1f" % round(xxx).
		If you want a number with less precision, you can use the Decimal module.
		"""
		def _get_vms_cpu_usage():
			cpu=dict()

			# Get domains' infos
			doms=self.node.legacy_server.xend.domains(True)
			log.debug("[Legacy-API]", self.node.get_hostname(), "doms=", doms)

			# Timestamp used to compute CPU percentage
			timestamp=time.time()

			# Initialize result with 0 for all vm
			# This is because legacy api do not report paused vm
			for vm in self.node.get_vms(nocache): # 5s of cache is ok, this func is designed to be run every 60s
				cpu[vm.name]=0

			for dom in doms:
				dom_info=main.parse_doms_info(dom)

				try:
					# String version with one digit after dot
					# See http://stackoverflow.com/questions/56820/round-in-python-doesnt-seem-to-be-rounding-properly for reasons.
					#cpu[dom_info['name']]="%.1f" % round(
					#	(dom_info['cpu_time']-self.cpu_cache[dom_info['name']])*100/(timestamp-self.cpu_cache['timestamp']),1
					#)
					cpu[dom_info['name']]=(dom_info['cpu_time']-self.cpu_cache[dom_info['name']])*100/(timestamp-self.cpu_cache['timestamp'])

				except KeyError: # First call: return zero values
					cpu[dom_info['name']]=0
				except ZeroDivisionError:
					cpu[dom_info['name']]=0

				# In case of reboot, remove negative values
				if cpu[dom_info['name']] < 0:
					cpu[dom_info['name']]=0

				# Update cpu_cache with the new value
				self.cpu_cache[dom_info['name']]=dom_info['cpu_time']

			# Update timestamp
			self.cpu_cache['timestamp']=timestamp

			return cpu

		return self._cache.cache(5, nocache, _get_vms_cpu_usage)

	def get_vms_disk_io(self,nocache=False):
		"""
		Return a dict with disks'IO stats for all runing VMs (including Dom0) since boot. 
		Result will be cached for 5 seconds, unless 'nocache' is True.
		
		Unit: Requests
		"""
		def _get_vms_disk_io():
			dom_recs = self.get_dom_records(nocache)

			io=dict()
			for dom_rec in dom_recs.values():
				if dom_rec['power_state'] == "Halted":
					continue # Discard non instantiated vm

				# We use *_req and report Requests instead of Bytes because *_sect values are not self-consistent
				io_read=[ int(val) for val in \
					self.node.run("cat /sys/bus/xen-backend/devices/vbd-" + dom_rec['domid'] + "-*/statistics/rd_req 2>/dev/null || true").readlines() ]
				io_write=[ int(val) for val in \
					self.node.run("cat /sys/bus/xen-backend/devices/vbd-" + dom_rec['domid'] + "-*/statistics/wr_req 2>/dev/null || true").readlines() ]
				io[dom_rec['name_label']]={ 'Read': sum(io_read), 'Write': sum(io_write) }
			return io

		return self._cache.cache(5, nocache, _get_vms_disk_io)

	def get_vms_disk_io_rate(self):
		"""Return a dict with disks'IO bandwith for all runing VMs. Unit: Requests/s"""
		io_rate=dict()

		# Timestamp used to compute per second rate
		timestamp=time.time()

		io=self.get_vms_disk_io(True)
		for vm in io.keys():
			io_rate[vm]=dict()
			try:
				# Compute io rate
				io_rate[vm]['Read']=int((io[vm]['Read']-self.io_cache[vm]['Read'])/(timestamp-self.io_cache['timestamp']))
				io_rate[vm]['Write']=int((io[vm]['Write']-self.io_cache[vm]['Write'])/(timestamp-self.io_cache['timestamp']))

			except KeyError: # First call
				# Initialize io_cache with the current value
				self.io_cache[vm]={'Read': io[vm]['Read'], 'Write': io[vm]['Write']}

				# Return zero values for the first call
				io_rate[vm]['Read']=0
				io_rate[vm]['Write']=0

			except ZeroDivisionError:
				io_rate[vm]['Read']=0
				io_rate[vm]['Write']=0

			# Update io_cache with the current value
			self.io_cache[vm]['Read']=io[vm]['Read']
			self.io_cache[vm]['Write']=io[vm]['Write']

		# Update timestamp of cached values
		self.io_cache['timestamp']=timestamp

		return io_rate

	def get_vms_net_io(self, nocache=False):
		"""
		Return a dict with network IO stats for all runing VMs. Unit: Bytes
		Result will be cached for 5 seconds, unless 'nocache' is True.
		"""

		def _get_vms_net_io():
			dom_recs = self.get_dom_records(nocache)

			vif_metrics_recs = self.server.xenapi.VIF_metrics.get_all_records()
			log.debug("[API]", self.node.get_hostname(), "vif_metrics_recs=", vif_metrics_recs)

			vifs_doms_metrics=dict()
			for dom_rec in dom_recs.values():
				if dom_rec['power_state'] == "Halted":
					continue # Discard non instantiated vm

				vifs_metrics=list()
				for vif in dom_rec['VIFs']:
					vifs_metrics.append({
						'Rx': int(float(vif_metrics_recs[vif]['io_total_read_kbs'])*1024),
						'Tx': int(float(vif_metrics_recs[vif]['io_total_write_kbs'])*1024)
					})
				vifs_doms_metrics[dom_rec['name_label']]= vifs_metrics

			return vifs_doms_metrics

		return self._cache.cache(5, nocache, _get_vms_net_io)

	def get_host_net_io(self):
		"""Return a dict with network IO stats for the host. Unit: Bytes"""
		bridges=self.node.get_bridges()
		vlans=self.node.get_vlans()
		io= { 'bridges': dict(), 'vlans': dict() }

		for line in self.node.run('cat /proc/net/dev').readlines():
			stats=line.replace(':',' ').strip().split()
			if stats[0] in bridges:
				io['bridges'][stats[0]]= {'Rx': stats[1], 'Tx': stats[9]}
			if stats[0] in vlans:
				io['vlans'][stats[0]]= {'Rx': stats[1], 'Tx': stats[9]}
		return io

	def get_host_pvs_io(self):
		"""Return a dict with PVs' bandwidth stats for the host. Unit: Bytes"""
		io=dict()
		sector_size=512 # This is a world constant (for now)

		# Get list of unique pvs from vgs_map
		devices=list(set([ y for x in self.node.get_vgs_map().values() for y in x ]))

		for line in self.node.run('cat /proc/diskstats').readlines():
			stats=line.strip().split()
			if stats[2] in devices:
				"""
				Doc is in <kernel>/Documentation/iostats.txt
				Struct of file /proc/diskstats :

						Field 3 -- # of reads issued
						Field 4 -- # of reads merged
						Field 5 -- # of sectors read
						Field 6 -- # of milliseconds spent reading
						Field 7 -- # of writes completed
						Field 8 -- # of writes merged
						Field 9 -- # of sectors written
						Field 10 -- # of milliseconds spent writing
						Field 11 -- # of I/Os currently in progress
						Field 12 -- # of milliseconds spent doing I/Os
						Field 13 -- weighted # of milliseconds spent doing I/Os 
				"""
				io[stats[2]]= { 'Read': int(stats[5])*sector_size, 'Write': int(stats[9])*sector_size }

		return io

	def get_host_vgs_io(self):
		"""Return a dict with VGs' bandwidth stats for the host. Unit: Bytes"""
		io=dict()

		pvs_io=self.get_host_pvs_io()
		vgs_map=self.node.get_vgs_map()

		for vg, pvs in  vgs_map.iteritems():
			io[vg]={'Read': 0, 'Write': 0}
			for pv in pvs:
				io[vg]['Read'] += pvs_io[pv]['Read']
				io[vg]['Write'] += pvs_io[pv]['Write']

		return io

	def get_vms_record(self, nocache=False):
		"""
		Return a tree with CPU, disks'IO and network IO for all running VMs.
		Result will be cached for 5 seconds, unless 'nocache' is True.

		Units: 
			CPU: Percetage
			Disk: Requests
			Net: Bytes
		"""
		
		def _get_vms_record():
			# Fetch all datas once
			vms_cpu=self.get_vms_cpu_usage(nocache)
			vms_net_io=self.get_vms_net_io(nocache)
			vms_disk_io=self.get_vms_disk_io(nocache)

			vms_record=dict()
			for vm in vms_cpu.keys():
				vms_record[vm]=dict()
				vms_record[vm]['disk']=vms_disk_io[vm]
				vms_record[vm]['cpu']=vms_cpu[vm]
				vms_record[vm]['net']=vms_net_io[vm]

			return vms_record

		return self._cache.cache(5, nocache, _get_vms_record)

	def get_used_irq(self, nocache=False):
		"""
		Return the number of used irq on this node. Unit: integer
		Result will be cached for 5 seconds, unless 'nocache' is True.
		"""

		def _get_used_irq():
			return int(self.node.run('grep Dynamic /proc/interrupts | wc -l').read())

		return self._cache.cache(5, nocache, _get_used_irq)

	def get_free_ram(self, nocache=False):
		"""Return the amount of free ram of this node. Unit: MB"""
		return self.get_ram_infos(nocache)['free']

	def get_total_ram(self, nocache=False):
		"""Return the amount of ram of this node (including Dom0 and Hypervisor). Unit: MB"""
		return self.get_ram_infos(nocache)['total']

	def get_used_ram(self, nocache=False):
		"""Return the amount of used ram (including Dom0 and Hypervisor) of this node. Unit: MB"""
		return self.get_ram_infos(nocache)['used']

	def get_ram_infos(self, nocache=False):
		"""
		Return a dict with the free, used, and total ram of this node. Units: MB
		Result will be cached for 5 seconds, unless 'nocache' is True.
		"""

		def _get_ram_infos():
			if core.cfg['USESSH']:
				vals=map(int, self.node.run('xm info | grep -E total_memory\|free_memory | cut -d: -f 2').read().strip().split())
				ram_infos = { 'total':vals[0], 'free':vals[1], 'used':vals[0]-vals[1] }
			else:
				host_record = self.server.xenapi.host.get_record(self.server.xenapi.session.get_this_host(self.server.getSession()))
				host_metrics_record = self.server.xenapi.host_metrics.get_record(host_record["metrics"])
				log.debug("[API]", self.node.get_hostname(), "host_metrics_record=", host_metrics_record)

				total=int(host_metrics_record["memory_total"])/1024/1024
				free=int(host_metrics_record["memory_free"])/1024/1024

				ram_infos = { 'total': total, 'free':free, 'used':total-free }

			return ram_infos

		return self._cache.cache(5, nocache, _get_ram_infos)

	def get_available_ram(self, nocache=False):
		"""
		Return the amount of really available ram (for VM usage, excluding Dom0 
		and Hypervisor) of this node. Unit: MB
		Result will be cached for 5 seconds, unless 'nocache' is True.
		"""
		def _get_available_ram():
			# Get all vm running on this node
			vms = self.node.get_vms(nocache)

			# Compute amount of ram used by VMs
			used_ram = sum(map(lambda x: x.get_ram(), vms))

			# Return really available ram for VM
			return self.get_free_ram(nocache) + used_ram

		return self._cache.cache(5, nocache, _get_available_ram)

	def get_load(self):
		"""Return the load of this node.

		The load is a percentage (0-100) and computed from free RAM and free IRQs.
		"""
		MAX_IRQ=1024 # Defined by RedHat patch (bz #442736) since 2.6.18

		# Compute IRQ load
		irq_load=(self.get_used_irq()*100)/MAX_IRQ

		# Compute RAM load
		ram=self.get_ram_infos()
		ram_load=(ram['used']*100)/ram['total']

		# Return the higher
		return (irq_load<ram_load and ram_load or irq_load)

	def get_lvs_size(self, lvs):
		"""Return a dict containnig size of each specified LVs. Unit: kB"""

		if len(lvs)<=0:
			return dict() # empty return if no LV given 

		size=dict()
		for line in self.node.run("lvs -o vg_name,lv_name,lv_size --noheading --units k --nosuffix " + " ".join(lvs)).readlines():
			infos=line.strip().split()
			lv_name="/dev/" + infos[0] + "/" + infos[1]

			if lv_name in lvs:  # In case of output error, don't feed with scrappy data
				size[lv_name]=float(infos[2])

		return size

# vim: ts=4:sw=4:ai

