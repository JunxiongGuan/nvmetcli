
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

    def test_save_restore(self):
        root = nvme.Root()
        root.clear_existing()

        s = nvme.Subsystem(nqn='testnqn', mode='create')

        n = nvme.Namespace(s, nsid=42, mode='create')
        n.set_attr('device', 'path', '/dev/ram0')
        n.set_enable(1)

        nguid = n.get_attr('device', 'nguid')

        root.save_to_file('test.json')
        root.clear_existing()
        root.restore_from_file('test.json')

        # additional restores should fai
        self.assertRaises(nvme.CFSError, root.restore_from_file,
                          'test.json', False)

        # ... unless forced!
        root.restore_from_file('test.json', True)

        # rebuild our view of the world
        s = nvme.Subsystem(nqn='testnqn', mode='lookup')
        n = nvme.Namespace(s, nsid=42, mode='lookup')

        # and check everything is still the same
        self.assertTrue(n.get_enable())
        self.assertEqual(n.get_attr('device', 'path'), '/dev/ram0')
        self.assertEqual(n.get_attr('device', 'nguid'), nguid)
