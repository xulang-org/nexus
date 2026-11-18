import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--core-only', action='store_true')
mode.add_argument('--device-only', action='store_true')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='xu-nexus-audio-isolation-') as temporary:
    target = Path(temporary)
    shutil.copyfile(ROOT / 'xu.xun', target / 'xu.xun')
    for name in ('foundation', 'resources/audio', 'formats/wav', 'audio/mixer', 'internal/file_snapshot', 'assets/audio'):
        shutil.copytree(ROOT / name, target / name)
    shutil.copytree(ROOT / 'build/audio-fixtures', target / 'build/audio-fixtures')
    shutil.copytree(ROOT / 'integration/audio_stream', target / 'integration/audio_stream')
    tool = os.environ.get('XU', 'xu')
    def check(name, source, environment=None, arguments=()):
        main = target / 'checks' / name / 'main.xu'
        main.parent.mkdir(parents=True)
        (main.parent / 'xu.xun').write_text(f'module: example/audio_{name}\nversion: !ver 0.1.0\nxu: !ver 0.12.3\nrequire:\n  "github.com/xulang-org/nexus": file:../..\n')
        shutil.copyfile(ROOT / 'tests' / source, main)
        binary = target / name
        subprocess.run([tool, 'build', str(main), '-o', str(binary)], cwd=target, check=True, timeout=60)
        subprocess.run([str(binary), *arguments], cwd=target, env=environment, check=True, timeout=20)
        return binary
    # CPU mixing, geometry, resources and format decoding need no native archives.
    environment = os.environ.copy()
    environment['XU_NEXUS_SDL_AUDIO_LIBRARY'] = '/nonexistent/audio-isolation'
    environment['XU_NEXUS_SDL_LIBRARY'] = '/nonexistent/gpu-isolation'
    if not args.device_only:
        check('wav', 'wav_checks.xu', environment)
        check('mixer', 'audio_mixer_checks.xu', environment)
        check('stream', 'audio_stream_checks.xu', environment)
        check('seek', 'audio_seek_checks.xu', environment)
        assert not (target / 'native').exists()
    if args.core_only:
        print('PASS: pure Xu WAV/mixer/streaming/seek without native archives or SDL')
        raise SystemExit(0)
    # Device playback adds only the audio ABI; still no GPU, scene, UI or scripts.
    shutil.copyfile(ROOT / 'audio/mod.xu', target / 'audio/mod.xu')
    shutil.copytree(ROOT / 'platform/sdl_audio', target / 'platform/sdl_audio')
    (target / 'native').mkdir()
    shutil.copyfile(ROOT / 'native/nexus_audio.xulib', target / 'native/nexus_audio.xulib')
    environment.pop('XU_NEXUS_SDL_AUDIO_LIBRARY')
    environment['SDL_AUDIO_DRIVER'] = 'dummy'
    environment['SDL_VIDEO_DRIVER'] = 'xu_no_video'
    binary = check('output', 'audio_output_checks.xu', environment)
    for overrides in ({'SDL_AUDIO_DRIVER': 'xu_no_audio'}, {'XU_NEXUS_SDL_AUDIO_LIBRARY': '/nonexistent/audio-isolation'}):
        rejected = environment | overrides
        subprocess.run([str(binary), '--expect-failure'], cwd=target, env=rejected, check=True, timeout=20)
    assert not (target / 'native/game_gpu.xulib').exists()
    assert not list(target.glob('*.xu')) and not (target / 'rendering').exists() and not (target / 'integration/audio').exists() and not (target / 'integration/rendering').exists()
    print('PASS: audio device output without GPU/scene/window/shader dependencies')
