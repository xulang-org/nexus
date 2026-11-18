"""Optional independent importer/exporter check. Run in an isolated test venv.

Dependencies: trimesh==5.2.1 numpy==2.5.4. Not a product/runtime dependency.
Reference API: https://trimesh.org/trimesh.exchange.load.html
"""
from pathlib import Path
import hashlib,json,os,subprocess
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'build/mesh-format-fixtures'
OUT=ROOT/'build/model-format-oracle';OUT.mkdir(parents=True,exist_ok=True)
manifest=json.loads((FIXTURES/'manifest.json').read_text())
results=[]
for name,expected in manifest['models'].items():
    area=None
    for suffix in ('.glb','.obj','.ascii.stl','.binary.stl','.solid-header.stl'):
        source=FIXTURES/(name+suffix)
        mesh=trimesh.load_mesh(source,process=False)
        assert len(mesh.faces)==expected['triangles'],source
        assert np.array_equal(mesh.bounds,expected['bounds']),source
        if area is None:area=mesh.area
        assert np.isclose(mesh.area,area,rtol=1e-12,atol=1e-12),source
        results.append({'file':source.name,'triangles':len(mesh.faces),'area':float(mesh.area),'bounds':mesh.bounds.tolist()})

# A second exporter produces a curved, multi-face model consumed by the Xu
# loaders. Quantize once to binary32 so all formats encode identical positions.
mesh=trimesh.creation.icosphere(subdivisions=2)
mesh.vertices=(mesh.vertices*np.array([1.0,.75,1.25])).astype(np.float32).astype(np.float64)
# Supply the ellipsoid's analytic normals, avoiding Trimesh's optional SciPy
# normal-averaging dependency while still exporting explicit OBJ normals.
normals=mesh.vertices/np.array([1.0,.75,1.25])**2
mesh.vertex_normals=normals/np.linalg.norm(normals,axis=1)[:,None]
(OUT/'icosphere.obj').write_text(trimesh.exchange.obj.export_obj(mesh,include_normals=True,include_color=False,include_texture=False,digits=17))
(OUT/'icosphere.glb').write_bytes(mesh.export(file_type='glb'))
(OUT/'icosphere.ascii.stl').write_text(trimesh.exchange.stl.export_stl_ascii(mesh))
(OUT/'icosphere.binary.stl').write_bytes(mesh.export(file_type='stl'))
binary=OUT/'checks'
subprocess.run([os.environ.get('XU','xu'),'build','tests/mesh_format_oracle_checks.xu','-o',str(binary)],cwd=ROOT,check=True,timeout=60)
subprocess.run([str(binary),str(OUT)],cwd=ROOT,check=True,timeout=60)
reference=None;captures=[]
for suffix in ('.glb','.obj','.ascii.stl','.binary.stl'):
    path=OUT/('icosphere'+suffix);capture=OUT/(path.name+'.png');capture.unlink(missing_ok=True)
    run=subprocess.run([str(ROOT/'build/model-formats'),'--model',str(path),'--frames','1','--capture',str(capture)],cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert run.returncode==0 and 'triangles=320 frames=1' in run.stdout,run.stdout+run.stderr
    png=capture.read_bytes()
    assert png[:8]==b'\x89PNG\r\n\x1a\n'
    if reference is None:reference=png
    assert png==reference,('Independent export GPU mismatch',suffix)
    captures.append({'file':path.name,'png_sha256':hashlib.sha256(png).hexdigest()})
(OUT/'results.json').write_text(json.dumps({'trimesh':trimesh.__version__,'numpy':np.__version__,
    'independent_imports':results,'independent_exports':captures,'export_triangles':len(mesh.faces)},indent=2)+'\n')
print('PASS: Trimesh '+trimesh.__version__+' independently verifies 15 original files; its own 320-triangle exports load in Xu and render identical GLB/OBJ/ASCII-STL/binary-STL GPU PNGs')
