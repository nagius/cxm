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

"""This module hold the Node class."""

import platform, paramiko, re, time, popen2, socket, StringIO
from xen.xm import XenAPI
from xen.xm import main
from xen.util.xmlrpcclient import ServerProxy
from sets import Set

from metrics import Metrics
from vm import VM
import core


class Node:
	
	"""This class is used to perform action on a node within the xen cluster."""

	def __init__(self,hostname):
		"""Instanciate a Node object.

		This constructor open SSH and XenAPI connections to the node.
		If the node is not online, this will fail with an uncatched exception from paramiko or XenAPI.
		"""
		if not core.QUIET : print "Connecting to "+ hostname + "..."
		self.hostname=hostname

		# Open SSH channel (localhost use popen2)
		if not self.is_local_node() or core.USESSH:
			self.ssh = paramiko.SSHClient()
			self.ssh.load_system_host_keys()
			#self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			self.ssh.connect(hostname,22,'root', timeout=2)

		# Open Xen-API Session (even if USESSH is true...)
		if self.is_local_node():
			# Use unix socket on localhost
			self.server = XenAPI.Session("httpu:///var/run/xend/xen-api.sock")
			if core.DEBUG: print "DEBUG Xen-Api: using unix socket."
		else:
			self.server = XenAPI.Session("http://"+hostname+":9363")
			if core.DEBUG: print "DEBUG Xen-Api: using tcp socket."
		self.server.login_with_password("root", "")

		# Prepare connection with legacy API
		self.__legacy_server=None

		# Prepare metrics
		self.__metrics=None

	def __del__(self):
		"""Close connection on exit."""
		# Close SSH
		try:
			self.ssh.close()
		except:
			pass

		# Close Xen-API
		try:
			self.server.xenapi.session.logout()
		except:
			pass

	def get_legacy_server(self):
		"""Return the legacy API socket."""
		if self.is_local_node():
			if self.__legacy_server is None:
				self.__legacy_server=ServerProxy("httpu:///var/run/xend/xmlrpc.sock")
			return self.__legacy_server
		else:
			raise ClusterNodeError(self.hostname,ClusterNodeError.LEGACY_ERROR,"unix socket")

	def get_metrics(self):
		"""Return the metrics instance of this node."""
		if self.__metrics is None:
			self.__metrics=Metrics(self)
		return self.__metrics

	def __repr__(self):
		return "<Node Instance: "+ self.hostname +">"

	def run(self,cmd):
		"""Execute command on this node via SSH (or via shell if this is the local node)."""
# Does'nt work with LVM commands
#		if(self.is_local_node()):
#			p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
#			msg=p.stderr.read()
#			if(len(msg)>0):
#				raise ClusterNodeError(self.hostname,ClusterNodeError.SHELL_ERROR,msg)
#			return p.stdout
#		else:
		
