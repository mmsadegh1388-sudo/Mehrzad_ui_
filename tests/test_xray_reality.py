import sys, tempfile, unittest, uuid, json, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import xray_reality as xr
class XrayRealityTests(unittest.TestCase):
 def test_config_and_uri(self):
  uid=str(uuid.uuid4()); cfg=xr.make_config('www.example.com','www.example.com:443',443,'A'*32,'a1b2',[{'id':uid,'email':'demo'}])
  self.assertEqual(cfg['inbounds'][0]['protocol'],'vless'); self.assertEqual(cfg['inbounds'][0]['streamSettings']['security'],'reality')
  uri=xr.client_uri(uid,'203.0.113.5',443,'B'*32,'www.example.com','a1b2','Mehrzad Demo')
  self.assertTrue(uri.startswith('vless://'+uid+'@203.0.113.5:443?')); self.assertIn('security=reality',uri); self.assertIn('Mehrzad%20Demo',uri)
 def test_reject_bad_inputs(self):
  with self.assertRaises(ValueError): xr.make_config('bad/name','dest:443',443,'A'*32,'ab',[{'id':str(uuid.uuid4())}])
  with self.assertRaises(ValueError): xr.make_config('sni','dest:443',443,'A'*32,'xyz!',[{'id':str(uuid.uuid4())}])
 def test_atomic_private_config(self):
  cfg=xr.make_config('sni.example','dest.example:443',443,'A'*32,'ab',[{'id':str(uuid.uuid4())}])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json'; xr.atomic_write(p,cfg); self.assertEqual(json.loads(p.read_text()),cfg); self.assertEqual(os.stat(p).st_mode & 0o777,0o600)
if __name__=='__main__': unittest.main()
