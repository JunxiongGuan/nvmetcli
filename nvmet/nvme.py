'''
Implements access to the NVMe target configfs hierarchy

Copyright (c) 2011-2013 by Datera, Inc.
Copyright (c) 2011-2014 by Red Hat, Inc.
Copyright (c) 2016 by HGST, a Western Digital Company.

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations
under the License.
'''

import os
import stat
import uuid
import json
from glob import iglob as glob

DEFAULT_SAVE_FILE = '/etc/nvmet/config.json'


class CFSError(Exception):
    '''
    Generic slib error.
    '''
    pass


class CFSNotFound(CFSError):
    '''
    The underlying configfs object does not exist. Happens when
    calling methods of an object that is instantiated but have
    been deleted from congifs, or when trying to lookup an
    object that does not exist.
    '''
    pass


class CFSNode(object):

    configfs_dir = '/sys/kernel/config/nvmet'

    def __init__(self):
        self._path = self.configfs_dir
        self._enable = None
        self.attr_groups = []

    def __eq__(self, other):
        return self._path == other._path

    def __ne__(self, other):
        return self._path != other._path

    def _get_path(self):
        return self._path

    def _create_in_cfs(self, mode):
        '''
        Creates the configFS node if it does not already exist, depending on
        the mode.
        any -> makes sure it exists, also works if the node already does exist
        lookup -> make sure it does NOT exist
        create -> create the node which must not exist beforehand
        '''
        if mode not in ['any', 'lookup', 'create']:
            raise CFSError("Invalid mode: %s" % mode)
        if self.exists and mode == 'create':
            raise CFSError("This %s already exists in configFS" %
                           self.__class__.__name__)
        elif not self.exists and mode == 'lookup':
            raise CFSNotFound("No such %s in configfs: %s" %
                              (self.__class__.__name__, self.path))

        if not self.exists:
            try:
                os.mkdir(self.path)
            except:
                raise CFSError("Could not create %s in configFS" %
                               self.__class__.__name__)
        self.get_enable()

    def _exists(self):
        return os.path.isdir(self.path)

    def _check_self(self):
        if not self.exists:
            raise CFSNotFound("This %s does not exist in configFS" %
                              self.__class__.__name__)

    def list_attrs(self, group, writable=None):
        '''
        @param group: The attribute group
        @param writable: If None (default), returns all attributes, if True,
        returns read-write attributes, if False, returns just the read-only
        attributes.
        @type writable: bool or None
        @return: A list of existing attribute names as strings.
        '''
        self._check_self()

        names = [os.path.basename(name).split('_', 1)[1]
                 for name in glob("%s/%s_*" % (self._path, group))
                     if os.path.isfile(name)]

        if writable is True:
            names = [name for name in names
                     if self._attr_is_writable(group, name)]
        elif writable is False:
            names = [name for name in names
                     if not self._attr_is_writable(group, name)]

        names.sort()
        return names

    def _attr_is_writable(self, group, name):
        s = os.stat("%s/%s_%s" % (self._path, group, name))
        return s[stat.ST_MODE] & stat.S_IWUSR

    def set_attr(self, group, attribute, value):
        '''
        Sets the value of a named attribute.
        The attribute must exist in configFS.
        @param group: The attribute group
        @param attribute: The attribute's name.
        @param value: The attribute's value.
        @type value: string
        '''
        self._check_self()
        path = "%s/%s_%s" % (self.path, str(group), str(attribute))

        if not os.path.isfile(path):
            raise CFSError("Cannot find attribute: %s" % path)

        if self._enable:
            raise CFSError("Cannot set attribute while %s is enabled" %
                           self.__class__.__name__)

        try:
            with open(path, 'w') as file_fd:
                file_fd.write(str(value))
        except Exception as e:
            raise CFSError("Cannot set attribute %s: %s" % (path, e))

    def get_attr(self, group, attribute):
        '''
        Gets the value of a named attribute.
        @param group: The attribute group
        @param attribute: The attribute's name.
        @return: The named attribute's value, as a string.
        '''
        self._check_self()
        path = "%s/%s_%s" % (self.path, str(group), str(attribute))
        if not os.path.isfile(path):
            raise CFSError("Cannot find attribute: %s" % path)

        with open(path, 'r') as file_fd:
            return file_fd.read().strip()

    def get_enable(self):
        self._check_self()
        path = "%s/enable" % self.path
        if not os.path.isfile(path):
            return None

        with open(path, 'r') as file_fd:
            self._enable = int(file_fd.read().strip())
        return self._enable

    def set_enable(self, value):
        self._check_self()
        path = "%s/enable" % self.path

        if not os.path.isfile(path) or self._enable is None:
            raise CFSError("Cannot enable %s" % self.path)

        try:
            with open(path, 'w') as file_fd:
                file_fd.write(str(value))
        except Exception as e:
            raise CFSError("Cannot enable %s: %s (%s)" %
                           (self.path, e, value))
        self._enable = value

    def delete(self):
        '''
        If the underlying configFS object does not exist, this method does
        nothing. If the underlying configFS object exists, this method attempts
        to delete it.
        '''
        if self.exists:
            os.rmdir(self.path)

    path = property(_get_path,
                    doc="Get the configFS object path.")
    exists = property(_exists,
            doc="Is True as long as the underlying configFS object exists. "
                      + "If the underlying configFS objects gets deleted "
                      + "either by calling the delete() method, or by any "
                      + "other means, it will be False.")

    def dump(self):
        d = {}
        for group in self.attr_groups:
            a = {}
            for i in self.list_attrs(group, writable=True):
                a[str(i)] = self.get_attr(group, i)
            d[str(group)] = a
        if self._enable is not None:
            d['enable'] = self._enable
        return d

    def _setup_attrs(self, attr_dict, err_func):
        for group in self.attr_groups:
            for name, value in attr_dict.get(group, {}).iteritems():
                try:
                    self.set_attr(group, name, value)
                except CFSError as e:
                    err_func(str(e))
        enable = attr_dict.get('enable')
        if enable is not None:
            self.set_enable(enable)


