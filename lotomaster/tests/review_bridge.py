"""Local bridge for JS/backend parity tests, with network disabled."""
import json, os, socket, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
socket.socket.connect = lambda self, address: (_ for _ in ()).throw(OSError('network blocked'))
from fastapi.testclient import TestClient
tmp = tempfile.TemporaryDirectory(prefix='lotomaster-review-bridge-')
os.environ['LOTOMASTER_DB_PATH'] = os.path.join(tmp.name, 'test.sqlite3')
from lotomaster.api import app
from lotomaster.validation import validate_draw
request=json.load(sys.stdin)
if request['action']=='validate':
    try:
        validate_draw(request['game'],request['draw'],require_game=True,require_special=True)
        result={'valid':True}
    except ValueError:
        result={'valid':False}
else:
    response=TestClient(app).post('/api/v1/timemania/generate',json=request['payload'])
    result={'status':response.status_code,'body':response.json()}
print(json.dumps(result))
tmp.cleanup()