# Deadlock bug if cmd's output is bigger than 65k
#       if(self.is_local_node() and not core.USESSH):
#           if core.DEBUG : print "DEBUG SHELL: "+ self.get_hostname() +" -> "+cmd
#           stdout, stdin, stderr = popen2.popen3(cmd,9300000)
#           msg=stderr.read()
#           if(len(msg)>0):
#               raise ClusterNodeError(self.hostname,ClusterNodeError.SHELL_ERROR,msg)

		if(core.cfg['PATH']):
			cmd=core.cfg['PATH'] + "/" + cmd

		if(self.is_local_node() and not core.USESSH):
			if core.DEBUG : print "DEBUG SHELL: "+ self.get_hostname() +" -> "+cmd

			# Create buffers
			stdout=StringIO.StringIO()
			stderr=StringIO.StringIO()

			proc=popen2.Popen3(cmd, True) # Run cmd

			# Load output in the buffers and rewind them
			stdout.write(proc.fromchild.read())
			stderr.write(proc.childerr.read())
			stdout.seek(0)
			stderr.seek(0)

			if proc.wait() != 0:
				msg=stderr.read()
				if(len(msg)>0):
					raise ClusterNodeError(self.hostname,ClusterNodeError.SHELL_ERROR,msg)
		else:
			if core.DEBUG : print "DEBUG SSH: "+ self.get_hostname() +" -> "+cmd
			stdin, stdout, stderr = self.ssh.exec_command(cmd)
			# Lock bug workaround : Check exit status before trying to read stderr
			# Because sometimes, when stdout is big (maybe >65k ?), strderr.read() hand on
			# a thread's deadlock if stderr is readed before stdout...
			if stderr.channel.recv_exit_status() != 0:
				stderr.channel.settimeout(3)
				try:
					msg=stderr.read()
					if(len(msg)>0):
						raise ClusterNodeError(self.hostname,ClusterNodeError.SSH_ERROR,msg)
				except socket.timeout:
					raise ClusterNodeError(self.hostname,ClusterNodeError.SSH_ERROR,"Timeout reading stderr !")
		return stdout

	def is_local_node(self):
		"""Return True if this node is the local node."""
		return platform.node()==self.hostname
		
	def is_vm_started(self, vmname):
		"""Return True if the specified vm is started on this node."""
		if core.USESSH:
			for vm in self.run("xm list | awk '{print $1;}'").readlines():
				if vmname == vm.strip():
					return True
			return False
		else:
			vm=self.server.xenapi.VM.get_by_name_label(vmname)
			if core.DEBUG: print "DEBUG Xen-Api: ", vm
			return len(vm)>0	

	def is_vm_autostart_enabled(self, vmname):
		"""Return True if the autostart link is present for the specified vm on this node."""
		for link in self.run("ls /etc/xen/auto/").readlines():
			if vmname == link.strip():
				return True
		return False

	def get_hostname(self):
		"""Return the hostname of this node."""
		return self.hostname

	def get_bridges(self):
		"""Return the list of bridges on this node."""
		# brctl show | tail -n +2 | perl -ne 'print "$1\n" if(/^(\w+)\s/)'
		# ou 
		# find /sys/class/net/ -name bridge | grep -v brport | awk -F/ '{ print $5 }'
		# ou 
		# brctl show | perl -ne 'next if(/bridge/); print "$1\n" if(/^(\w+)\s/)'
		# ou
		# find /sys/class/net/ -maxdepth 2 -name bridge  |  awk -F/ '{ print $5 }'
		bridges=list()
		for line in self.run("find /sys/class/net/ -maxdepth 2 -name bridge").readlines():
			bridges.append(line.split('/')[4])
		return bridges

	def get_vlans(self):
		"""Return the list of vlans configured on this node."""
		vlans=list()
		for line in self.run("cat /proc/net/vlan/config | tail -n +3").readlines():
			vlans.append(line.split()[0])
		return vlans

	def get_vm_started(self):
		"""Return the number of started vm on this node."""
		if core.USESSH:
			return int(self.run('xenstore-list /local/domain | wc -l').read())-1 # don't count Dom0
		else:
			if core.DEBUG: print "DEBUG Xen-Api: ", self.server.xenapi.VM.get_all()
			return len(self.server.xenapi.VM.get_all())-1

	def get_vgs(self,lvs):
		"""Return the list of volumes groups associated with the given logicals volumes."""
		vgs=list()
		for line in self.run("lvdisplay -c " + " ".join(lvs)).readlines():
			vgs.append(line.split(':')[1])

		return list(set(vgs))	# Delete duplicate entries
	
	def get_vgs_map(self):
		"""Return the dict of volumes groups with each associated physicals volumes of this node."""
		map=dict()
		for line in self.run("pvs -o pv_name,vg_name --noheading").readlines():
			(pv, vg)=line.split()
			map.setdefault(vg, []).append(pv.lstrip("/dev/"))

		return map

	def refresh_lvm(self,vgs):
		"""Perform a LVM refresh."""
		self.run("lvchange --refresh " + " ".join(vgs))

	def deactivate_lv(self,vmname):
		"""Deactivate the logicals volumes of the specified VM on this node.

		Raise a ClusterNodeError if the VM is running.
		"""
		if(self.is_vm_started(vmname)):
			raise ClusterNodeError(self.hostname,ClusterNodeError.VM_RUNNING,vmname) 
		else:
			lvs=VM(vmname).get_lvs()
			self.refresh_lvm(self.get_vgs(lvs))
			self.run("lvchange -aln " + " ".join(lvs))

	def deactivate_all_lv(self):
		"""Deactivate all the logicals volumes used by stopped VM on this node."""
		for vm in [ vm.strip() for vm in self.run("ls -F "+ core.cfg['VMCONF_PATH'] +" | grep -v '/'").readlines() ]:
			if not self.is_vm_started(vm):
				self.deactivate_lv(vm)

	def activate_lv(self,vmname):
		"""Activate the logicals volumes of the specified VM on this node."""
		lvs=VM(vmname).get_lvs()
		self.refresh_lvm(self.get_vgs(lvs))
		self.run("lvchange -aly " + " ".join(lvs))
		
	def start_vm(self, vmname, console):
		"""Start the specified VM on this node.

		vmname - (String) VM hostname 
		console - (boolean) Attach console to the domain
		"""

		args = [core.cfg['VMCONF_PATH'] + vmname]
		if core.USESSH:
			self.run("xm create " + args[0])
		else:
			if self.is_local_node():

				if console:
					args.append('-c')

				# Use Legacy XMLRPC because Xen-API is sometimes buggy
				main.server=self.get_legacy_server()
				main.serverType=main.SERVER_LEGACY_XMLRPC
				main.xm_importcommand("create" , args)
			else:
				if console:
					print "Warning : cannot attach console when using remote Xen-API."
				args.append('--skipdtd') # Because file /usr/share/xen/create.dtd is missing

				main.server=self.server
				main.serverType=main.SERVER_XEN_API
				main.xm_importcommand("create" , args)
			

	def migrate(self, vmname, dest_node):
		"""Live migration of specified VM to the given node.

		Raise a ClusterNodeError if the vm is not started on this node.
		"""
		if core.USESSH:
			self.run("xm migrate -l " + vmname + " " + dest_node.get_hostname())
		else:
