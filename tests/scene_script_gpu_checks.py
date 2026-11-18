from pathlib import Path
import hashlib
import json
import subprocess
root=Path(__file__).resolve().parents[1]
binary=root/'build/scene-scripts-demo';output=root/'build/scene-scripts/hot-saved.xuscene'
result=subprocess.run([str(binary),'--scene','build/scene-scripts/world.xuscene','--frames','120','--reload-at','60','--reload-from','next.xubc','--save',str(output),'--capture','build/scene-scripts-hot.png'],cwd=root,check=True,capture_output=True,text=True,timeout=45)
assert 'epoch=2; preserved calls=60' in result.stdout,result.stdout
assert 'calls=120; received=120; epoch=2; last=0.15' in result.stdout,result.stdout
scene=json.loads(output.read_text());script=next(r for r in scene['resources'] if r['uid']=='55005500550055005500550055005500')
assert script['path']=='next.xubc' and script['sha256']==hashlib.sha256((output.parent/'next.xubc').read_bytes()).hexdigest()
assert scene['version']==1 and len(scene['surfaces'])==8 and len(scene['audio_emitters'])==1 and len(scene['script_connections'])==1 and len(scene['lights'])==1
fresh=subprocess.run([str(binary),'--scene',str(output),'--frames','1'],cwd=root,check=True,capture_output=True,text=True,timeout=30)
assert 'calls=1; received=1; epoch=1; last=0.15' in fresh.stdout,fresh.stdout
print('PASS: real GPU/audio scene hot-reloads at frame 60 with state/routes intact, completes 120 callbacks/signals, saves accepted revision and restarts in a new process')