class Root(CFSNode):
    def __init__(self):
        super(Root, self).__init__()

        if not os.path.isdir(self.configfs_dir):
            self._modprobe('nvmet')

        if not os.path.isdir(self.configfs_dir):
            raise CFSError("%s does not exist.  Giving up." %
                           self.configfs_dir)

        self._path = self.configfs_dir
        self._create_in_cfs('lookup')

    def _modprobe(self, modname):
        try:
            from kmodpy import kmod

            try:
                kmod.Kmod().modprobe(modname, quiet=True)
            except kmod.KmodError:
                pass
        except ImportError:
            pass

    def _list_subsystems(self):
        self._check_self()

        for d in os.listdir("%s/subsystems/" % self._path):
            yield Subsystem(d, 'lookup')

    subsystems = property(_list_subsystems,
                          doc="Get the list of Subsystems.")

    def _list_ports(self):
        self._check_self()

        for d in os.listdir("%s/ports/" % self._path):
            yield Port(d, 'lookup')

    ports = property(_list_ports,
                doc="Get the list of Ports.")

    def _list_hosts(self):
        self._check_self()

        for h in os.listdir("%s/hosts/" % self._path):
            yield Host(h, 'lookup')

    hosts = property(_list_hosts,
                     doc="Get the list of Hosts.")

    def save_to_file(self, savefile=None):
        '''
        Write the configuration in json format to a file.
        '''
        if savefile:
            savefile = os.path.expanduser(savefile)
        else:
            savefile = DEFAULT_SAVE_FILE

        with open(savefile + ".temp", "w+") as f:
            os.fchmod(f.fileno(), stat.S_IRUSR | stat.S_IWUSR)
            f.write(json.dumps(self.dump(), sort_keys=True, indent=2))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
            f.close()

        os.rename(savefile + ".temp", savefile)

    def clear_existing(self):
        '''
        Remove entire current configuration.
        '''

        for p in self.ports:
            p.delete()
        for s in self.subsystems:
            s.delete()
        for h in self.hosts:
            h.delete()

    def restore(self, config, clear_existing=False, abort_on_error=False):
        '''
        Takes a dict generated by dump() and reconfigures the target to match.
        Returns list of non-fatal errors that were encountered.
        Will refuse to restore over an existing configuration unless
        clear_existing is True.
        '''
        if clear_existing:
            self.clear_existing()
        else:
            if any(self.subsystems):
                raise CFSError("subsystems present, not restoring")

        errors = []

        if abort_on_error:
            def err_func(err_str):
                raise CFSError(err_str)
        else:
            def err_func(err_str):
                errors.append(err_str + ", skipped")

        # Create the hosts first because the subsystems reference them
        for index, t in enumerate(config.get('hosts', [])):
            if 'nqn' not in t:
                err_func("'nqn' not defined in host %d" % index)
                continue

            Host.setup(t, err_func)

        for index, t in enumerate(config.get('subsystems', [])):
            if 'nqn' not in t:
                err_func("'nqn' not defined in subsystem %d" % index)
                continue

            Subsystem.setup(t, err_func)

        for index, t in enumerate(config.get('ports', [])):
            if 'portid' not in t:
                err_func("'portid' not defined in port %d" % index)
                continue

            Port.setup(self, t, err_func)

        return errors

    def restore_from_file(self, savefile=None, clear_existing=True,
                          abort_on_error=False):
        '''
        Restore the configuration from a file in json format.
        Returns a list of non-fatal errors. If abort_on_error is set,
          it will raise the exception instead of continuing.
        '''
        if savefile:
            savefile = os.path.expanduser(savefile)
        else:
            savefile = DEFAULT_SAVE_FILE

        with open(savefile, "r") as f:
            config = json.loads(f.read())
            return self.restore(config, clear_existing=clear_existing,
                                abort_on_error=abort_on_error)

    def dump(self):
        d = super(Root, self).dump()
        d['subsystems'] = [s.dump() for s in self.subsystems]
        d['ports'] = [p.dump() for p in self.ports]
        d['hosts'] = [h.dump() for h in self.hosts]
        return d


