Installation instructions
=========================

Dependencies:
-------------

The following packages are needed:

* python
* python-twisted  
* python-simplejson (due to python2.4)
* python-paramiko
* LVM2
* SSH
* fping

    If you plan to use SVNwatcher, these additional packages are needed:

* subversion
* inotifytools
* and a SVN server on another machine

Prerequistes:
-------------

* First of all, you need a SAN with LVM. 
The use of clvmd and the Redhat Cluster Suite is not manadatory, but it is a good idea if you do not want to risk loosing data.
Without clvmd, set `REFRESH=True` in `cxm.conf` to run `vgchange --refresh` before each LVM action to avoid metadata corruption.

* The heartbeat system need a shared storage over a SAN, like a rack disk with a Fibre Channel or a SAS network. All ethernet-based solutions, such as iSCSI, NFS or NBD should be avoided, as they rely on an ethernet network, and thus cannot be used to detect when a network partition splits the cluster.

* All virtual machines have to be named within Xen with their FQDN, with a valid DNS record.

* All VM configuration files should be named with the FQDN of the corresponding virtual machine.

* All files in the VM configuration directory (/etc/xen/vm) must contain valid xen syntax, where disk devices must exist. Any incorrect file will put the cxmd daemon in panic mode.

* The VM configuration directory (/etc/xen/vm) must be shared and synchronized between all nodes. You can use SVNWatcher to do this. See /doc/SVNWatcher.md for more information.

* All servers, both physical and virtual, must be configured to answer a ping request that can be sent from anywhere in the cluster. fping is used to check whether virtual machines are alive.

* All disk devices used by virtual machines must be defined as LVM logical volumes, using the `phy:/` prefix. tap or file devices are not supported.

* All nodes must be allowed to connect to each other with SSH without requesting a password. You need to deploy SSH keys over all nodes and accept all servers keys.

* Of course, live migration must be operational between all nodes.


Cxm installation steps
----------------------

* Configure Xend as described in doc/cxmd.md
* Put SSH keys for root and check login from/to each server. This is the most common error.
* Setup the cman/clvm cluster with the SAN and switch all shared volume group in cluster mode.
* Copy `lib/cxm` to your Python 2.4 library path.
* Copy `bin/cxm` and `bin/cxmd_ctl` to your sbin path.
* Copy `bin/cxmd`, `bin/cxmdomains` and `bin/svnwatcherd` to /etc/init.d/. These are SystemV init script. You can enable them with `chkconfig`.
* Copy `misc/cxm.conf` to /etc/. This is the main configuration file. 
* Create a fencing script, for example with IPMI or iLO, that will poweroff the node passed in parameter.
* Create a 4 MB logical volume on the shared VG to hold the heartbeat disk.
* Adapt `/etc/cxm.conf` to your configuration. Do not forget to preserve Python syntax. Interesting parameters are :
    * `CLUSTER_NAME`: Name of the cluster
    * `ALLOWED_NODES` : Python list of the cluster members
    * `HB_DISK` : Full name of the heartbeat LV
    * `FENCE_CMD` : Path to your fencing script
* Format the heartbeat disk with the `cxmd_ctl --format` command.
* Start cxm : `/etc/init.d/cxmd start`
* Check log `/var/log/xen/cxmd.log` to see whats happening.

You can start playing with cxm with `cxm help` and `cxmd_ctl -h` 


SVNWatcher installation steps
-----------------------------

* Setup a SVN repository on another server.
* On each node, as root :
    * Do a checkout of this repo in /etc/xen/vm/
    * Configure SVN to remember the password.
    * Start SVNWatcher : `/etc/init.d/svnwatcherd start`. It must be started after cxmd.
    * Check log `/var/log/xen/svnwatcherd.log`.


