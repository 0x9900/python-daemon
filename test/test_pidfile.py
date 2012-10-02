# -*- coding: utf-8 -*-
#
# test/test_pidfile.py
# Part of python-daemon, an implementation of PEP 3143.
#
# Copyright © 2008–2010 Ben Finney <ben+python@benfinney.id.au>
#
# This is free software: you may copy, modify, and/or distribute this work
# under the terms of the Python Software Foundation License, version 2 or
# later as published by the Python Software Foundation.
# No warranty expressed or implied. See the file LICENSE.PSF-2 for details.

""" Unit test for ‘pidfile’ module.
    """

import __builtin__ as builtins
import os
from StringIO import StringIO
import itertools
import tempfile
import errno

import lockfile
from lockfile import pidlockfile

import scaffold

import daemon.pidfile


class FakeFileDescriptorStringIO(StringIO, object):
    """ A StringIO class that fakes a file descriptor. """

    _fileno_generator = itertools.count()

    def __init__(self, *args, **kwargs):
        self._fileno = self._fileno_generator.next()
        super_instance = super(FakeFileDescriptorStringIO, self)
        super_instance.__init__(*args, **kwargs)

    def fileno(self):
        return self._fileno


def make_pidlockfile_scenarios():
    """ Make a collection of scenarios for testing PIDLockFile instances. """

    mock_current_pid = 235
    mock_other_pid = 8642
    mock_pidfile_path = tempfile.mktemp()

    mock_pidfile_empty = FakeFileDescriptorStringIO()
    mock_pidfile_current_pid = FakeFileDescriptorStringIO(
        u"%(mock_current_pid)d\n" % vars())
    mock_pidfile_other_pid = FakeFileDescriptorStringIO(
        u"%(mock_other_pid)d\n" % vars())
    mock_pidfile_bogus = FakeFileDescriptorStringIO(
        u"b0gUs")

    scenarios = {
        'simple': {},
        'not-exist': {
            'open_func_name': 'mock_open_nonexist',
            'os_open_func_name': 'mock_os_open_nonexist',
            },
        'not-exist-write-denied': {
            'open_func_name': 'mock_open_nonexist',
            'os_open_func_name': 'mock_os_open_nonexist',
            },
        'not-exist-write-busy': {
            'open_func_name': 'mock_open_nonexist',
            'os_open_func_name': 'mock_os_open_nonexist',
            },
        'exist-read-denied': {
            'open_func_name': 'mock_open_read_denied',
            'os_open_func_name': 'mock_os_open_read_denied',
            },
        'exist-locked-read-denied': {
            'locking_pid': mock_other_pid,
            'open_func_name': 'mock_open_read_denied',
            'os_open_func_name': 'mock_os_open_read_denied',
            },
        'exist-empty': {},
        'exist-invalid': {
            'pidfile': mock_pidfile_bogus,
            },
        'exist-current-pid': {
            'pidfile': mock_pidfile_current_pid,
            'pidfile_pid': mock_current_pid,
            },
        'exist-current-pid-locked': {
            'pidfile': mock_pidfile_current_pid,
            'pidfile_pid': mock_current_pid,
            'locking_pid': mock_current_pid,
            },
        'exist-other-pid': {
            'pidfile': mock_pidfile_other_pid,
            'pidfile_pid': mock_other_pid,
            },
        'exist-other-pid-locked': {
            'pidfile': mock_pidfile_other_pid,
            'pidfile_pid': mock_other_pid,
            'locking_pid': mock_other_pid,
            },
        }

    for scenario in scenarios.values():
        scenario['pid'] = mock_current_pid
        scenario['path'] = mock_pidfile_path
        if 'pidfile' not in scenario:
            scenario['pidfile'] = mock_pidfile_empty
        if 'pidfile_pid' not in scenario:
            scenario['pidfile_pid'] = None
        if 'locking_pid' not in scenario:
            scenario['locking_pid'] = None
        if 'open_func_name' not in scenario:
            scenario['open_func_name'] = 'mock_open_okay'
        if 'os_open_func_name' not in scenario:
            scenario['os_open_func_name'] = 'mock_os_open_okay'

    return scenarios


