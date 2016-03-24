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

DEFAULT_SAVE_FILE = '/etc/nvmet.json'


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
        self._attr_groups = []

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
            raise CFSError("This %s already exists in configFS"
                              % self.__class__.__name__)
        elif not self.exists and mode == 'lookup':
            raise CFSNotFound("No such %s in configfs: %s"
                                 % (self.__class__.__name__, self.path))

        if not self.exists:
            try:
                os.mkdir(self.path)
            except:
                raise CFSError("Could not create %s in configFS"
                                  % self.__class__.__name__)

    def _exists(self):
        return os.path.isdir(self.path)

    def _check_self(self):
        if not self.exists:
            raise CFSNotFound("This %s does not exist in configFS"
                                 % self.__class__.__name__)

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

        names = [os.path.basename(name).split('_')[1]
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
        for group in self._attr_groups:
            a = {}
            for i in self.list_attrs(group, writable=True):
                a[str(i)] = self.get_attr(group, i)
            d[str(group)] = a
        return d

    def _setup_attrs(self, attr_dict, err_func):
        for group in self._attr_groups:
            for name, value in attr_dict.get(group, {}).iteritems():
                try:
                    self.set_attr(group, name, value)
                except CFSError as e:
                    err_func(str(e))


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
            os.fsync(f.fileno())

        os.rename(savefile + ".temp", savefile)

    def clear_existing(self):
        '''
        Remove entire current configuration.
        '''

        for s in self.subsystems:
            s.delete()

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

        for index, t in enumerate(config.get('subsystems', [])):
            if 'nqn' not in t:
                err_func("'nqn' not defined in subsystem %d" % index)
                continue

            Subsystem.setup(t, err_func)

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
        return d


class Subsystem(CFSNode):
    '''
    This is an interface to a NVMe Subsystem in configFS.
    A Subsystem is identified by its NQN.
    '''

    def __repr__(self):
        return "<Namespace %s>" % self.nqn

    def __init__(self, nqn=None, mode='any'):
        '''
        @param nqn: The optional Target's NQN.
            If no NQN is specified, one will be generated.
        @type nqn: string
        @param mode:An optionnal string containing the object creation mode:
            - I{'any'} means the configFS object will be either looked up
              or created.
            - I{'lookup'} means the object MUST already exist configFS.
            - I{'create'} means the object must NOT already exist in configFS.
        @type mode:string
        @return: A Subsystem object.
        '''
        super(Subsystem, self).__init__()

        if nqn is None:
            nqn = self._generate_nqn()

        self.nqn = nqn
        self._path = "%s/subsystems/%s" % (self.configfs_dir, nqn)
        self._create_in_cfs(mode)

    def _generate_nqn(self):
        prefix = "nqn.2014-08.org.nvmexpress:NVMf:uuid"
        name = str(uuid.uuid4())
        return "%s:%s" % (prefix, name)

    def _list_namespaces(self):
        self._check_self()
        for d in os.listdir("%s/namespaces/" % self._path):
            yield Namespace(self, int(d), 'lookup')

    def delete(self):
        '''
        Recursively deletes a Subsystems object.
        This will delete all attached Namespace objects and then the
        Subsystem itself.
        '''
        self._check_self()
        for ns in self.namespaces:
            ns.delete()
        super(Subsystem, self).delete()

    namespaces = property(_list_namespaces,
                doc="Get the list of Namespaces for the Subsystem.")

    @classmethod
    def setup(cls, t, err_func):
        '''
        Set up Subsystems objects based upon t dict, from saved config.
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

    def dump(self):
        d = super(Subsystem, self).dump()
        d['nqn'] = self.nqn
        d['namespaces'] = [ns.dump() for ns in self.namespaces]
        return d


class Namespace(CFSNode):
    '''
    This is an interface to a NVMe Namespace in configFS.
    A Namespace is identified by its parent Subsystem and Namespace ID.
    '''

    MAX_NSID = 8192

    def __repr__(self):
        return "<Namspace %d>" % self.nsid

    def __init__(self, subsystem, nsid=None, mode='any'):
        '''
        A LUN object can be instanciated in two ways:
            - B{Creation mode}: If I{storage_object} is specified, the
              underlying configFS object will be created with that parameter.
              No LUN with the same I{lun} index can pre-exist in the parent TPG
              in that mode, or instanciation will fail.
            - B{Lookup mode}: If I{storage_object} is not set, then the LUN
              will be bound to the existing configFS LUN object of the parent
              TPG having the specified I{lun} index. The underlying configFS
              object must already exist in that mode.

        @param parent_tpg: The parent TPG object.
        @type parent_tpg: TPG
        @param lun: The LUN index.
        @type lun: 0-255
        @param storage_object: The storage object to be exported as a LUN.
        @type storage_object: StorageObject subclass
        @param alias: An optional parameter to manually specify the LUN alias.
        You probably do not need this.
        @type alias: string
        @return: A LUN object.
        '''
        super(Namespace, self).__init__()

        if not isinstance(subsystem, Subsystem):
            raise CFSError("Invalid parent class")

        if nsid is None:
            nsids = [n.nsid for n in self.subsystem.namespaces]
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

        self._attr_groups = ['device']
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
    nsid = property(_get_nsid,
            doc="Get the NSID as an int.")

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


def _test():
    from doctest import testmod
    testmod()

if __name__ == "__main__":
    _test()