#			if self.is_local_node():
#				# Use Legacy XMLRPC because Xen-API is sometimes buggy
#				server=self.get_legacy_server()
#				server.xend.domain.migrate(vmname, dest_node.get_hostname(), True, 0, -1, None)
#			else:
				try:
					vm=self.server.xenapi.VM.get_by_name_label(vmname)[0]
				except IndexError:
					raise ClusterNodeError(self.get_hostname(),ClusterNodeError.VM_NOT_RUNNING,vmname)
				self.server.xenapi.VM.migrate(vm,dest_node.get_hostname(),True,{'port':0,'node':-1,'ssl':None})

		
	def enable_vm_autostart(self, vmname):
		"""Create the autostart link for the specified vm."""
		self.run("test -L /etc/xen/auto/%s || ln -s /etc/xen/vm/%s /etc/xen/auto/" % (vmname, vmname))
		
	def disable_vm_autostart(self, vmname):
		"""Delete the autostart link for the specified vm."""
		self.run("rm -f /etc/xen/auto/"+vmname)
		
	def shutdown(self, vmname):
		"""Shutdown the specified vm.

		Raise a ClusterNodeError if the vm is not running.
		"""
		MAX_TIMOUT=60	# Time waiting for VM shutdown 

		if core.USESSH:
			self.run("xm shutdown " + vmname)
		else:
			try:
				vm=self.server.xenapi.VM.get_by_name_label(vmname)[0]
			except IndexError:
				raise ClusterNodeError(self.get_hostname(),ClusterNodeError.VM_NOT_RUNNING,vmname)
			self.server.xenapi.VM.clean_shutdown(vm)

		# Wait until VM is down
		time.sleep(2)
		timout=0
		while(self.is_vm_started(vmname) and timout<=MAX_TIMOUT):
			time.sleep(1)
			timout += 1

		self.deactivate_lv(vmname)
	
	def get_vm(self, vmname):
		"""Return the VM instance corresponding to the given vmname."""
		if core.USESSH:
			line=self.run("xm list | grep " + vmname + " | awk '{print $1,$2,$3,$4;}'").read()
			if len(line)<1:
				raise ClusterNodeError(self.get_hostname(),ClusterNodeError.VM_NOT_RUNNING,vmname)
			(name, id, ram, vcpu)=line.strip().split()
			return VM(name, id, ram, vcpu)
		else:
			try:
				uuid=self.server.xenapi.VM.get_by_name_label(vmname)[0]
			except IndexError:
				raise ClusterNodeError(self.get_hostname(),ClusterNodeError.VM_NOT_RUNNING,vmname)
			vm_rec=self.server.xenapi.VM.get_record(uuid)
			vm=VM(vm_rec['name_label'],vm_rec['domid'])
			vm.metrics=self.server.xenapi.VM_metrics.get_record(vm_rec['metrics'])
			return vm

	def get_vms(self):
		"""Return the list of VM instance for each running vm."""
		vms=list()
		if core.USESSH:
			for line in self.run("xm list | awk '{print $1,$2,$3,$4;}' | tail -n +3").readlines():
				(name, id, ram, vcpu)=line.strip().split()
				vms.append(VM(name, id, ram, vcpu))
		else:
			dom_recs = self.server.xenapi.VM.get_all_records()
			dom_metrics_recs = self.server.xenapi.VM_metrics.get_all_records()
			if core.DEBUG: print "DEBUG Xen-Api: ", dom_recs

			for dom_rec in dom_recs.values():
				if dom_rec['name_label'] != "Domain-0":
					vm=VM(dom_rec['name_label'],dom_rec['domid'])
					vm.metrics=dom_metrics_recs[dom_rec['metrics']]
					vms.append(vm)

		return vms

	def check_lvs(self):
		"""Perform a sanity check of the LVM activation on this node."""
		if not core.QUIET: print "Checking LV activation on",self.get_hostname(),"..." 
		safe=True

		# Get all active LVs on the node
		regex = re.compile('.{4}a.')
		active_lvs = list()
		for line in self.run("lvs -o vg_name,name,attr --noheading").readlines():
			(vg, lv, attr)=line.strip().split()
			if regex.search(attr) != None:
				active_lvs.append("/dev/"+vg+"/"+lv)

		# Get all LVs used by VMs
		used_lvs = list()
		regex = re.compile('phy:([^,]+).*')
		for line in self.run("cat "+ core.cfg['VMCONF_PATH'] +"* 2>/dev/null").readlines():
			try:
				used_lvs.append(regex.search(line).group(1))
			except:
				pass

		# Compute the intersection of the two lists (active and used LVs)
		active_and_used_lvs = list(Set(active_lvs) & Set(used_lvs))
		if core.DEBUG: print "DEBUG active_and_used_lvs =", active_and_used_lvs

		# Get all LVs of running VM
		running_lvs = [ lv for vm in self.get_vms() for lv in vm.get_lvs() ]
		if core.DEBUG: print "DEBUG running_lvs =", running_lvs

		# Compute activated LVs without running vm
		lvs_without_vm = list(Set(active_and_used_lvs) - Set(running_lvs))
		if len(lvs_without_vm):
			print " ** WARNING : Found activated LV without running VM :\n\t", "\n\t".join(lvs_without_vm)
			safe=False

		# Compute running vm without activated LVs 
		vm_without_lvs = list(Set(running_lvs) - Set(active_and_used_lvs))
		if len(vm_without_lvs):
			print " ** WARNING : Found running VM without activated LV :\n\t", "\n\t".join(vm_without_lvs)
			safe=False

		return safe

	def check_autostart(self):
		"""Perform a sanity check of the autostart links."""
		if not core.QUIET: print "Checking autostart links on",self.get_hostname(),"..." 
		safe=True

		# Get all autostart links on the node
		links = [ link.strip() for link in self.run("ls /etc/xen/auto/").readlines() ]
		if core.DEBUG: print "DEBUG links =", links

		# Get all running VM
		running_vms = [ vm.name for vm in self.get_vms() ]
		if core.DEBUG: print "DEBUG running_vms =", running_vms

		# Compute running vm without autostart link
		link_without_vm = list(Set(links) - Set(running_vms))
		if len(link_without_vm):
			print " ** WARNING : Found autostart link without running VM :\n\t", "\n\t".join(link_without_vm)
			safe=False

		# Compute running vm without autostart link
		vm_without_link = list(Set(running_vms) - Set(links))
		if len(vm_without_link):
			print " ** WARNING : Found running VM without autostart link :\n\t", "\n\t".join(vm_without_link)
			safe=False

		return safe

	# Define accessors 
	legacy_server = property(get_legacy_server)
	metrics = property(get_metrics)




