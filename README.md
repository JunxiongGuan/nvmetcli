
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

You can load the default config that exports the first NVMe device and
the first ramdisk by running "nvmetcli restore nvmet.json".  The default
config is stored in /etc/nvmet.json.  You can also edit the json file
directly.

To get started with the interactive mode start nvmetcli without
arguments.  Then in the nvmetcli prompt type:

# 
# Create a subsystem.  If you do not specify a name a NQN will be generated.
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
# Create a new namespace.  If you do not specify a namespace ID the fist
# unused one will be used.
#

...> cd namespaces 
...> create 1
...> cd 1
...> set device path=/dev/ram1
...> enable


Testing
-------

nvmetcli comes with a testsuite that tests itself and the kernel configfs
interface for the NVMe target.  To run it make sure you have nose2 and
the coverage plugin for it installed and simple run 'make test'.
