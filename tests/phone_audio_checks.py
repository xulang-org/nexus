from pathlib import Path
import os
import shlex
import shutil
import platform
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
XU=os.environ.get('XU','xu')
with tempfile.TemporaryDirectory(prefix='phone audio ') as temporary:
    directory=Path(temporary)
    sdk=Path(shutil.which(XU)).resolve().parents[1]
    include=sdk/'include'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','sdl3'],text=True))
    system_flags=[]
    if platform.system()=='Darwin':
        system_flags=['-isysroot',subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()]
    binary=directory/'audio-test'
    subprocess.run(['clang',*system_flags,'-std=c11','-Wall','-Wextra','-Werror','-iquote'+str(include),
                    ROOT/'tests/phone_audio_lifecycle.c',*flags,'-o',binary],check=True)
    subprocess.run([binary],env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),check=True,timeout=25)
