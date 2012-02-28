Documentation of cxm daemon
===========================

In a cxm cluster, each node, or cxmd instance, may have one or two roles: slave and master. To avoid split-brain and STONITH deathmatch, all failover and fencing decisions are only taken by the master, which is unique on a given cluster.

Each node is a slave, but only one of them is also the master. The master is choosen by a random election mechanism. If the master die, slaves will choose another master.

A node with only a slave running is called "passive".
The node with both master and slave running is called "active".


Behavior
--------

List of diagrams explaining cxmd behavior :

* usecase1.dia : Startup of a node
* usecase2.dia : Standard run
* usecase3.dia : Shutdown a node
* usecase4.dia : Lost one or many slaves
* usecase5.dia : Lost all nodes
* usecase6.dia : Lost disk heartbeats
* usecase7.dia : Lost master
* usecase8.dia : Split brain
* usecase9.dia : Election
* states.dia   : States charts


Prerequistes:
-------------

* The heartbeat system needs a shared storage over a SAN, like a rack disk with a Fibre Channel or a SAS network. All ethernet-based solutions, such as iSCSI, NFS or NBD should be avoided, as they rely on an ethernet network, and thus cannot be used to detect when a network partition splits the cluster.
* All virtual machines have to be named within Xen with their FQDN, with a valid DNS record.
* All VM configuration files should be named with the FQDN of the corresponding virtual machine.
* All files in the VM configuration directory (/etc/xen/vm) must contain valid xen syntax, where disk devices must exist. Any incorrect file will put the cxmd daemon in panic mode.
* The VM configuration directory (/etc/xen/vm) must be shared and synchronized between all nodes. You can use SVNWatcher to do this.
* All servers, both physical and virtual, must be configured to answer a ping request that can be sent from anywhere in the cluster. fping is used to check whether virtual machines are alive.
* All disk devices used by virtual machines must be defined as LVM logical volumes, using the 'phy:/' prefix. tap or file devices are not supported.
* All nodes must be allowed to connect to each other with SSH without requesting a password. You need to deploy SSH keys over all nodes and to accept all servers keys.
* Of course, live migration must be operational between all nodes.


Xend Configuration:
------------------

Cxm need an access to xen API to manage vm. It use both LegacyAPI and new XEN-API, with TCP and unix socket.

You have to change the folowing parameters in /etx/xen/xend.conf:

`(xend-relocation-server yes)
(xen-api-server ((9363 'none') (unix)))
(xend-tcp-xmlrpc-server yes)
(xend-tcp-xmlrpc-server-address '')`



Error handling
--------------

Cxmd has been designed to survive to any possible errors. It would normally never stop completely.

If a serious error occurs, or if there is not enough informations to take the right decision (ex: fencing), cxm daemon will drop into the so called 'Panic mode'. In this state, cxmd take no more decision and wait for a human intervention. Only election stuff and master failover are still running. You cannot add a new node.

To recover from this state, you have to :

1. Check the logs to find the root cause. File /var/log/cxm/cxmd.log is a good start.
2. Fix the problem and cleanup the system
3. Run 'cxmd_ctl --recover' to switch back to normal mode.


Configuration file modification
-------------------------------

There is no way to reload the configuration file (/etc/xen/cxm.conf). If you want to change a value, you have to :

1. Shutdown all cxmd daemon
2. Change the configuration file
3. Copy this file on all nodes
4. Restart all cxmd daemon

During this operation, failover and administration stuff with cxm will be unavailable, but vm will be still running.


Clock restriction
-----------------

Cxm is able to handle a time difference between nodes, but using a NTP daemon is recommended.
Nevertheless, time leap bigger than 5 seconds will trigger failover an may fence nodes. Do not manually set the date while runing cxmd !


Messages 
--------

### Protocols:

Two kind of messages are used internally by cxmd, UDP for heartbeat and elections; RPC for actions and resquest.
RPC are connected via TCP for remote action and Unix socket for local request.

* UDP messages use hash tables encoded in JSON and gzipped
* RPC messages use native Twisted RPC named PerspectiveBroker

### Messages lists :

Source       | Destination | Type      | Message
-------------|-------------|-----------|------------------
Alone node   | Master      | RPC       | Join request
Leaving node | Master      | RPC       | Quit request
Slave        | Slaves      | Broadcast | Election request
Slaves       | Slaves      | Broadcast | Election vote
Slaves       | Master      | Unicast   | Slave heartbeat
Master       | Slaves      | Broadcast | Master heartbeat


Heartbeat disk
--------------

The heartbeat disk is use as a second channel to propagate timestamps between nodes.
It must be a partition or a logical volume on the shared storage, and all nodes must have simultaneous read/write access as a raw block device.

The command cxmd_ctl --format will initialize it with the following struture :

Block 1       | Block 2        |
--------------|----------------|
Magic number  | Number of node |
Node name 1   | Timestamp      |
Node name 2   | Timestamp      |
Node name X   | Timestamp      |
0             | 0              |

Each cell is a 4k-block.

