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
OID_BASE=".1.3.6.1.3.53.3.54.1"

# Configure cxm module
cxm.core.cfg['DEBUG']=False
cxm.core.cfg['QUIET']=True

# Globals vars
pp=None
node=None


"""
 Map of snmp_xen MIB :

+--XenStats(1)
   |
   +--XenStatsHost(1)
      |
      +-- -R-- String    XenStatsHostName(1)
      |        Textual Convention: DisplayString
      |        Size: 0..255
      +-- -R-- Gauge     XenStatsHostCpu(2)
      +-- -R-- Gauge     XenStatsHostVm(3)
      +-- -R-- Gauge     XenStatsHostIrq(4)
      |
      +--XenStatsHostRam(5)
      |  |
      |  +-- -R-- Gauge     XenStatsHostRamUsed(1)
      |  +-- -R-- Gauge     XenStatsHostRamFree(2)
      |
      +--XenStatsHostDisks(6)
      |  |  Index: XenStatsHostDiskName
      |  |
      |  +-- -R-- String    XenStatsHostDiskName(1)
      |  |        Textual Convention: DisplayString
      |  |        Size: 0..255
      |  +-- -R-- Counter   XenStatsHostDiskRead(2)
      |  +-- -R-- Counter   XenStatsHostDiskWrite(3)
      |
      +--XenStatsHostBridges(7)
      |  |  Index: XenStatsHostBridgeName
      |  |
      |  +-- -R-- String    XenStatsHostBridgeName(1)
      |  |        Textual Convention: DisplayString
      |  |        Size: 0..255
      |  +-- -R-- Counter   XenStatsHostBridgeRx(2)
      |  +-- -R-- Counter   XenStatsHostBridgeTx(3)
      |
      +--XenStatsHostVlans(8)
      |  |  Index: XenStatsHostVlanName
      |  |
      |  +-- -R-- String    XenStatsHostVlanName(1)
      |  |        Textual Convention: DisplayString
      |  |        Size: 0..255
      |  +-- -R-- Counter   XenStatsHostVlanRx(2)
      |  +-- -R-- Counter   XenStatsHostVlanTx(3)
      |
      +--XenStatsHostVms(9)
      |  |  Index: XenStatsHostVmName
      |  |
      |  +-- -R-- String    XenStatsHostVmName(1)
      |  |        Textual Convention: DisplayString
      |  |        Size: 0..255
      |  +-- -R-- INTEGER   XenStatsHostVmId(2)
      |  +-- -R-- Gauge     XenStatsHostVmCpuUsage(3)
      |  +-- -R-- Gauge     XenStatsHostVmVcpu(4)
      |  +-- -R-- Gauge     XenStatsHostVmAllocRam(5)
      |  +-- -R-- Counter   XenStatsHostVmDiskRead(6)
      |  +-- -R-- Counter   XenStatsHostVmDiskWrite(7)
      |
      +--XenStatsHostVmNet(10)
         |  Index: XenStatsHostVmNetIfName, XenStatsHostVmName
         |
         +-- -R-- String    XenStatsHostVmNetIfName(1)
         |        Textual Convention: DisplayString
         |        Size: 0..255
         +-- -R-- Counter   XenStatsHostVmNetRx(2)
         +-- -R-- Counter   XenStatsHostVmNetTx(3)

"""


def update_data():
	"""Update snmp's data from cxm API"""
	global pp
	global node

	# Load all stats once
	vms=node.get_vms()
	ram=node.metrics.get_ram_infos()
	nr_cpu=int(node.metrics.get_host_nr_cpus())
	vgs_io=node.metrics.get_host_vgs_io()
	net_io=node.metrics.get_host_net_io()
	vms_stat=node.metrics.get_vms_record()

	# Number of VM
	pp.add_gau('1.3.0',len(vms))

	# Number of used IRQ
	pp.add_gau('1.4.0',node.metrics.get_used_irq())

	# Ram infos
	pp.add_gau('1.5.1.0',ram['used'])
	pp.add_gau('1.5.2.0',ram['free'])

	# Disk's IO
	for name in vgs_io.keys():
		oid=pp.encode(name)
		pp.add_str('1.6.1.'+oid,name)
		pp.add_cnt('1.6.2.'+oid,vgs_io[name]['Read'])
		pp.add_cnt('1.6.3.'+oid,vgs_io[name]['Write'])

	# Network's IO
	for name in net_io['bridges'].keys():
		oid=pp.encode(name)
		pp.add_str('1.7.1.'+oid,name)
		pp.add_cnt('1.7.2.'+oid,net_io['bridges'][name]['Rx'])
		pp.add_cnt('1.7.3.'+oid,net_io['bridges'][name]['Tx'])

	for name in net_io['vlans'].keys():
		oid=pp.encode(name)
		pp.add_str('1.8.1.'+oid,name)
		pp.add_cnt('1.8.2.'+oid,net_io['vlans'][name]['Rx'])
		pp.add_cnt('1.8.3.'+oid,net_io['vlans'][name]['Tx'])

	# For each VM
	for vm in vms:
		oid=pp.encode(vm.name)
		pp.add_str('1.9.1.'+oid,vm.name)
		pp.add_int('1.9.2.'+oid,vm.id)
		pp.add_gau('1.9.3.'+oid,"%.1f" % round(vms_stat[vm.name]['cpu']/nr_cpu,1)) # CPU Percentage relative to the host capatity
		pp.add_gau('1.9.4.'+oid,vm.get_vcpu())
		pp.add_gau('1.9.5.'+oid,vm.get_ram())
		pp.add_cnt('1.9.6.'+oid,vms_stat[vm.name]['disk']['Read'])
		pp.add_cnt('1.9.7.'+oid,vms_stat[vm.name]['disk']['Write'])
		vifn=0
		for vif in vms_stat[vm.name]['net']:
			vifoid=pp.encode('eth'+str(vifn))
			pp.add_str('1.10.1.'+vifoid+'.'+oid,'eth'+str(vifn))
			pp.add_cnt('1.10.2.'+vifoid+'.'+oid,vif['Rx'])
			pp.add_cnt('1.10.3.'+vifoid+'.'+oid,vif['Tx'])
			vifn+=1

	# For the dom0
	oid=pp.encode("Domain-0")
	pp.add_gau('1.9.3.'+oid,"%.1f" % round(vms_stat['Domain-0']['cpu']/nr_cpu,1))



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
			pp.add_str('1.1.0',node.get_hostname())
			pp.add_gau('1.2.0',int(node.metrics.get_host_nr_cpus()))
			oid=pp.encode("Domain-0")
			pp.add_str('1.9.1.' + oid,'Domain-0')
			pp.add_int('1.9.2.' + oid,0)
			pp.add_gau('1.9.4.' + oid,2) # Always 2 VPCU for Dom0 (TODO: ask the Xen-API)
			
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
