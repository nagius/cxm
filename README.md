cxm - Clustered Xen Manager
===========================

What is cxm?
------------

Cxm is a set of tools that help you manage a cluster of xen servers.
It is composed of two main parts: an API and a daemon (cxmd).

The API, and the associated command line interface 'cxm', is used to manipulate the virtuals machines, the xen servers in the cluster, and to retrieve the cluster attributes. 
With the snmp_xen.py script, you can monitor the xen servers defined in your cluster via snmp.

The daemon, and the associated command line interface 'cxmd_ctl', is used to manage the cluster. It can automate actions like loadbalancing, failover and fencing, and it uses internally a heartbeat system.

Another daemon, SVNWatcherd, allows the user to share configuration files across all cluster nodes using a Subversion repository.

Why cxm?
--------

Cxm was developed to cover the shortcomings of other free software packages for cluster management of Xen servers.

In particular, it turns out that most of them are designed to manage clusters of virtual machines, whereas our specific requirement was to manage clusters of xen servers.

Redhat Cluster Suite was considered, but some of its features and behaviours did not match our requirements. For example, fencing was found too aggressive for our needs, and in our case, we did not need any quorum protection.
Others tools, like Pacemaker, are more adapted to manage applicative clusters than xen servers.


Prerequistes:
-------------

- The heartbeat system needs a shared storage over a SAN, like a rack disk with a Fibre Channel or a SAS network. All ethernet-based solutions, such as iSCSI, NFS or NBD should be avoided, as they rely on an ethernet network, and thus cannot be used to detect when a network partition splits the cluster.

- All virtual machines have to be named within Xen with their FQDN, with a valid DNS record.

- All VM configuration files should be named with the FQDN of the corresponding virtual machine.

- All files in the VM configuration directory (/etc/xen/vm) must contain valid xen syntax, where disk devices must exist. Any incorrect file will put the cxmd daemon in panic mode.

- The VM configuration directory (/etc/xen/vm) must be shared and synchronized between all nodes. You can use SVNWatcher to do this.

- All servers, both physical and virtual, must be configured to answer a ping request that can be sent from anywhere in the cluster. fping is used to check whether virtual machines are alive.

- All disk devices used by virtual machines must be defined as LVM logical volumes, using the 'phy:/' prefix. tap or file devices are not supported.

- All nodes must be allowed to connect to each other with SSH without requesting a password. You need to deploy SSH keys over all nodes and to accept all servers' keys.

- Of course, live migration must be operational between all nodes.

+ TODO conf API xen both LegacyAPI and new XEN-API with TCP and unix socket.


Dependencies:
-------------

Due to a constraint in RedHat 5.x production version, cxm has only been tested with Python 2.4 and twisted 8.1.0.
The folowing packages are needed:

 - python
 - python-twisted 
 - python-simplejson (due to python2.4)
 - python-paramiko
 - LVM2
 - SSH
 - fping

	If you plan to use SVNwatcher, these additional packages are needed:

 - subversion
 - inotifytools


Runtime:
--------

* SVNWatcher

If an error occurs during SVNWatcher execution, it will automatically shutdown itself to prevent more damages.
In case of uncommitted modifications, you will have to resynchronize the repository with the following procedure:


  - Shutdown SVNWatcher
		/etc/init.d/svnwatcherd stop

  - Recover your SVN repository and clean it
		svn status # Should not return anything

  - Start SVNWatcher
		/etc/init.d/svnwatcherd start

  - Force an update to propagate "un-watched" modifications to other nodes
		/etc/init.d/svnwatcherd update

# EOF
