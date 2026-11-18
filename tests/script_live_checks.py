import os, re, signal, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/script-live'
OUT.mkdir(parents=True,exist_ok=True)
source=OUT/'player.xus';schema=OUT/'schema.json';artifact=OUT/'player.xubc'
receiver_source=OUT/'indicator.xus';receiver_schema=OUT/'indicator.schema.json';receiver_artifact=OUT/'indicator.xubc'
original=(ROOT/'examples/script_reload/player.xus').read_text()
original_schema=(ROOT/'examples/script_reload/player.schema.json').read_text()
source.write_text(original);schema.write_text(original_schema)
receiver_original=(ROOT/'examples/script_reload/indicator.xus').read_text()
receiver_original_schema=(ROOT/'examples/script_reload/indicator.schema.json').read_text()
receiver_source.write_text(receiver_original);receiver_schema.write_text(receiver_original_schema)
command=[sys.executable,str(ROOT/'tools/watch_script.py'),'--tool',str(ROOT/'build/xu-nexus-script'),'--source',str(source),'--schema',str(schema),'--output',str(artifact)]
receiver_command=[sys.executable,str(ROOT/'tools/watch_script.py'),'--tool',str(ROOT/'build/xu-nexus-script'),'--source',str(receiver_source),'--schema',str(receiver_schema),'--output',str(receiver_artifact)]
for invocation in (command,receiver_command):
    first=subprocess.run(invocation+['--once'],cwd=ROOT,capture_output=True,text=True,timeout=8)
    assert first.returncode==0,first.stderr+first.stdout
baseline=artifact.read_bytes()
receiver_baseline=receiver_artifact.read_bytes()
watch_log=OUT/'watcher.log';game_log=OUT/'nexus.log'
receiver_watch_log=OUT/'receiver-watcher.log'

