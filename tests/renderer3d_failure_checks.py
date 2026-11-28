"""Inject one consumed submit failure and one depth-target allocation failure."""
import ctypes.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE='''@main
#window
#os
ren #"github.com/xulang-org/nexus/rendering/three_d"
shaders #"github.com/xulang-org/nexus/assets/shaders/three_d"
fn failed_read(device $&ren.Device3D) bool {
    device.read_pixel(0,0) or(err){ assert(err.msg()=="gpu: injected consumed submit failure")
        println(err.msg())
        << true }
    << false
}
fn failed_begin(device $&ren.Device3D) bool {
    device.begin(255) or(err){ assert(err.msg()=="gpu: injected depth allocation failure")
        println(err.msg())
        << true }
    << false
}
fn run() int {
    args := os.args()
    program := shaders.load_mesh("build/mesh-shaders") >>>
    $device := ren.open_3d("3D failure recovery",64,64,0,&program) >>>
    device.begin(4278190335) >>>
    write_file(args[1]+"","submit") >>>
    assert(failed_read($&device))
    device.begin(16711935) >>>
    assert((device.read_pixel(0,0) >>>)==16711935)
    device.present() >>>
    target := device.window() >>>
    target.resize(96,80) >>>
    window.pump() >>>
    write_file(args[2]+"","depth") >>>
    assert(failed_begin($&device))
    device.begin(65535) >>>
    assert((device.read_pixel(95,79) >>>)==65535)
    device.present() >>>
    device.close() >>>
    assert((window.live_count() >>>)==0)
    println("PASS: consumed submit failure and partial resize allocation failure preserve errors and recover the next 3D frame")
    << 0
}
fn main() int { << run() or(err){ eprintln(err.msg())
    << 1 } }
'''
SHIM='''#include <SDL3/SDL.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <unistd.h>
static int armed(const char *name) {
 const char *path=getenv(name);
 if (!path || access(path,F_OK)) return 0;
 unlink(path);return 1;
}
SDL_GPUFence *SDL_SubmitGPUCommandBufferAndAcquireFence(SDL_GPUCommandBuffer *command) {
 if (armed("XU_TEST_GPU_SUBMIT_MARKER")) {
  SDL_CancelGPUCommandBuffer(command);SDL_SetError("injected consumed submit failure");return NULL;
 }
 void *library=dlopen(XU_TEST_REAL_SDL,RTLD_NOW|RTLD_LOCAL);
 SDL_GPUFence *(*real)(SDL_GPUCommandBuffer *)=dlsym(library,"SDL_SubmitGPUCommandBufferAndAcquireFence");
 return real(command);
}
SDL_GPUTexture *SDL_CreateGPUTexture(SDL_GPUDevice *device,const SDL_GPUTextureCreateInfo *info) {
 if (info->format==SDL_GPU_TEXTUREFORMAT_D32_FLOAT && armed("XU_TEST_GPU_DEPTH_MARKER")) {
  SDL_SetError("injected depth allocation failure");return NULL;
 }
 void *library=dlopen(XU_TEST_REAL_SDL,RTLD_NOW|RTLD_LOCAL);
 SDL_GPUTexture *(*real)(SDL_GPUDevice *,const SDL_GPUTextureCreateInfo *)=dlsym(library,"SDL_CreateGPUTexture");
 return real(device,info);
}
'''
if platform.system()!='Darwin':
    raise SystemExit('This Metal fault gate requires macOS; do not report other GPU backends as tested.')
with tempfile.TemporaryDirectory(prefix='xu 3D faults ') as directory:
    root=Path(directory)
    (root/'main.xu').write_text(SOURCE)
    (root/'shim.c').write_text(SHIM)
    sdk=next(line for line in (ROOT/'xu.xun').read_text().splitlines() if line.startswith('xu:'))
    (root/'xu.xun').write_text('module: example/three_d_failures\nversion: !ver 0.1.0\n'+sdk+'\nrequire:\n  "github.com/xulang-org/nexus": file:'+str(ROOT)+'\n')
    binary=root/'faults'
    subprocess.run([os.environ.get('XU','xu'),'build',str(root/'main.xu'),'--release','-o',str(binary)],cwd=ROOT,check=True,timeout=60)
    library=ctypes.util.find_library('SDL3')
    if not library:
        libdir=subprocess.check_output(['pkg-config','--variable=libdir','sdl3'],text=True).strip()
        for name in ('libSDL3.dylib','libSDL3.so'):
            candidate=Path(libdir)/name
            if candidate.exists():
                library=str(candidate)
                break
    if not library:
        raise SystemExit('SDL3 shared library not found')
    library=str(Path(library).resolve())
    flags=subprocess.check_output(['pkg-config','--cflags','sdl3'],text=True).split()
    shim=root/'fault SDL.dylib'
    cmd=[shutil.which('clang'),'-dynamiclib','-mmacosx-version-min=11.0','-std=c11','-Wall','-Wextra','-Werror',*flags,
         '-DXU_TEST_REAL_SDL="'+library+'"',str(root/'shim.c'),'-Wl,-reexport_library,'+library,'-o',str(shim)]
    if os.environ.get('XU_TEST_SYSROOT'):
        subprocess.run([*cmd,'-isysroot',os.environ['XU_TEST_SYSROOT']],check=True,timeout=60)
    else:
        compiled=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        xcode_sdk=Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk')
        if compiled.returncode!=0 and xcode_sdk.exists():
            subprocess.run([*cmd,'-isysroot',str(xcode_sdk)],check=True,timeout=60)
        elif compiled.returncode!=0:
            raise subprocess.CalledProcessError(compiled.returncode,cmd,compiled.stdout,compiled.stderr)
    submit=root/'submit marker';depth=root/'depth marker'
    env=os.environ | {'XU_SDL_LIBRARY':str(shim),'XU_TEST_GPU_SUBMIT_MARKER':str(submit),'XU_TEST_GPU_DEPTH_MARKER':str(depth)}
    subprocess.run([str(binary),str(submit),str(depth)],cwd=ROOT,env=env,check=True,timeout=60)

    assert not submit.exists() and not depth.exists(), "fault injection was not consumed"
