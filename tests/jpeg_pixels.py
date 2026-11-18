from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'build/jpeg-fixtures'
for name in ('rgb444','rgb420','gray'):
 reference=Image.open(ROOT/(name+'.jpg')).convert('RGBA').tobytes();actual=(ROOT/(name+'.rgba')).read_bytes()
 assert len(actual)==len(reference)
 differences=[abs(a-b) for i,(a,b) in enumerate(zip(actual,reference)) if i%4!=3]
 mae=sum(differences)/len(differences);maximum=max(differences)
 assert mae<4 and maximum<24,(name,mae,maximum)
 assert all(a==255 for a in actual[3::4])
 print('PASS:',name,'JPEG vs independent libjpeg/Pillow mean error',round(mae,3),'max',maximum)
