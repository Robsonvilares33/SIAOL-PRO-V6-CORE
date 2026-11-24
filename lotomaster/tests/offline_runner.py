"""Run the Python suite with external networking blocked and an isolated temporary SQLite DB.

Usage from repository root: python lotomaster/tests/offline_runner.py
"""
import ipaddress
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


def is_local_address(family, address):
    if family == socket.AF_UNIX:
        return True
    if family not in (socket.AF_INET, socket.AF_INET6):
        return False
    host = address[0] if isinstance(address, tuple) else address
    try:
        parsed = ipaddress.ip_address(str(host).split("%", 1)[0])
    except ValueError:
        return False
    return parsed.is_loopback or bool(
        isinstance(parsed, ipaddress.IPv6Address)
        and parsed.ipv4_mapped
        and parsed.ipv4_mapped.is_loopback
    )


def block_connect(self, address):
    if not is_local_address(self.family, address):
        raise OSError("external network blocked for offline tests")
    return original_connect(self, address)


def block_connect_ex(self, address):
    if not is_local_address(self.family, address):
        raise OSError("external network blocked for offline tests")
    return original_connect_ex(self, address)


socket.socket.connect = block_connect
socket.socket.connect_ex = block_connect_ex
with tempfile.TemporaryDirectory(prefix="lotomaster-offline-") as tmp:
    os.environ["LOTOMASTER_DB_PATH"] = os.path.join(tmp, "test.sqlite3")
    tests = unittest.defaultTestLoader.discover(str(root / "lotomaster" / "tests"), pattern="test*.py")
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