def setup_pidfile_fixtures(testcase):
    """ Set up common fixtures for PID file test cases. """
    testcase.mock_tracker = scaffold.MockTracker()

    scenarios = make_pidlockfile_scenarios()
    testcase.pidlockfile_scenarios = scenarios

    def get_scenario_option(testcase, key, default=None):
        value = default
        try:
            value = testcase.scenario[key]
        except (NameError, TypeError, AttributeError, KeyError):
            pass
        return value

    scaffold.mock(
        u"os.getpid",
        returns=scenarios['simple']['pid'],
        tracker=testcase.mock_tracker)

    def make_mock_open_funcs(testcase):

        def mock_open_nonexist(filename, mode, buffering):
            if 'r' in mode:
                raise IOError(
                    errno.ENOENT, u"No such file %(filename)r" % vars())
            else:
                result = testcase.scenario['pidfile']
            return result

        def mock_open_read_denied(filename, mode, buffering):
            if 'r' in mode:
                raise IOError(
                    errno.EPERM, u"Read denied on %(filename)r" % vars())
            else:
                result = testcase.scenario['pidfile']
            return result

        def mock_open_okay(filename, mode, buffering):
            result = testcase.scenario['pidfile']
            return result

        def mock_os_open_nonexist(filename, flags, mode):
            if (flags & os.O_CREAT):
                result = testcase.scenario['pidfile'].fileno()
            else:
                raise OSError(
                    errno.ENOENT, u"No such file %(filename)r" % vars())
            return result

        def mock_os_open_read_denied(filename, flags, mode):
            if (flags & os.O_CREAT):
                result = testcase.scenario['pidfile'].fileno()
            else:
                raise OSError(
                    errno.EPERM, u"Read denied on %(filename)r" % vars())
            return result

        def mock_os_open_okay(filename, flags, mode):
            result = testcase.scenario['pidfile'].fileno()
            return result

        funcs = dict(
            (name, obj) for (name, obj) in vars().items()
            if hasattr(obj, '__call__'))

        return funcs

    testcase.mock_pidfile_open_funcs = make_mock_open_funcs(testcase)

    def mock_open(filename, mode='r', buffering=None):
        scenario_path = get_scenario_option(testcase, 'path')
        if filename == scenario_path:
            func_name = testcase.scenario['open_func_name']
            mock_open_func = testcase.mock_pidfile_open_funcs[func_name]
            result = mock_open_func(filename, mode, buffering)
        else:
            result = FakeFileDescriptorStringIO()
        return result

    scaffold.mock(
        u"builtins.open",
        returns_func=mock_open,
        tracker=testcase.mock_tracker)

    def mock_os_open(filename, flags, mode=None):
        scenario_path = get_scenario_option(testcase, 'path')
        if filename == scenario_path:
            func_name = testcase.scenario['os_open_func_name']
            mock_os_open_func = testcase.mock_pidfile_open_funcs[func_name]
            result = mock_os_open_func(filename, flags, mode)
        else:
            result = FakeFileDescriptorStringIO().fileno()
        return result

    scaffold.mock(
        u"os.open",
        returns_func=mock_os_open,
        tracker=testcase.mock_tracker)

    def mock_os_fdopen(fd, mode='r', buffering=None):
        scenario_pidfile = get_scenario_option(
            testcase, 'pidfile', FakeFileDescriptorStringIO())
        if fd == testcase.scenario['pidfile'].fileno():
            result = testcase.scenario['pidfile']
        else:
            raise OSError(errno.EBADF, u"Bad file descriptor")
        return result

    scaffold.mock(
        u"os.fdopen",
        returns_func=mock_os_fdopen,
        tracker=testcase.mock_tracker)

    testcase.scenario = NotImplemented


def setup_lockfile_method_mocks(testcase, scenario, class_name):
    """ Set up common mock methods for lockfile class. """

    def mock_read_pid():
        return scenario['pidfile_pid']
    def mock_is_locked():
        return (scenario['locking_pid'] is not None)
    def mock_i_am_locking():
        return (
            scenario['locking_pid'] == scenario['pid'])
    def mock_acquire(timeout=None):
        if scenario['locking_pid'] is not None:
            raise lockfile.AlreadyLocked()
        scenario['locking_pid'] = scenario['pid']
    def mock_release():
        if scenario['locking_pid'] is None:
            raise lockfile.NotLocked()
        if scenario['locking_pid'] != scenario['pid']:
            raise lockfile.NotMyLock()
        scenario['locking_pid'] = None
    def mock_break_lock():
        scenario['locking_pid'] = None

    for func_name in [
        'read_pid',
        'is_locked', 'i_am_locking',
        'acquire', 'release', 'break_lock',
        ]:
        mock_func = vars()["mock_%(func_name)s" % vars()]
        lockfile_func_name = u"%(class_name)s.%(func_name)s" % vars()
        mock_lockfile_func = scaffold.Mock(
            lockfile_func_name,
            returns_func=mock_func,
            tracker=testcase.mock_tracker)
        try:
            scaffold.mock(
                lockfile_func_name,
                mock_obj=mock_lockfile_func,
                tracker=testcase.mock_tracker)
        except NameError:
            pass


