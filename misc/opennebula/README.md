OpenNebula 3.6+ drivers for cxm
===============================

Concepts
--------

These drivers provide high availability, failover and loadbalancing to OpenNebula with cxm cluster tools. In this mode of hosting, virtual machine disks are stored on a SAN with LVM, one LV per disk.

The current architecture of cxm drivers for Opennebula allow to do this :

<pre>

                                ┏━━━━━━━━━━━━━━┓
                                ┃  OpenNebula  ┃
                                ┃   Frontend   ┃
                                ┃         ╭───╮┃
                                ┃         │DAS│┃
                                ┃         ╰───╯┃
                                ┗━━━━━━━━━━━━━━┛
                                     ╱   ╲
                                    ╱     ╲
                                   ╱       ╲
  ╭╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╮       ╲
  ┆ CXM Cluster                     ┆        ╲
  ┆                                 ┆    ┏━━━━━━━━━━━━━━┓
  ┆  ┏━━━━━━━━━━━━┓ ┏━━━━━━━━━━━━┓  ┆    ┃  Standalone  ┃
  ┆  ┃  XEN Node  ┃ ┃  XEN Node  ┃  ┆    ┃   XEN host   ┃
  ┆  ┗━━━━━━┯━━━━━┛ ┗━━━━━━┯━━━━━┛  ┆    ┃         ╭───╮┃
  ┆         └──────┬───────┘        ┆    ┃         │DAS│┃
  ┆             ╭──┴──╮             ┆    ┃         ╰───╯┃
  ┆             │ SAN │             ┆    ┗━━━━━━━━━━━━━━┛
  ┆             ╰─────╯             ┆   
  ┆                                 ┆
  ╰╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╯
</pre>

Standalone XEN hosts have local storage (for performance), and clustered hosts use a SAN to allow HA and automatic load balancing. The OpenNebula controler use its own local storage so it can manage both clustered and standalone hosts without specific configuration.

To speedup the deployent time, these drivers include a tar mode, configurable in the file `cxmrc`. In this mode, only datas (and maybe zipped) are transfered to the node, not the entire empty disk.


### Why oned frontend is not connected to the SAN ?

Because, to access to the SAN, the machine must be a member of the clvmd cluster, and it must handle some fencing to properly respond to a failure without damaging datas. Within cxm, fencing is directly handled by cxm daemon. As the one frontend is not a xen server, it cannot be part of the cxm cluster.

Cxmd and clvmd clusters have to be configured with exactly the same nodes.

Prerequisite
------------

* You need a functionnal OpenNebula installation and a cxm cluster already working.
* All xen hosts must be able to make ssh connection to OpenNebula frontend as `oneadmin` without password.
* The `xpath` perl utility is needed on the OpenNebula frontend.
* The package `python-yaml` is needed on all xen hosts.
* User `oneadmin` on each host must have special sudo access. Example of sudoers entries :

    oneadmin    ALL=(ALL) NOPASSWD: ALL
    Defaults:oneadmin env_keep+="HOME"
    Defaults:oneadmin !requiretty

* The system datastore /var/lib/one/datastores/0 must be shared between hosts (but not with the frontend). You can dedicate one LV on the SAN, with GFS2. Yyou can also use NFS, but as you are using cxm, you surely have cman and clvmd already running, so GFS2 is a good choice.
This datastore is not used to store images, as we use LVM block devices, but is needed to share some configuration files and links. A few gigabytes is enough.

Installation 
------------

Just copy `cxmrc`, tm/ and vmm/ in the directory /var/lib/one/remotes/ on the OpenNebula frontend.
Also copy one-migrate script in /usr/local/sbin/ on each xen host. Do not forget to set execution perms on it.

Configuration
-------------

* Cxm drivers

Edit the file /var/lib/one/remotes/cxmrc and adapt variables `VG_NAME` and `VM_FQDN_TEMPLATE` to your configuration.

* Transfert manager (TM\_MAD)

Add the cxm transfer manager in the /etc/one/oned.conf file. Example :

    TM_MAD = [
    executable = "one_tm",
    arguments  = "-t 15 -d dummy,lvm,shared,qcow2,ssh,vmware,iscsi,cxm" ]


* Virtual machine manager (VM\_MAD)

Add the cxm vmm in the /etc/one/oned.conf file :

    VM_MAD = [
    name       = "vmm_cxm",
    executable = "one_vmm_exec",
    arguments  = "-t 15 -r 0 cxm",
    default    = "vmm_exec/vmm_exec_xen.conf",
    type       = "xen" ]

Change the default disk driver for `phy:` in `/etc/one/vmm_exec/vmm_exec_xen.conf` :

    DISK = [ driver = "phy:" ]

* Information Manager (IM\_MAD)

Just keep the xen default manager.

* Datastore

For each datastore, use :

    DS_MAD="fs"
    TM_MAD="cxm"

* Hosts

To add a serveur, use :

    onehost create my_server --im im_xen --vm vmm_cxm --net dummy

* cxm

Change the post-migration hook in the cxm configuration to use one-migrate script. Example in /etc/xen/cxm.conf :

    POST_MIGRATION_HOOK="/usr/local/sbin/one-migrate"

And update this script to fill the variable `ONE_HOST` with the hostname of your OpenNebula frontend.

Template options
----------------

Some storage options can be set directly in the image template :

* `SIZE` : Fix the size of the logical volume. This use LVM syntax. If not set, will use the `DEFAULT_LV_SIZE` defined in `cxmrc`. Example:

    SIZE="8G"

* `FSTYPE` : Set the filesystem type for mkfs. If not set, will use the `DEFAULT_FSTYPE` defined in `cxmrc`. Example:

	FSTYPE="ext4"

Limits
------

Operations `save` and `restore` are not (yet) supported when in cluster.
Disk hotplug is not supported too.

Versions
--------

This code has been succesfully tested with OpenNebula 3.6 and 3.8.1 on Centos.


