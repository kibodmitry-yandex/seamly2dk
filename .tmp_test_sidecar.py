from sidecar import Sidecar
import os, time
s=Sidecar('SlipMy.svg')
path=s.path
print('path',path)
try:
    t0=os.path.getmtime(path)
except Exception:
    t0=None
print('mtime before',t0)
s.save()
try:
    t1=os.path.getmtime(path)
except Exception:
    t1=None
print('mtime after first save',t1)
# wait and save again
time.sleep(1)
s.save()
try:
    t2=os.path.getmtime(path)
except Exception:
    t2=None
print('mtime after second save',t2)
print('changed on second save?', t2!=t1)