def setup_pidlockfile_fixtures(testcase, scenario_name=None):
    """ Set up common fixtures for PIDLockFile test cases. """

    setup_pidfile_fixtures(testcase)

    scaffold.mock(
        u"pidlockfile.write_pid_to_pidfile",
        tracker=testcase.mock_tracker)
    scaffold.mock(
        u"pidlockfile.remove_existing_pidfile",
        tracker=testcase.mock_tracker)

    if scenario_name is not None:
        set_pidlockfile_scenario(testcase, scenario_name, clear_tracker=False)


def set_pidlockfile_scenario(testcase, scenario_name, clear_tracker=True):
    """ Set up the test case to the specified scenario. """
    testcase.scenario = testcase.pidlockfile_scenarios[scenario_name]
    setup_lockfile_method_mocks(
        testcase, testcase.scenario, u"lockfile.LinkLockFile")
    testcase.pidlockfile_args = dict(
        path=testcase.scenario['path'],
        )
    testcase.test_instance = pidlockfile.PIDLockFile(
        **testcase.pidlockfile_args)
    if clear_tracker:
        testcase.mock_tracker.clear()


class TimeoutPIDLockFile_TestCase(scaffold.TestCase):
    """ Test cases for ‘TimeoutPIDLockFile’ class. """

    def setUp(self):
        """ Set up test fixtures. """
        self.mock_tracker = scaffold.MockTracker()

        pidlockfile_scenarios = make_pidlockfile_scenarios()
        self.pidlockfile_scenario = pidlockfile_scenarios['simple']
        pidfile_path = self.pidlockfile_scenario['path']

        scaffold.mock(
            u"pidlockfile.PIDLockFile.__init__",
            tracker=self.mock_tracker)
        scaffold.mock(
            u"pidlockfile.PIDLockFile.acquire",
            tracker=self.mock_tracker)

        self.scenario = {
            'pidfile_path': self.pidlockfile_scenario['path'],
            'acquire_timeout': object(),
            }

        self.test_kwargs = dict(
            path=self.scenario['pidfile_path'],
            acquire_timeout=self.scenario['acquire_timeout'],
            )
        self.test_instance = daemon.pidfile.TimeoutPIDLockFile(
            **self.test_kwargs)

    def tearDown(self):
        """ Tear down test fixtures. """
        scaffold.mock_restore()

    def test_inherits_from_pidlockfile(self):
        """ Should inherit from PIDLockFile. """
        instance = self.test_instance
        self.failUnlessIsInstance(instance, pidlockfile.PIDLockFile)

    def test_init_has_expected_signature(self):
        """ Should have expected signature for ‘__init__’. """
        def test_func(self, path, acquire_timeout=None, *args, **kwargs): pass
        test_func.__name__ = '__init__'
        self.failUnlessFunctionSignatureMatch(
            test_func, 
            daemon.pidfile.TimeoutPIDLockFile.__init__)

    def test_has_specified_acquire_timeout(self):
        """ Should have specified ‘acquire_timeout’ value. """
        instance = self.test_instance
        expect_timeout = self.test_kwargs['acquire_timeout']
        self.failUnlessEqual(expect_timeout, instance.acquire_timeout)

    def test_calls_superclass_init(self):
        """ Should call the superclass ‘__init__’. """
        expect_path = self.test_kwargs['path']
        expect_mock_output = u"""\
            Called pidlockfile.PIDLockFile.__init__(
                %(expect_path)r)
            """ % vars()
        self.failUnlessMockCheckerMatch(expect_mock_output)

    def test_acquire_uses_specified_timeout(self):
        """ Should call the superclass ‘acquire’ with specified timeout. """
        instance = self.test_instance
        test_timeout = object()
        expect_timeout = test_timeout
        self.mock_tracker.clear()
        expect_mock_output = u"""\
            Called pidlockfile.PIDLockFile.acquire(%(expect_timeout)r)
            """ % vars()
        instance.acquire(test_timeout)
        self.failUnlessMockCheckerMatch(expect_mock_output)

    def test_acquire_uses_stored_timeout_by_default(self):
        """ Should call superclass ‘acquire’ with stored timeout by default. """
        instance = self.test_instance
        test_timeout = self.test_kwargs['acquire_timeout']
        expect_timeout = test_timeout
        self.mock_tracker.clear()
        expect_mock_output = u"""\
            Called pidlockfile.PIDLockFile.acquire(%(expect_timeout)r)
            """ % vars()
        instance.acquire()
        self.failUnlessMockCheckerMatch(expect_mock_output)
