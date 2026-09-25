#!/usr/bin/env python3
"""Generate and validate a minimal Xray VLESS + REALITY config (no system changes)."""
import argparse, json, os, re, secrets, subprocess, tempfile, uuid
from pathlib import Path
from urllib.parse import urlencode, quote

FLOW = 'xtls-rprx-vision'

def make_config(server_name, dest, port, private_key, short_id, clients):
    if not re.fullmatch(r'[A-Za-z0-9.-]+', server_name) or '..' in server_name:
        raise ValueError('Invalid REALITY server name')
    if not re.fullmatch(r'[A-Za-z0-9.-]+:\d{1,5}', dest) or int(dest.rsplit(':',1)[1]) not in range(1,65536):
        raise ValueError('dest must be host:port')
    if not 1 <= int(port) <= 65535: raise ValueError('Port must be 1..65535')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,256}', private_key): raise ValueError('Invalid private key format')
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}){0,8}', short_id): raise ValueError('shortId must be 0-16 hex chars')
    if not clients: raise ValueError('At least one client is required')
    out=[]
    for c in clients:
        try: uid=str(uuid.UUID(c['id']))
        except Exception as e: raise ValueError('Client id must be a UUID') from e
        out.append({'id':uid, 'flow':FLOW, 'email':str(c.get('email',uid))[:64]})
    return {'log':{'loglevel':'warning'},'inbounds':[{'tag':'vless-reality-in','listen':'0.0.0.0','port':int(port),'protocol':'vless','settings':{'clients':out,'decryption':'none'},'streamSettings':{'network':'tcp','security':'reality','realitySettings':{'show':False,'dest':dest,'serverNames':[server_name],'privateKey':private_key,'shortIds':[short_id]}}}],'outbounds':[{'protocol':'freedom','tag':'direct'}]}

def client_uri(uid, host, port, public_key, sni, short_id, label):
    try: uid=str(uuid.UUID(uid))
    except Exception as e: raise ValueError('Invalid client UUID') from e
    if not re.fullmatch(r'[A-Za-z0-9.-]+',host): raise ValueError('Invalid server host/IP')
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,256}',public_key): raise ValueError('Invalid public key format')
    q=urlencode({'type':'tcp','security':'reality','pbk':public_key,'fp':'chrome','sni':sni,'sid':short_id,'spx':'/','flow':FLOW})
    return f'vless://{uid}@{host}:{int(port)}?{q}#{quote(label)}'

def atomic_write(path, data):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.xray-',dir=p.parent,text=True)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p); os.chmod(p,0o600)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server-name',required=True,help='REALITY SNI hostname')
    p.add_argument('--dest',required=True,help='REALITY destination host:port')
    p.add_argument('--port',type=int,default=443)
    p.add_argument('--private-key',required=True,help='Private key from `xray x25519`; keep secret')
    p.add_argument('--short-id',default=None,help='0-16 hex chars; default generated')
    p.add_argument('--client-id',action='append',default=[],help='Client UUID (repeatable); generated if omitted')
    p.add_argument('--output',default='xray-config.json')
    p.add_argument('--xray-bin',default='xray',help='Optional Xray binary; runs xray run -test -config FILE')
    p.add_argument('--skip-xray-test',action='store_true')
    a=p.parse_args(); sid=a.short_id if a.short_id is not None else secrets.token_hex(4); ids=a.client_id or [str(uuid.uuid4())]
    cfg=make_config(a.server_name,a.dest,a.port,a.private_key,sid,[{'id':x,'email':f'mehrzad-{i+1}'} for i,x in enumerate(ids)])
    atomic_write(a.output,cfg)
    if not a.skip_xray_test:
        try: r=subprocess.run([a.xray_bin,'run','-test','-config',a.output],capture_output=True,text=True,timeout=30)
        except (OSError,subprocess.TimeoutExpired) as e: Path(a.output).unlink(missing_ok=True); raise SystemExit(f'Xray validation unavailable/failed: {e}')
        if r.returncode: Path(a.output).unlink(missing_ok=True); raise SystemExit('Xray rejected config: '+(r.stderr or r.stdout)[-2000:])
    print(f'Config written: {a.output} (mode 0600); clients: '+', '.join(ids))
    print('No service was installed, restarted, or exposed to the network.')
if __name__=='__main__': main()