class Subsystem(CFSNode):
    '''
    This is an interface to a NVMe Subsystem in configFS.
    A Subsystem is identified by its NQN.
    '''

    def __repr__(self):
        return "<Subsystem %s>" % self.nqn

    def __init__(self, nqn=None, mode='any'):
        '''
        @param nqn: The Subsystems' NQN.
            If no NQN is specified, one will be generated.
        @type nqn: string
        @param mode:An optional string containing the object creation mode:
            - I{'any'} means the configFS object will be either looked up
              or created.
            - I{'lookup'} means the object MUST already exist configFS.
            - I{'create'} means the object must NOT already exist in configFS.
        @type mode:string
        @return: A Subsystem object.
        '''
        super(Subsystem, self).__init__()

        if nqn is None:
            if mode == 'lookup':
                raise CFSError("Need NQN for lookup")
            nqn = self._generate_nqn()

        self.nqn = nqn
        self.attr_groups = ['attr']
        self._path = "%s/subsystems/%s" % (self.configfs_dir, nqn)
        self._create_in_cfs(mode)

    def _generate_nqn(self):
        prefix = "nqn.2014-08.org.nvmexpress:NVMf:uuid"
        name = str(uuid.uuid4())
        return "%s:%s" % (prefix, name)

    def delete(self):
        '''
        Recursively deletes a Subsystem object.
        This will delete all attached Namespace objects and then the
        Subsystem itself.
        '''
        self._check_self()
        for ns in self.namespaces:
            ns.delete()
        for h in self.allowed_hosts:
            self.remove_allowed_host(h)
        super(Subsystem, self).delete()

    def _list_namespaces(self):
        self._check_self()
        for d in os.listdir("%s/namespaces/" % self._path):
            yield Namespace(self, int(d), 'lookup')

    namespaces = property(_list_namespaces,
                          doc="Get the list of Namespaces for the Subsystem.")

    def _list_allowed_hosts(self):
        return [os.path.basename(name)
                for name in os.listdir("%s/allowed_hosts/" % self._path)]

    allowed_hosts = property(_list_allowed_hosts,
                             doc="Get the list of Allowed Hosts for the Subsystem.")

    def add_allowed_host(self, nqn):
        '''
        Enable access for the host identified by I{nqn} to the Subsystem
        '''
        try:
            os.symlink("%s/hosts/%s" % (self.configfs_dir, nqn),
                       "%s/allowed_hosts/%s" % (self._path, nqn))
        except Exception as e:
            raise CFSError("Could not symlink %s in configFS: %s" % (nqn, e))

    def remove_allowed_host(self, nqn):
        '''
        Disable access for the host identified by I{nqn} to the Subsystem
        '''
        try:
            os.unlink("%s/allowed_hosts/%s" % (self._path, nqn))
        except Exception as e:
            raise CFSError("Could not unlink %s in configFS: %s" % (nqn, e))

    @classmethod
    def setup(cls, t, err_func):
        '''
        Set up Subsystem objects based upon t dict, from saved config.
        Guard against missing or bad dict items, but keep going.
        Call 'err_func' for each error.
        '''

        if 'nqn' not in t:
            err_func("'nqn' not defined for Subsystem")
            return

        try:
            s = Subsystem(t['nqn'])
        except CFSError as e:
            err_func("Could not create Subsystem object: %s" % e)
            return

        for ns in t.get('namespaces', []):
            Namespace.setup(s, ns, err_func)
        for h in t.get('allowed_hosts', []):
            s.add_allowed_host(h)

        s._setup_attrs(t, err_func)

    def dump(self):
        d = super(Subsystem, self).dump()
        d['nqn'] = self.nqn
        d['namespaces'] = [ns.dump() for ns in self.namespaces]
        d['allowed_hosts'] = self.allowed_hosts
        return d


