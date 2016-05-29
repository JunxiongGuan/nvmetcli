
nvmetcli
========

This contains the NVMe target admin tool "nvmetcli".  It can either be
used interactively by invoking it without arguments, or it can be used
to save, restore or clear the current NVMe target configuration.


Installation
------------

Please install the configshell-fb package from
https://github.com/agrover/configshell-fb first.

Nvmetcli can be run directly from the source directory or installed
using setup.py.


Usage
-----

Make sure to run nvmetcli as root, the nvmet module is loaded and
configfs is mounted on /sys/kernel/config, using:

	mount -t configs none /sys/kernel/config

To get started with the interactive mode start nvmetcli without
arguments.  Then in the nvmetcli prompt type:

# 
# Create a subsystem.  If you do not specify a name a NQN will be generated,
# which is probably the best choice, we we don't do it here as the name
# would be random
#

> cd /subsystems
...> create testnqn

#
# Add access for a specific NVMe Host by it's NQN:
#
...> cd /hosts
...> create hostnqn
...> cd /subsystems/testnqn/allowed_hosts/
...> create hostnqn

#
# Alternatively this allows any host to connect to the subsystsem.  Only
# use this in tightly controller environments:
#
...> cd /subsystems/testnqn/
...> set attr allow_any_host=1

#
# Create a port through which access is allowed, and enable access to
# a subsystem through it.
#
# This creates a trivial loopback port that can be used with nvme-loop on
# the same machine:
#
...> cd /ports/
...> create 1
...> cd 1/
...> set addr trtype=loop
...> cd subsystems/
...> create testnqn

#
# Create a new namespace.  If you do not specify a namespace ID the fist
# unused one will be used.
#

...> cd namespaces 
...> create 1
...> cd 1
...> set device path=/dev/nvme0n1
...> enable

#
# Or create a RDMA (IB, RoCE, iWarp) port using IPv4 addressing, 4420 is the
# IANA assigned port for NVMe over Fabrics using RDMA:
#
...> cd /ports/
...> create 2
...> cd 2/
...> set addr trtype=rdma
...> set addr adrfam=ipv4
...> set addr traddr=192.168.6.68
...> set addr trsvcid=4420
...> cd subsystems/
...> create testnqn


Saving and restoring the configuration
--------------------------------------

The saveconfig and restoreconfig commands inside nvmetcli save and restore
the current configuration, but you can also invoke these commands for the
command line using the load and restore arguments to nvmetcli.  Without
an additional file name these operate on /etc/nvmet.json.

To load the loop + explicit host version above do the following:

  ./nvmetcli load loop.json

Or to load the rdma + no host authentication version do the following
after you've ensured that the IP address in rdma.json fits your setup:

  ./nvmetcli load rdma.json

You can also edit the json files directly.


Testing
-------

nvmetcli comes with a testsuite that tests itself and the kernel configfs
interface for the NVMe target.  To run it make sure you have nose2 and
the coverage plugin for it installed and simple run 'make test'.