class ClusterNodeError(Exception):

	"""This class is used to raise specials errors relatives to the node."""

	# Error codes list
	VM_RUNNING=1
	VM_NOT_RUNNING=2
	SSH_ERROR=3
	SHELL_ERROR=4
	LEGACY_ERROR=5
	NOT_ENOUGH_RAM=6

	def __init__(self, nodename, type, value=""):
		self.nodename=nodename
		self.type=type
		self.value=value

	def __str__(self):
		if(self.type==self.VM_RUNNING):
			msg = "VM "+ self.value + " is running."
		elif(self.type==self.VM_NOT_RUNNING):
			msg = "VM " + self.value + " is not running here."
		elif(self.type==self.SSH_ERROR):
			msg = "SSH failure: " + self.value
		elif(self.type==self.SHELL_ERROR):
			msg = "Local Exec failure: " + self.value
		elif(self.type==self.LEGACY_ERROR):
			msg = "Legacy-API unavailable: " + self.value + " is not available on remote host."
		elif(self.type==self.NOT_ENOUGH_RAM):
			msg = "There is not enough ram: " + self.value
		else:
			msg = "Unknown error."
		return "\nError on node " +self.nodename+ ": " + msg



if __name__ == "__main__":
	"""Main is used to run test case."""
	pass


# vim: ts=4:sw=4:ai
