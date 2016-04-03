
import random
import string
import unittest
import nvmet.nvme as nvme


class TestNvmet(unittest.TestCase):
    def test_subsystem(self):
        root = nvme.Root()
        root.clear_existing()
        for s in root.subsystems:
            self.assertTrue(False, 'Found Subsystem after clear')

        # create mode
        s1 = nvme.Subsystem(nqn='testnqn1', mode='create')
        self.assertIsNotNone(s1)
        self.assertEqual(len(list(root.subsystems)), 1)

        # any mode, should create
        s2 = nvme.Subsystem(nqn='testnqn2', mode='any')
        self.assertIsNotNone(s2)
        self.assertEqual(len(list(root.subsystems)), 2)

        # random name
        s3 = nvme.Subsystem(mode='create')
        self.assertIsNotNone(s3)
        self.assertEqual(len(list(root.subsystems)), 3)

        # duplicate
        self.assertRaises(nvme.CFSError, nvme.Subsystem,
                          nqn='testnqn1', mode='create')
        self.assertEqual(len(list(root.subsystems)), 3)

        # lookup using any, should not create
        s = nvme.Subsystem(nqn='testnqn1', mode='any')
        self.assertEqual(s1, s)
        self.assertEqual(len(list(root.subsystems)), 3)

        # lookup only
        s = nvme.Subsystem(nqn='testnqn2', mode='lookup')
        self.assertEqual(s2, s)
        self.assertEqual(len(list(root.subsystems)), 3)

        # lookup without nqn
        self.assertRaises(nvme.CFSError, nvme.Subsystem, mode='lookup')

        # and delete them all
        for s in root.subsystems:
            s.delete()
        self.assertEqual(len(list(root.subsystems)), 0)

    def test_namespace(self):
        root = nvme.Root()
        root.clear_existing()

        s = nvme.Subsystem(nqn='testnqn', mode='create')
        for n in s.namespaces:
            self.assertTrue(False, 'Found Namespace in new Subsystem')

        # create mode
        n1 = nvme.Namespace(s, nsid=3, mode='create')
        self.assertIsNotNone(n1)
        self.assertEqual(len(list(s.namespaces)), 1)

        # any mode, should create
        n2 = nvme.Namespace(s, nsid=2, mode='any')
        self.assertIsNotNone(n2)
        self.assertEqual(len(list(s.namespaces)), 2)

        # create without nsid, should pick lowest available
        n3 = nvme.Namespace(s, mode='create')
        self.assertIsNotNone(n3)
        self.assertEqual(n3.nsid, 1)
        self.assertEqual(len(list(s.namespaces)), 3)

        n4 = nvme.Namespace(s, mode='create')
        self.assertIsNotNone(n4)
        self.assertEqual(n4.nsid, 4)
        self.assertEqual(len(list(s.namespaces)), 4)

        # duplicate
        self.assertRaises(nvme.CFSError, nvme.Namespace, 1, mode='create')
        self.assertEqual(len(list(s.namespaces)), 4)

        # lookup using any, should not create
        n = nvme.Namespace(s, nsid=3, mode='any')
        self.assertEqual(n1, n)
        self.assertEqual(len(list(s.namespaces)), 4)

        # lookup only
        n = nvme.Namespace(s, nsid=2, mode='lookup')
        self.assertEqual(n2, n)
        self.assertEqual(len(list(s.namespaces)), 4)

        # lookup without nsid
        self.assertRaises(nvme.CFSError, nvme.Namespace, None, mode='lookup')

        # and delete them all
        for n in s.namespaces:
            n.delete()
        self.assertEqual(len(list(s.namespaces)), 0)

    def test_namespace_attrs(self):
        root = nvme.Root()
        root.clear_existing()

        s = nvme.Subsystem(nqn='testnqn', mode='create')
        n = nvme.Namespace(s, mode='create')

        self.assertFalse(n.get_enable())
        self.assertTrue('device' in n.attr_groups)
        self.assertTrue('path' in n.list_attrs('device'))

        # no device set yet, should fail
        self.assertRaises(nvme.CFSError, n.set_enable, 1)

        # now set a path and enable
        n.set_attr('device', 'path', '/dev/ram0')
        n.set_enable(1)
        self.assertTrue(n.get_enable())

        # test double enable
        n.set_enable(1)

        # test that we can't write to attrs while enabled
        self.assertRaises(nvme.CFSError, n.set_attr, 'device', 'path',
                          '/dev/ram1')
        self.assertRaises(nvme.CFSError, n.set_attr, 'device', 'nguid',
                          '15f7767b-50e7-4441-949c-75b99153dea7')

        # disable: once and twice
        n.set_enable(0)
        n.set_enable(0)

        # enable again, and remove while enabled
        n.set_enable(1)
        n.delete()

    def test_recursive_delete(self):
        root = nvme.Root()
        root.clear_existing()

        s = nvme.Subsystem(nqn='testnqn', mode='create')
        n1 = nvme.Namespace(s, mode='create')
        n2 = nvme.Namespace(s, mode='create')

        s.delete()
        self.assertEqual(len(list(root.subsystems)), 0)

    def test_port(self):
        root = nvme.Root()
        root.clear_existing()
        for p in root.ports:
            self.assertTrue(False, 'Found Port after clear')

        # create mode
        p1 = nvme.Port(root, portid=0, mode='create')
        self.assertIsNotNone(p1)
        self.assertEqual(len(list(root.ports)), 1)

        # any mode, should create
        p2 = nvme.Port(root, portid=1, mode='any')
        self.assertIsNotNone(p2)
        self.assertEqual(len(list(root.ports)), 2)

        # automatic portid
        p3 = nvme.Port(root, mode='create')
        self.assertIsNotNone(p3)
        self.assertNotEqual(p3, p1)
        self.assertNotEqual(p3, p2)
        self.assertEqual(len(list(root.ports)), 3)

        # duplicate
        self.assertRaises(nvme.CFSError, nvme.Port,
                          root, portid=0, mode='create')
        self.assertEqual(len(list(root.ports)), 3)

        # lookup using any, should not create
        p = nvme.Port(root, portid=0, mode='any')
        self.assertEqual(p1, p)
        self.assertEqual(len(list(root.ports)), 3)

        # lookup only
        p = nvme.Port(root, portid=1, mode='lookup')
        self.assertEqual(p2, p)
        self.assertEqual(len(list(root.ports)), 3)

        # lookup without portid
        self.assertRaises(nvme.CFSError, nvme.Port, root, mode='lookup')

        # and delete them all
        for p in root.ports:
            p.delete()
        self.assertEqual(len(list(root.ports)), 0)

    def test_loop_port(self):
        root = nvme.Root()
        root.clear_existing()

        p = nvme.Port(root, portid=0, mode='create')

        self.assertFalse(p.get_enable())
        self.assertTrue('addr' in p.attr_groups)

        # no trtype set yet, should fail
        self.assertRaises(nvme.CFSError, p.set_enable, 1)

        # now set trtype to loop and other attrs and enable
        p.set_attr('addr', 'trtype', 'loop')
        p.set_attr('addr', 'adrfam', 'ipv4')
        p.set_attr('addr', 'traddr', '192.168.0.1')
        p.set_attr('addr', 'treq', 'not required')
        p.set_attr('addr', 'trsvcid', '1023')
        p.set_enable(1)
        self.assertTrue(p.get_enable())

        # test double enable
        p.set_enable(1)

        # test that we can't write to attrs while enabled
        self.assertRaises(nvme.CFSError, p.set_attr, 'addr', 'trtype',
                          'rdma')
        self.assertRaises(nvme.CFSError, p.set_attr, 'addr', 'adrfam',
                          'ipv6')
        self.assertRaises(nvme.CFSError, p.set_attr, 'addr', 'traddr',
                          '10.0.0.1')
        self.assertRaises(nvme.CFSError, p.set_attr, 'addr', 'treq',
                          'required')
        self.assertRaises(nvme.CFSError, p.set_attr, 'addr', 'trsvcid',
                          '21')

        # disable: once and twice
        p.set_enable(0)
        p.set_enable(0)

        # check that the attrs haven't been tampered with
        self.assertEqual(p.get_attr('addr', 'trtype'), 'loop')
        self.assertEqual(p.get_attr('addr', 'adrfam'), 'ipv4')
        self.assertEqual(p.get_attr('addr', 'traddr'), '192.168.0.1')
        self.assertEqual(p.get_attr('addr', 'treq'), 'not required')
        self.assertEqual(p.get_attr('addr', 'trsvcid'), '1023')

        # enable again, and remove while enabled
        p.set_enable(1)
        p.delete()

    def test_host(self):
        root = nvme.Root()
        root.clear_existing()
        for p in root.hosts:
            self.assertTrue(False, 'Found Host after clear')

        # create mode
        h1 = nvme.Host(nqn='foo', mode='create')
        self.assertIsNotNone(h1)
        self.assertEqual(len(list(root.hosts)), 1)

        # any mode, should create
        h2 = nvme.Host(nqn='bar', mode='any')
        self.assertIsNotNone(h2)
        self.assertEqual(len(list(root.hosts)), 2)

        # duplicate
        self.assertRaises(nvme.CFSError, nvme.Host,
                          'foo', mode='create')
        self.assertEqual(len(list(root.hosts)), 2)

        # lookup using any, should not create
        h = nvme.Host('foo', mode='any')
        self.assertEqual(h1, h)
        self.assertEqual(len(list(root.hosts)), 2)

        # lookup only
        h = nvme.Host('bar', mode='lookup')
        self.assertEqual(h2, h)
        self.assertEqual(len(list(root.hosts)), 2)

        # and delete them all
        for h in root.hosts:
            h.delete()
        self.assertEqual(len(list(root.hosts)), 0)

    def test_allowed_hosts(self):
        root = nvme.Root()

        h = nvme.Host(nqn='hostnqn', mode='create')

        s = nvme.Subsystem(nqn='testnqn', mode='create')

        # add allowed_host
        s.add_allowed_host(nqn='hostnqn')

        # duplicate
        self.assertRaises(nvme.CFSError, s.add_allowed_host, 'hostnqn')

        # invalid
        self.assertRaises(nvme.CFSError, s.add_allowed_host, 'invalid')

        # remove again
        s.remove_allowed_host('hostnqn')

        # duplicate removal
        self.assertRaises(nvme.CFSError, s.remove_allowed_host, 'hostnqn')

        # invalid removal
        self.assertRaises(nvme.CFSError, s.remove_allowed_host, 'foobar')

    def test_invalid_input(self):
        root = nvme.Root()
        root.clear_existing()

        self.assertRaises(nvme.CFSError, nvme.Subsystem,
                          nqn='', mode='create')
        self.assertRaises(nvme.CFSError, nvme.Subsystem,
                          nqn='/', mode='create')

        for l in [ 257, 512, 1024, 2048 ]:
            toolong = ''.join(random.choice(string.lowercase)
                              for i in range(l))
            self.assertRaises(nvme.CFSError, nvme.Subsystem,
                              nqn=toolong, mode='create')

        discover_nqn = "nqn.2014-08.org.nvmexpress.discovery"
        self.assertRaises(nvme.CFSError, nvme.Subsystem,
                          nqn=discover_nqn, mode='create')

        self.assertRaises(nvme.CFSError, nvme.Port,
                          root=root, portid=1 << 17, mode='create')

    def test_save_restore(self):
        root = nvme.Root()
        root.clear_existing()

        h = nvme.Host(nqn='hostnqn', mode='create')

        s = nvme.Subsystem(nqn='testnqn', mode='create')
        s.add_allowed_host(nqn='hostnqn')

        s2 = nvme.Subsystem(nqn='testnqn2', mode='create')
        s2.set_attr('attr', 'allow_any_host', 1)

        n = nvme.Namespace(s, nsid=42, mode='create')
        n.set_attr('device', 'path', '/dev/ram0')
        n.set_enable(1)

        nguid = n.get_attr('device', 'nguid')

        p = nvme.Port(root, portid=66, mode='create')
        p.set_attr('addr', 'trtype', 'loop')
        p.set_attr('addr', 'adrfam', 'ipv4')
        p.set_attr('addr', 'traddr', '192.168.0.1')
        p.set_attr('addr', 'treq', 'not required')
        p.set_attr('addr', 'trsvcid', '1023')
        p.set_enable(1)

        # save, clear, and restore
        root.save_to_file('test.json')
        root.clear_existing()
        root.restore_from_file('test.json')

        # additional restores should fai
        self.assertRaises(nvme.CFSError, root.restore_from_file,
                          'test.json', False)

        # ... unless forced!
        root.restore_from_file('test.json', True)

        # rebuild our view of the world
        h = nvme.Host(nqn='hostnqn', mode='lookup')
        s = nvme.Subsystem(nqn='testnqn', mode='lookup')
        s2 = nvme.Subsystem(nqn='testnqn2', mode='lookup')
        n = nvme.Namespace(s, nsid=42, mode='lookup')
        p = nvme.Port(root, portid=66, mode='lookup')

        self.assertEqual(s.get_attr('attr', 'allow_any_host'), "0")
        self.assertEqual(s2.get_attr('attr', 'allow_any_host'), "1")
        self.assertIn('hostnqn', s.allowed_hosts)

        # and check everything is still the same
        self.assertTrue(n.get_enable())
        self.assertEqual(n.get_attr('device', 'path'), '/dev/ram0')
        self.assertEqual(n.get_attr('device', 'nguid'), nguid)

        self.assertEqual(p.get_attr('addr', 'trtype'), 'loop')
        self.assertEqual(p.get_attr('addr', 'adrfam'), 'ipv4')
        self.assertEqual(p.get_attr('addr', 'traddr'), '192.168.0.1')
        self.assertEqual(p.get_attr('addr', 'treq'), 'not required')
        self.assertEqual(p.get_attr('addr', 'trsvcid'), '1023')
