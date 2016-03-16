
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
/subsystems> create testnqn

#
# Create a new namespace.  If you do not specify a namespace ID the fist
# unused one will be used.
#

/subsystems> cd testnqn/
/subsystems/testnqn> cd namespaces 
/subsystems/testnqn/namespaces> create 1
/subsystems/testnqn/namespaces> cd 1
/subsystems/t.../namespaces/1> set device path=/dev/ram1