class Namespace(CFSNode):
    '''
    This is an interface to a NVMe Namespace in configFS.
    A Namespace is identified by its parent Subsystem and Namespace ID.
    '''

    MAX_NSID = 8192

    def __repr__(self):
        return "<Namespace %d>" % self.nsid

    def __init__(self, subsystem, nsid=None, mode='any'):
        '''
        @param subsystem: The parent Subsystem object
        @param nsid: The Namespace identifier
            If no nsid is specified, the next free one will be used.
        @type nsid: int
        @param mode:An optional string containing the object creation mode:
            - I{'any'} means the configFS object will be either looked up
              or created.
            - I{'lookup'} means the object MUST already exist configFS.
            - I{'create'} means the object must NOT already exist in configFS.
        @type mode:string
        @return: A Namespace object.
        '''
        super(Namespace, self).__init__()

        if not isinstance(subsystem, Subsystem):
            raise CFSError("Invalid parent class")

        if nsid is None:
            if mode == 'lookup':
                raise CFSError("Need NSID for lookup")

            nsids = [n.nsid for n in subsystem.namespaces]
            for index in xrange(1, self.MAX_NSID + 1):
                if index not in nsids:
                    nsid = index
                    break
            if nsid is None:
                raise CFSError("All NSIDs 1-%d in use" % self.MAX_NSID)
        else:
            nsid = int(nsid)
            if nsid < 1 or nsid > self.MAX_NSID:
                raise CFSError("NSID must be 1 to %d" % self.MAX_NSID)

        self.attr_groups = ['device']
        self._subsystem = subsystem
        self._nsid = nsid
        self._path = "%s/namespaces/%d" % (self.subsystem.path, self.nsid)
        self._create_in_cfs(mode)

    def _get_subsystem(self):
        return self._subsystem

    def _get_nsid(self):
        return self._nsid

    subsystem = property(_get_subsystem,
                         doc="Get the parent Subsystem object.")
    nsid = property(_get_nsid, doc="Get the NSID as an int.")

    @classmethod
    def setup(cls, subsys, n, err_func):
        '''
        Set up a Namespace object based upon n dict, from saved config.
        Guard against missing or bad dict items, but keep going.
        Call 'err_func' for each error.
        '''

        if 'nsid' not in n:
            err_func("'nsid' not defined for Namespace")
            return

        try:
            ns = Namespace(subsys, n['nsid'])
        except CFSError as e:
            err_func("Could not create Namespace object: %s" % e)
            return

        ns._setup_attrs(n, err_func)

    def dump(self):
        d = super(Namespace, self).dump()
        d['nsid'] = self.nsid
        return d


