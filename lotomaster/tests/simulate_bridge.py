"""Bridge local/offline para testar fallback JS contra /simulate real."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
def no_network(self, address):
    if self.family != socket.AF_UNIX:
        raise OSError('network blocked')
socket.socket.connect = no_network
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix='lotomaster-simulator-') as tmp:
    os.environ['LOTOMASTER_DB_PATH'] = os.path.join(tmp, 'db.sqlite3')
    from lotomaster.api import app
    response = TestClient(app).post('/api/v1/maismilionaria/simulate', json=json.load(sys.stdin))
    print(json.dumps({'status': response.status_code, 'body': response.json()}))
