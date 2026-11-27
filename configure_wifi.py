"""Provision one board over USB, validate its Wi-Fi path before activating."""
import getpass
import sys
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("host")
    parser.add_argument("--ssid")
    args=parser.parse_args()
    def board(*cmd):
        return subprocess.run([sys.executable,"-m","mpremote","connect",args.port,*cmd],check=True,timeout=65)
    ssid=args.ssid or input("2.4 GHz Wi-Fi 名称：")
    if not ssid.strip():
        raise SystemExit("未填写网络名称")
    password=getpass.getpass("Wi-Fi 密码（输入隐藏）：")
    check = """import network,time,json,socket,os
with open('/nest-wifi.new') as f: c=json.load(f)
w=network.WLAN(network.STA_IF); w.active(True)
w.disconnect()
time.sleep_ms(350)
w.connect(c['ssid'],c['password'])
for _ in range(42):
    if w.isconnected(): break
    time.sleep_ms(500)
if not w.isconnected(): raise OSError('Wi-Fi association failed, status %d' % w.status())
s=socket.socket()
try:
    s.settimeout(5); s.connect((c['host'],c['port']))
    s.write(b'GET /api/pet-nest/state?limit=1 HTTP/1.0\\r\\nHost: cove\\r\\nConnection: close\\r\\n\\r\\n')
    if s.readline().split()[1]!=b'200': raise OSError('Cove did not return HTTP 200')
finally: s.close()
print('Wi-Fi associated; board -> Cove state HTTP 200')
"""
    with tempfile.TemporaryDirectory() as tmp:
        f=Path(tmp)/"wifi.json"
        f.write_text(json.dumps(dict(ssid=ssid,password=password,host=args.host,port=8081)))
        f.chmod(0o600)
        try:
            board("fs","cp",str(f),":/nest-wifi.new","+","exec",check)
            # Preserve the last known-good file across a failed replacement.
            board("exec","import os\nif 'nest-wifi.old' in os.listdir('/'): os.remove('/nest-wifi.old')\nif 'nest-wifi.json' in os.listdir('/'): os.rename('/nest-wifi.json','/nest-wifi.old')\ntry: os.rename('/nest-wifi.new','/nest-wifi.json')\nexcept OSError:\n if 'nest-wifi.old' in os.listdir('/'): os.rename('/nest-wifi.old','/nest-wifi.json')\n raise\nif 'nest-wifi.old' in os.listdir('/'): os.remove('/nest-wifi.old')\nprint('Wi-Fi configuration saved')")
        finally:
            board("exec","import os\nif 'nest-wifi.new' in os.listdir('/'): os.remove('/nest-wifi.new')","+","reset")

if __name__=="__main__":
    main()
