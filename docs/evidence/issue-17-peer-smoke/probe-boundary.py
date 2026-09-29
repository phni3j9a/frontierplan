import socket, pathlib, urllib.request, json, subprocess
checks={}
r=subprocess.run(['/home/server/.local/bin/herdr','agent','get','fp-87624cc57b10-249b647355db'],capture_output=True,text=True)
checks['herdr']={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
assert r.returncode==0
p=pathlib.Path('.fp17-workspace-probe')
try: p.write_text('temporary boundary probe'); checks['workspace_write']=True
finally: p.unlink(missing_ok=True)
p=pathlib.Path('/home/server/projects/frontierplan/.fp17-outside-probe')
try:
 p.write_text('unexpected access'); p.unlink(); raise AssertionError('outside workspace write allowed')
except OSError as e:
 assert e.errno in (1,13,30), e
 checks['outside_write']=str(e)
s=socket.socket(); s.settimeout(2)
try:
 s.connect(('1.1.1.1',443)); raise AssertionError('direct internet socket allowed')
except OSError as e:
 assert e.errno in (1,13,101,111), e
 checks['direct_network']=str(e)
finally: s.close()
try:
 urllib.request.urlopen('https://github.com',timeout=8); raise AssertionError('empty domain policy allowed internet')
except urllib.error.URLError as e: checks['proxy_network']=str(e)
print(json.dumps(checks,indent=2))
