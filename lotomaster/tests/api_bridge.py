"""Offline subprocess bridge used only by the JS/ASGI integration test."""
import json
import ipaddress
import os
from pathlib import Path
import socket
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
original_connect = socket.socket.connect
def no_network(self, address):
    if self.family == socket.AF_UNIX:
        return original_connect(self, address)
    if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
        try:
            if ipaddress.ip_address(address[0]).is_loopback:
                return original_connect(self, address)
        except ValueError:
            pass
    raise OSError('network blocked')
socket.socket.connect = no_network
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix='lotomaster-bridge-') as tmp:
    os.environ['LOTOMASTER_DB_PATH'] = os.path.join(tmp, 'db.sqlite3')
    from lotomaster.api import app
    response = TestClient(app).post('/api/v1/quina/statistics/from-draws', json=json.load(sys.stdin))
    print(json.dumps({'status': response.status_code, 'body': response.json()}))
