from pathlib import Path
from PIL import Image
import io
OUT=Path(__file__).resolve().parents[1]/'build/jpeg-fixtures';OUT.mkdir(parents=True,exist_ok=True)
image=Image.new('RGB',(19,11));image.putdata([(x*11,y*20,(x*5+y*9)%256) for y in range(11) for x in range(19)])
image.save(OUT/'rgb444.jpg',quality=95,subsampling=0)
image.save(OUT/'rgb420.jpg',quality=95,subsampling=2)
image.convert('L').save(OUT/'gray.jpg',quality=95)
image.save(OUT/'progressive.jpg',quality=95,progressive=True)
image.convert('CMYK').save(OUT/'cmyk.jpg')
raw=bytearray((OUT/'rgb444.jpg').read_bytes());at=raw.index(b'\xff\xc0')
raw[at+5:at+9]=b'\xff\xff\xff\xff';(OUT/'oversized.jpg').write_bytes(raw)
(OUT/'bad-marker.jpg').write_bytes(b'\xff\xd8x'+b'\0'*30)
(OUT/'not-jpeg.jpg').write_bytes(b'not a jpeg')
print('Prepared odd-size RGB 444/420/gray JPEG fixtures and codec/byte/dimension failures')
