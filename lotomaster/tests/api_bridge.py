"""Offline subprocess bridge used only by the JS/ASGI integration test."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
def no_network(self, address):
    if self.family != socket.AF_UNIX:
        raise OSError('network blocked')
socket.socket.connect = no_network
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix='lotomaster-bridge-') as tmp:
    os.environ['LOTOMASTER_DB_PATH'] = os.path.join(tmp, 'db.sqlite3')
    from lotomaster.api import app
    response = TestClient(app).post('/api/v1/quina/statistics/from-draws', json=json.load(sys.stdin))
    print(json.dumps({'status': response.status_code, 'body': response.json()}))
