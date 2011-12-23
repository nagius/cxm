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

Others documentations:
----------------------

See /doc directory.