def wait_for(predicate,label,timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate():return
        if nexus.poll() is not None:raise AssertionError((label,'nexus exited',game_log.read_text()))
        time.sleep(.02)
    raise AssertionError((label,'timeout',game_log.read_text(),watch_log.read_text(),receiver_watch_log.read_text()))

with watch_log.open('w') as w,receiver_watch_log.open('w') as rw,game_log.open('w') as g:
    watcher=subprocess.Popen(command,cwd=ROOT,stdout=w,stderr=subprocess.STDOUT,start_new_session=True)
    receiver_watcher=subprocess.Popen(receiver_command,cwd=ROOT,stdout=rw,stderr=subprocess.STDOUT,start_new_session=True)
    nexus=subprocess.Popen([str(ROOT/'build/script-reload'),'--artifact',str(artifact),'--receiver-artifact',str(receiver_artifact),'--frames','300','--autoplay','--trace','--capture',str(OUT/'result.png')],cwd=ROOT,stdout=g,stderr=subprocess.STDOUT)
    try:
        wait_for(lambda:'frame=30 ' in game_log.read_text(),'initial movement')
        source.write_text('@scripts/player\npub struct Player {')
        wait_for(lambda:'compile rejected' in watch_log.read_text(),'isolated parse failure')
        assert artifact.read_bytes()==baseline,'bad source replaced active bytecode'
        wait_for(lambda:'frame=60 epoch=1' in game_log.read_text(),'old behavior continued')
        # The connection is stored by ID, so renaming the signal alongside the
        # behavior update must not require reconnecting the running host.
        schema.write_text(original_schema.replace('"moved"','"motion"'))
        source.write_text(original.replace('180.0','360.0').replace('"moved"','"motion"'))
        wait_for(lambda:'Script activated: epoch=2' in game_log.read_text(),'behavior update')
        valid_next=artifact.read_bytes()
        assert valid_next!=baseline
        activated=re.search(r'Script activated: epoch=2 calls=(\d+) x=([^ ]+) ticks_before=([^ ]+) ticks_after=([^\n]+)',game_log.read_text())
        assert activated and int(activated[1])>0 and float(activated[3])==float(activated[4]),activated
        assert float(activated[2])>160,'position was reset'
        # An invalid externally replaced artifact is rejected at a later safe point.
        artifact.write_bytes(b'invalid artifact')
        wait_for(lambda:'Script candidate rejected:' in game_log.read_text(),'artifact verification rejection')
        artifact.write_bytes(valid_next)
        wait_for(lambda:'frame=120 ' in game_log.read_text(),'receiver baseline')
        receiver_source.write_text('@scripts/indicator\npub struct Indicator {')
        wait_for(lambda:'compile rejected' in receiver_watch_log.read_text(),'isolated receiver parse failure')
        assert receiver_artifact.read_bytes()==receiver_baseline,'bad receiver source overwrote artifact'
        wait_for(lambda:'frame=150 ' in game_log.read_text(),'old receiver kept executing')
        receiver_schema.write_text(receiver_original_schema.replace('"on_moved"','"on_motion"'))
        receiver_source.write_text(receiver_original.replace('30.0','60.0').replace('on_moved','on_motion'))
        wait_for(lambda:'Receiver activated: epoch=2' in game_log.read_text(),'receiver behavior and name update')
        receiver_changed=re.search(r'Receiver activated: epoch=2 calls=(\d+) events_before=([^ ]+) events_after=([^\n]+)',game_log.read_text())
        assert receiver_changed and int(receiver_changed[1])>0 and float(receiver_changed[2])==float(receiver_changed[3]),receiver_changed
        nexus.wait(timeout=10)
        log=game_log.read_text()
        assert nexus.returncode==0,log
        assert 'Finished 300 script frames; epoch=2 calls=300' in log,log
        assert len(re.findall('Script activated:',log))==1,log
        assert 'frame=270 epoch=2 calls=271' in log,log
        rows=[(int(f),int(e),float(x)) for f,e,x in re.findall(r'Script step: frame=(\d+) epoch=(\d+) calls=\d+ x=([^ ]+)',log)]
        old=[(f,x) for f,e,x in rows if e==1 and f<120]
        new=[(f,x) for f,e,x in rows if e==2 and f<120]
        assert len(old)>=2 and abs((old[1][1]-old[0][1])/(old[1][0]-old[0][0])-3.0)<1e-6,rows
        measured=[]
        for (f1,e1,x1),(f2,e2,x2) in zip(rows,rows[1:]):
            if e1==e2==2 and f1//120==f2//120 and 69<x1<863 and 69<x2<863:
                measured.append(abs(x2-x1)/(f2-f1))
        assert any(abs(speed-6.0)<1e-6 for speed in measured),('new behavior did not double movement',rows,measured)
        signal_rows=[(int(f),int(count),float(value),int(connections)) for f,count,value,connections in re.findall(r'Script signals: frame=(\d+) delivered=(\d+) value=([^ ]+) connections=(\d+)',log)]
        assert len(signal_rows)==10,signal_rows
        for frame,count,value,connections in signal_rows:
            assert count==frame+1 and connections==1,signal_rows
            epoch=next(e for f,e,x in rows if f==frame)
            assert abs(abs(value)-(3.0 if epoch==1 else 6.0))<1e-6,signal_rows
        assert 'Signals delivered=300 connections=1' in log,log
        receiver_rows=[(int(f),int(e),float(offset)) for f,e,offset in re.findall(r'Script signals: frame=(\d+) delivered=\d+ value=[^ ]+ connections=\d+ receiver_epoch=(\d+) offset=([^\n]+)',log)]
        assert len(receiver_rows)==10 and any(e==2 for f,e,offset in receiver_rows),receiver_rows
        for frame,epoch,offset in receiver_rows:
            value=next(value for f,count,value,connections in signal_rows if f==frame)
            assert abs(offset-value*(30.0 if epoch==1 else 60.0))<1e-6,receiver_rows
        assert 'Receiver epoch=2 calls=300 events=300' in log,log
        assert len(re.findall('Receiver activated:',log))==1,log
        assert (OUT/'result.png').stat().st_size>100
        print('PASS: real GPU process survived both bad sources and bad artifact; sender speed 180->360 and receiver gain 30->60/handler rename hot-reloaded with state/connection preserved; 300 frames / 300 sender callbacks / 300 receiver callbacks / 300 delivered signals')
    finally:
        if nexus.poll() is None:nexus.terminate();nexus.wait(timeout=5)
        for process in (watcher,receiver_watcher):
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            process.wait(timeout=5)
