cxm - Clustered Xen Manager
===========================

What is cxm?
------------

Cxm is a set of tools that help you manage a cluster of xen servers.
It is composed of two main parts: an API and a daemon (cxmd).

The API, and the associated command line interface `cxm`, is used to manipulate the virtuals machines, the xen servers in the cluster, and to retrieve the cluster attributes. 
With the snmp_xen.py script, you can monitor the xen servers defined in your cluster via snmp.

The daemon, and the associated command line interface `cxmd_ctl`, is used to manage the cluster. It can automate actions like loadbalancing, failover and fencing, and it uses internally a heartbeat system.

Another daemon, SVNWatcherd, allows the user to share configuration files across all cluster nodes using a Subversion repository.

Why cxm?
--------

Cxm was developed to cover the shortcomings of other free software packages for cluster management of Xen servers.

In particular, it turns out that most of them are designed to manage clusters of virtual machines, whereas our specific requirement was to manage clusters of xen servers.

Redhat Cluster Suite with xen driver was considered, but some of its features and behaviours did not match our requirements. For example, fencing was found too aggressive for our needs, and in our case, we did not need any quorum protection.
Others tools, like Pacemaker, are more adapted to manage applicative clusters than xen servers.


Context:
--------

This tool is designed for Xen. Support of other hypervisors, such KVM or libvirt, is out of scope.

All cxm component are written in Python. Due to a constraint in Centos 5.x production version, it has only been tested with Python 2.4 and Twisted 8.1.0.

Whole management is only done via CLI, with root account, as this is a tool for sysadmin expert in virtualization.
If you want a graphical interface for VM provisionning, you can try [Opennebula](http://www.opennebula.org/). See /misc/opennebula/ for details.


Other documentation:
--------------------

See /doc/INSTALL.md for installation instructions.

For further information, see /doc directory.

