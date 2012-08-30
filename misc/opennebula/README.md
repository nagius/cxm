OpenNebula 3.6 drivers for cxm
==============================

Concepts
--------

TODO

Prerequiste
-----------

You need a functionnal OpenNebula installation and a cxm cluster.

All xen hosts must be able to make ssh connection with the user oneadmin without password.

You need the 'xpath' utility in you path on the OpenNebula host.


Installation 
------------

Just copy cxmrc, tm/ and vmm/ in the directory /var/lib/one/remotes/ of the OpenNebula host.


Configuration
-------------

 - Transfert manager (TM_MAD)

Add the cxm transfer manager in the /etc/one/oned.conf file :

Example :

TM_MAD = [
    executable = "one_tm",
    arguments  = "-t 15 -d dummy,lvm,shared,qcow2,ssh,vmware,iscsi,cxm" ]


 - Virtual machine manager (VM_MAD)

Add the cxm vmm in the /etc/one/oned.conf file :

VM_MAD = [
    name       = "vmm_cxm",
    executable = "one_vmm_exec",
    arguments  = "-t 15 -r 0 cxm",
    default    = "vmm_exec/vmm_exec_xen.conf",
    type       = "xen" ]

Change the default disk driver for 'phy:' in /etc/one/vmm_exec/vmm_exec_xen.conf :

DISK   = [ driver = "phy:" ]

 - Information Manager (IM_MAD)

Just keep the xen default manager.

 - Datastore

 For each datastore, use :

  DS_MAD="fs"
  TM_MAD="cxm"

 - Hosts

To add a serveur, use :

onehost create my_server --im im_xen --vm vmm_cxm --net dummy




