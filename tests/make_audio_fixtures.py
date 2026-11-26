from pathlib import Path
import struct
import math
import json

out = Path(__file__).resolve().parents[1] / 'build/audio-fixtures'
out.mkdir(parents=True, exist_ok=True)
def chunk(tag, data): return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')
def wav(name, samples, bits, fmt=1, channels=1, rate=24000, extra=b'', reverse=False):
    if fmt == 3: payload=struct.pack('<'+'f'*len(samples),*samples)
    else: payload=b''.join(int(x).to_bytes(bits//8,'little',signed=bits != 8) for x in samples)
    alignment=channels*(bits//8)
    form=chunk(b'fmt ',struct.pack('<HHIIHH',fmt,channels,rate,rate*alignment,alignment,bits))
    data=chunk(b'data',payload)
    body=b'WAVE'+extra+(data+form if reverse else form+data)
    raw=b'RIFF'+struct.pack('<I',len(body))+body
    (out/name).write_bytes(raw)
    return raw

valid={
 'pcm8.wav': [-32768,0,32512],
 'pcm16.wav': [-32768,0,32767],
 'pcm24.wav': [-32768,0,32767],
 'pcm32.wav': [-32768,0,32767],
 'float.wav': [-32768,0,32767,16384],
 'stereo.wav': [1000,-2000,3000,-4000],
 'order.wav': [100,200],
}
base=wav('pcm16.wav',[-32768,0,32767],16)
wav('pcm8.wav',[0,128,255],8)
wav('pcm24.wav',[-8388608,0,8388607],24)
wav('pcm32.wav',[-2147483648,0,2147483647],32)
wav('float.wav',[-1,0,1,0.5],32,3)
wav('stereo.wav',[1000,-2000,3000,-4000],16,channels=2)
wav('order.wav',[100,200],16,extra=chunk(b'JUNK',b'x'),reverse=True)
wrong={}
wrong['short.wav']=b'RIFF'
wrong['tag.wav']=b'RIFX'+base[4:]
wrong['extent.wav']=base+b'junk'
wrong['truncated.wav']=base[:-1]
def replaced(offset, data):
    value=bytearray(base);value[offset:offset+len(data)]=data;return value
wrong['format.wav']=replaced(20,struct.pack('<H',65534))
wrong['channels.wav']=replaced(22,struct.pack('<H',3))
wrong['rate.wav']=replaced(24,struct.pack('<I',0))
wrong['byterate.wav']=replaced(28,struct.pack('<I',7))
wrong['alignment.wav']=replaced(32,struct.pack('<H',0))
wrong['bits.wav']=replaced(34,struct.pack('<H',12))
wrong['chunk-overflow.wav']=replaced(40,struct.pack('<I',0xffffffff))
for name,value in wrong.items(): (out/name).write_bytes(value)
wav('nan.wav',[math.nan],32,3);wrong['nan.wav']=b''
wav('float-over.wav',[2.0],32,3);wrong['float-over.wav']=b''
wav('empty.wav',[],16);wrong['empty.wav']=b''
fmt_chunk=base[12:36]
body=b'WAVE'+fmt_chunk+fmt_chunk+base[36:]
(out/'duplicate-fmt.wav').write_bytes(b'RIFF'+struct.pack('<I',len(body))+body);wrong['duplicate-fmt.wav']=b''
body=b'WAVE'+fmt_chunk+base[36:]+base[36:]
(out/'duplicate-data.wav').write_bytes(b'RIFF'+struct.pack('<I',len(body))+body);wrong['duplicate-data.wav']=b''
lines=['@main','', 'assets #"github.com/xulang-org/nexus/assets/audio"', '#os', '',
'fn rejected(name string) bool { assets.load_wav("build/audio-fixtures/" + name) or (err) { << true }', '    << false }', 'fn run() int {']
for name,expected in valid.items():
    var=name.split('.')[0]
    lines += [f'    {var} := assets.load_wav("build/audio-fixtures/{name}") or >>',f'    assert({var}.sample_count() == {len(expected)} && {var}.sample_rate() == 24000)']
    channels=2 if name=='stereo.wav' else 1
    for i,sample in enumerate(expected): lines += [f'    assert(({var}.sample({i//channels}, {i%channels}) or >>) == {sample})']
for name in wrong: lines += [f'    assert(rejected("{name}"))']
lines += [f'    println("PASS: PCM8/16/24/32, float WAV, stereo, odd/unknown chunks and order; {len(wrong)} malformed/unsupported WAV cases")','    << 0','}', 'fn main() int { << run() or (err) { eprintln(err.msg())','    << 1 } }']
(Path(__file__).resolve().parent/'wav_checks.xu').write_text('\n'.join(lines)+'\n')
print(f'WAV fixtures: {len(valid)} valid profiles, {len(wrong)} rejection cases')

# Sparse source larger than the static decoder limit, with known first/last frames.
frames = 12000000
data_bytes = frames * 4
head = b'RIFF' + struct.pack('<I', 36 + data_bytes) + b'WAVE' + chunk(b'fmt ', struct.pack('<HHIIHH', 1, 2, 48000, 192000, 4, 16)) + b'data' + struct.pack('<I', data_bytes)
with (out / 'large.wav').open('wb') as file:
    file.write(head)
    file.write(struct.pack('<hh', 11, -11))
    file.seek(44 + data_bytes - 8)
    file.write(struct.pack('<hhhh', 1000, -1000, 2000, -2000))
print('Sparse streamed WAV: 48 MB source with bounded random-access first/last frames')
