#!/usr/bin/python -u
# Option -u is needed for communication with snmpd

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


import snmp_passpersist as snmp
import cxm.node, cxm.core
import platform, syslog, sys, time, errno

# General stuff
POOLING_INTERVAL=60			# Update timer, in second
MAX_RETRY=10				# Number of successives retry in case of error
OID_BASE=".1.3.6.1.3.53.8"

# Configure cxm module
cxm.core.DEBUG=False
cxm.core.QUIET=True

# Globals vars
pp=None
node=None


"""
 Map of snmp_xen MIB :

	- 0:hostname
		- 1:nr_cpu
		- 2:nr_vm
		- 3:nr_irq
		- 4:ram 
			+ 1:used ram
			+ 2:free ram
		- 5:disks
			- #: 
				+ 1:name
				+ 2:read
				+ 3:write
		- 6:bridges
			- #:
				+ 1:name
				+ 2:Rx
				+ 3:Tx
		- 7:vlans
			- #:
				+ 1:name
				+ 2:Rx
				+ 3:Tx
		- 8:VMs
			- #:
				+ 1:name
				+ 2:id
				+ 3:%cpu
				+ 4:nr_vcpu
				+ 5:allocated ram
				- 6:disk
					+ 2:read
					+ 3:write
				- 7:net
					- #:
						+ 2:Rx
						+ 3:Tx

"""


def update_data():
	"""Update snmp's data from cxm API"""
	global pp
	global node

	# Load all stats once
	vms=node.get_vms()
	ram=node.metrics.get_ram_infos()
	vgs_io=node.metrics.get_host_vgs_io()
	net_io=node.metrics.get_host_net_io()
	vms_stat=node.metrics.get_vms_record()

	# Number of VM
	pp.add_int('0.2',len(vms))

	# Number of used IRQ
	pp.add_int('0.3',node.metrics.get_used_irq())

	# Ram infos
	pp.add_int('0.4.1',ram['used'])
	pp.add_int('0.4.2',ram['free'])

	# Disk's IO
	oid=0
	for name in vgs_io.keys():
		pp.add_str('0.5.'+str(oid)+'.1',name)
		pp.add_cnt('0.5.'+str(oid)+'.2',vgs_io[name]['Read'])
		pp.add_cnt('0.5.'+str(oid)+'.3',vgs_io[name]['Write'])
		oid+=1

	# Network's IO
	oid=0
	for name in net_io['bridges'].keys():
		pp.add_str('0.6.'+str(oid)+'.1',name)
		pp.add_cnt('0.6.'+str(oid)+'.2',net_io['bridges'][name]['Rx'])
		pp.add_cnt('0.6.'+str(oid)+'.3',net_io['bridges'][name]['Tx'])
		oid+=1

	oid=0
	for name in net_io['vlans'].keys():
		pp.add_str('0.7.'+str(oid)+'.1',name)
		pp.add_cnt('0.7.'+str(oid)+'.2',net_io['vlans'][name]['Rx'])
		pp.add_cnt('0.7.'+str(oid)+'.3',net_io['vlans'][name]['Tx'])
		oid+=1

	# For each VM
	oid=1
	for vm in vms:
		pp.add_str('0.8.'+str(oid)+'.1',vm.name)
		pp.add_int('0.8.'+str(oid)+'.2',vm.id)
		pp.add_int('0.8.'+str(oid)+'.3',vms_stat[vm.name]['cpu'])
		pp.add_int('0.8.'+str(oid)+'.4',vm.get_vcpu())
		pp.add_int('0.8.'+str(oid)+'.5',vm.get_ram())
		pp.add_cnt('0.8.'+str(oid)+'.6.2',vms_stat[vm.name]['disk']['Read'])
		pp.add_cnt('0.8.'+str(oid)+'.6.3',vms_stat[vm.name]['disk']['Write'])
		vifn=0
		for vif in vms_stat[vm.name]['net']:
			pp.add_cnt('0.8.'+str(oid)+'.7.'+str(vifn)+'.2',vif['Rx'])
			pp.add_cnt('0.8.'+str(oid)+'.7.'+str(vifn)+'.3',vif['Tx'])
			vifn+=1
		oid+=1

	# For the dom0
	pp.add_int('0.8.0.3',vms_stat['Domain-0']['cpu'])



def main():
	"""Feed the snmp_xen MIB tree and start listening for snmp's passpersist"""
	global pp
	global node

	syslog.openlog(sys.argv[0],syslog.LOG_PID)
	
	retry_timestamp=int(time.time())
	retry_counter=MAX_RETRY
	while retry_counter>0:
		try:
			syslog.syslog(syslog.LOG_INFO,"Starting Xen monitoring...")

			# Load helpers
			pp=snmp.PassPersist(OID_BASE)
			node=cxm.node.Node(platform.node())

			# Set statics data
			pp.add_str('0',node.get_hostname())
			pp.add_int('0.1',int(node.metrics.get_host_nr_cpus()))
			pp.add_str('0.8.0.1','Domain-0')
			pp.add_int('0.8.0.2',0)
			pp.add_int('0.8.0.4',2) # Always 2 VPCU for Dom0 (TODO: ask the Xen-API)
			
			pp.start(update_data,POOLING_INTERVAL) # Should'nt return (except if updater thread has died)

		except IOError, e:
			if e.errno == errno.EPIPE:
				syslog.syslog(syslog.LOG_INFO,"Snmpd had close the pipe, exiting...")
				sys.exit(0)
		except Exception, e:
			syslog.syslog(syslog.LOG_WARNING,"Main thread as died: %s" % (e))
		else:
			syslog.syslog(syslog.LOG_WARNING,"Updater thread as died: %s" % (pp.error))

		syslog.syslog(syslog.LOG_WARNING,"Restarting monitoring in 15 sec...")
		time.sleep(15)

		# Errors frequency detection
		now=int(time.time())
		if (now - 3600) > retry_timestamp: 	# If the previous error is older than 1H
			retry_counter=MAX_RETRY			# Reset the counter
		else:
			retry_counter-=1				# Else countdown
		retry_timestamp=now

	syslog.syslog(syslog.LOG_ERR,"Too many retry, abording... Please check if xen is running !")
	sys.exit(1)


if __name__ == "__main__":
	main()

# vim: ts=4:sw=4:ai
