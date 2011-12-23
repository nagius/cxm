SVNWatcher
==========

SVNWatcher is a small daemon which syncronize vm configuration files within a cxm cluster, using Subversion an Inotify.

In order to run it, you have to set-up a dedicated repository on a SVN server and run a checkout into /etx/xen/vm/ on each node of the cluster. Then SVNWatcher will automatically commit all modifications made in this directory and update all others nodes.

In case of rollback or other corrections on the local repopsitory, you will have to play manually with svn.

Runtime:
--------

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

