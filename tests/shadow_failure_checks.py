"""Reuse the standard GPU fault shim without importing/executing its test."""
import ast,ctypes.util,os,platform,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if platform.system()!='Darwin':raise SystemExit('Metal fault check requires macOS; other backends remain unverified')
syntax=ast.parse((ROOT/'tests/renderer3d_failure_checks.py').read_text())
shim=next(ast.literal_eval(node.value) for node in syntax.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SHIM' for t in node.targets))
with tempfile.TemporaryDirectory(prefix='xu shadow faults ') as name:
 root=Path(name);(root/'shim.c').write_text(shim);binary=root/'checks'
 subprocess.run([os.environ.get('XU','xu'),'build','tests/shadow_failure_checks.xu','--release','-o',str(binary)],cwd=ROOT,check=True,timeout=60)
 library=ctypes.util.find_library('SDL3');assert library
 library=str(Path(library).resolve());flags=subprocess.check_output(['pkg-config','--cflags','sdl3'],text=True).split()
 if os.environ.get('XU_TEST_SYSROOT'):flags+=['-isysroot',os.environ['XU_TEST_SYSROOT']]
 override=root/'shadow SDL.dylib'
 subprocess.run([shutil.which('clang'),'-dynamiclib','-mmacosx-version-min=11.0','-std=c11','-Wall','-Wextra','-Werror',*flags,'-DXU_TEST_REAL_SDL="'+library+'"',str(root/'shim.c'),'-Wl,-reexport_library,'+library,'-o',str(override)],check=True,timeout=60)
 submit=root/'submit marker';depth=root/'depth marker';env=os.environ|{'XU_SDL_LIBRARY':str(override),'XU_TEST_GPU_SUBMIT_MARKER':str(submit),'XU_TEST_GPU_DEPTH_MARKER':str(depth)}
 subprocess.run([str(binary),str(submit),str(depth)],cwd=ROOT,env=env,check=True,timeout=60)
 assert not submit.exists() and not depth.exists()
