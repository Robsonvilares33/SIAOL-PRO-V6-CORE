"""Run the Python suite with network disabled and an isolated temporary SQLite DB.

Usage from repository root: python lotomaster/tests/offline_runner.py
"""
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex


def block_connect(self, address):
    if self.family != socket.AF_UNIX:
        raise OSError('network blocked for offline tests')
    return original_connect(self, address)


def block_connect_ex(self, address):
    if self.family != socket.AF_UNIX:
        raise OSError('network blocked for offline tests')
    return original_connect_ex(self, address)


socket.socket.connect = block_connect
socket.socket.connect_ex = block_connect_ex
with tempfile.TemporaryDirectory(prefix='lotomaster-offline-') as tmp:
    os.environ['LOTOMASTER_DB_PATH'] = os.path.join(tmp, 'test.sqlite3')
    tests = unittest.defaultTestLoader.discover(str(root / 'lotomaster' / 'tests'), pattern='test*.py')
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