class Port(CFSNode):
    '''
    This is an interface to a NVMe Port in configFS.
    '''

    MAX_PORTID = 8192

    def __repr__(self):
        return "<Port %d>" % self.portid

    def __init__(self, portid, mode='any'):
        super(Port, self).__init__()

        self.attr_groups = ['addr']
        self._portid = int(portid)
        self._path = "%s/ports/%d" % (self.configfs_dir, self._portid)
        self._create_in_cfs(mode)

    def _get_portid(self):
        return self._portid

    portid = property(_get_portid, doc="Get the Port ID as an int.")

    def _list_subsystems(self):
        return [os.path.basename(name)
                for name in os.listdir("%s/subsystems/" % self._path)]

    subsystems = property(_list_subsystems,
                          doc="Get the list of Subsystem for this Port.")

    def add_subsystem(self, nqn):
        '''
        Enable access to the Subsystem identified by I{nqn} through this Port.
        '''
        try:
            os.symlink("%s/subsystems/%s" % (self.configfs_dir, nqn),
                       "%s/subsystems/%s" % (self._path, nqn))
        except Exception as e:
            raise CFSError("Could not symlink %s in configFS: %s" % (nqn, e))

    def remove_subsystem(self, nqn):
        '''
        Disable access to the Subsystem identified by I{nqn} through this Port.
        '''
        try:
            os.unlink("%s/subsystems/%s" % (self._path, nqn))
        except Exception as e:
            raise CFSError("Could not unlink %s in configFS: %s" % (nqn, e))

    def delete(self):
        '''
        Recursively deletes a Port object.
        '''
        self._check_self()
        for s in self.subsystems:
            self.remove_subsystem(s)
        for r in self.referrals:
            r.delete()
        super(Port, self).delete()

    def _list_referrals(self):
        self._check_self()
        for d in os.listdir("%s/referrals/" % self._path):
            yield Referral(self, d, 'lookup')

    referrals = property(_list_referrals,
                         doc="Get the list of Referrals for this Port.")

    @classmethod
    def setup(cls, root, n, err_func):
        '''
        Set up a Namespace object based upon n dict, from saved config.
        Guard against missing or bad dict items, but keep going.
        Call 'err_func' for each error.
        '''

        if 'portid' not in n:
            err_func("'portid' not defined for Port")
            return

        try:
            port = Port(n['portid'])
        except CFSError as e:
            err_func("Could not create Port object: %s" % e)
            return

        port._setup_attrs(n, err_func)
        for s in n.get('subsystems', []):
            port.add_subsystem(s)
        for r in n.get('referrals', []):
            Referral.setup(port, r, err_func)

    def dump(self):
        d = super(Port, self).dump()
        d['portid'] = self.portid
        d['subsystems'] = self.subsystems
        d['referrals'] = [r.dump() for r in self.referrals]
        return d


class Referral(CFSNode):
    '''
    This is an interface to a NVMe Referral in configFS.
    '''

    def __repr__(self):
        return "<Referral %d>" % self.name

    def __init__(self, port, name, mode='any'):
        super(Referral, self).__init__()

        if not isinstance(port, Port):
            raise CFSError("Invalid parent class")

        self.attr_groups = ['addr']
        self.port = port
        self._name = name
        self._path = "%s/referrals/%s" % (self.port.path, self._name)
        self._create_in_cfs(mode)

    def _get_name(self):
        return self._name

    name = property(_get_name, doc="Get the Referral name.")

    @classmethod
    def setup(cls, port, n, err_func):
        '''
        Set up a Referral based upon n dict, from saved config.
        Guard against missing or bad dict items, but keep going.
        Call 'err_func' for each error.
        '''

        if 'name' not in n:
            err_func("'name' not defined for Referral")
            return

        try:
            r = Referral(port, n['name'])
        except CFSError as e:
            err_func("Could not create Referral object: %s" % e)
            return

        r._setup_attrs(n, err_func)

    def dump(self):
        d = super(Referral, self).dump()
        d['name'] = self.name
        return d


class Host(CFSNode):
    '''
    This is an interface to a NVMe Host in configFS.
    A Host is identified by its NQN.
    '''

    def __repr__(self):
        return "<Host %s>" % self.nqn

    def __init__(self, nqn, mode='any'):
        '''
        @param nqn: The Hosts's NQN.
        @type nqn: string
        @param mode:An optional string containing the object creation mode:
            - I{'any'} means the configFS object will be either looked up
              or created.
            - I{'lookup'} means the object MUST already exist configFS.
            - I{'create'} means the object must NOT already exist in configFS.
        @type mode:string
        @return: A Host object.
        '''
        super(Host, self).__init__()

        self.nqn = nqn
        self._path = "%s/hosts/%s" % (self.configfs_dir, nqn)
        self._create_in_cfs(mode)

    @classmethod
    def setup(cls, t, err_func):
        '''
        Set up Host objects based upon t dict, from saved config.
        Guard against missing or bad dict items, but keep going.
        Call 'err_func' for each error.
        '''

        if 'nqn' not in t:
            err_func("'nqn' not defined for Host")
            return

        try:
            h = Host(t['nqn'])
        except CFSError as e:
            err_func("Could not create Host object: %s" % e)
            return

    def dump(self):
        d = super(Host, self).dump()
        d['nqn'] = self.nqn
        return d


def _test():
    from doctest import testmod
    testmod()

if __name__ == "__main__":
    _test()
