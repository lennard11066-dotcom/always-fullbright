"""Build one Java-21 Fabric JAR, then verify it on locally installed game versions.

No libraries or Minecraft classes are bundled in the mod. FULLBRIGHT_MC,
FULLBRIGHT_META and FULLBRIGHT_JDK can override local installation directories.
"""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
MC = Path(os.environ.get('FULLBRIGHT_MC', HOME / 'AppData/Roaming/.minecraft'))
META = Path(os.environ.get('FULLBRIGHT_META', HOME / 'AppData/Roaming/ModrinthApp/meta'))
JDK = Path(os.environ.get('FULLBRIGHT_JDK', HOME / '.jdks/corretto-26.0.2.1')) / 'bin'
CACHE = HOME / '.gradle/caches/modules-2/files-2.1'
LOADER_VERSION = '0.20.1'
MIXIN_VERSION = '0.17.5+mixin.0.8.7'
ASM_VERSION = '9.10.1'


def artifact(group, name, version):
    glob = f'{group}/{name}/{version}/*/{name}-{version}.jar'
    matches = list(CACHE.glob(glob))
    if matches:
        return matches[0]
    candidate = META / 'libraries' / group.replace('.', '/') / name / version / f'{name}-{version}.jar'
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f'Missing local dependency: {group}:{name}:{version}')


LOADER = artifact('net.fabricmc', 'fabric-loader', LOADER_VERSION)
MIXIN = artifact('net.fabricmc', 'sponge-mixin', MIXIN_VERSION)
ASM = [artifact('org.ow2.asm', n, ASM_VERSION)
       for n in ['asm', 'asm-tree', 'asm-commons', 'asm-util', 'asm-analysis']]
BOOTSTRAP = [LOADER, MIXIN, *ASM]
BUILD = ROOT / 'build/universal-1.1.0'
CLASSES = BUILD / 'classes'
TESTS = BUILD / 'tests'
OUTPUT = ROOT / 'build/libs/always-fullbright-1.1.0-mc1.21.11-26.3.jar'
SUPPORTED = ['1.21.11', '26.1', '26.1.1', '26.1.2', '26.2', '26.3']


def context(version):
    version_dir = MC / 'versions' / version
    game = version_dir / f'{version}.jar'
    manifest = version_dir / f'{version}.json'
    if not game.is_file() or not manifest.is_file():
        variants = sorted((META / 'versions').glob(f'{version}-*'))
        variants = [p for p in variants if (p / (p.name + '.jar')).is_file()]
        if not variants:
            raise FileNotFoundError(f'Minecraft {version} is not installed locally')
        version_dir = variants[-1]
        game = version_dir / (version_dir.name + '.jar')
        manifest = version_dir / (version_dir.name + '.json')
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    libraries = []
    for lib in metadata['libraries']:
        name = lib.get('name', '')
        if name.startswith(('net.fabricmc:', 'org.ow2.asm:')):
            continue
        relative = lib.get('downloads', {}).get('artifact', {}).get('path')
        if not relative:
            parts = name.split(':')
            if len(parts) != 3:
                continue
            group, package, ver = parts
            relative = f'{group.replace(".", "/")}/{package}/{ver}/{package}-{ver}.jar'
        for base in [MC / 'libraries', META / 'libraries']:
            candidate = base / relative
            if candidate.is_file():
                libraries.append(candidate)
                break
    if version == '1.21.11':
        libraries.append(ROOT.parent / 'hf11-deps/intermediary.jar')
    cp = os.pathsep.join(map(str, dict.fromkeys([game, *BOOTSTRAP, *libraries])))
    return {'version': version, 'game': game, 'classpath': cp}


def run(exe, args, name, java_bin=None):
    argfile = BUILD / (name + '.args')
    argfile.write_text('\n'.join('"' + str(a).replace('\\', '\\\\').replace('"', '\\"') + '"'
                                 for a in args), encoding='utf-8')
    result = subprocess.run([str((java_bin or JDK) / exe), '@' + str(argfile)], cwd=BUILD,
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=120)
    (BUILD / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout, end='', flush=True)
    print(result.stderr, end='', flush=True)
    result.check_returncode()
    return result.stdout


def smoke(ctx, mods=None, label=None):
    label = label or ctx['version']
    directory = BUILD / ('smoke-' + label)
    directory.mkdir(exist_ok=True)
    if ctx['version'] == '1.21.11':
        # Reuse the existing, exactly matching intermediary game bytecode.
        # Windows sandbox ACL probes can make Java ZipFS report new files as
        # read-only; Python can assemble the same local Fabric cache normally.
        old_input = ROOT.parent / 'hf11-deps/minecraft-client.jar'
        old_mapped = ROOT.parent / 'hf11-deps/minecraft-intermediary.jar'
        if old_input.is_file() and old_mapped.is_file():
            assert hashlib.sha1(old_input.read_bytes()).digest() == hashlib.sha1(ctx['game'].read_bytes()).digest()
            cache = directory / '.fabric/remappedJars' / ('minecraft-1.21.11-' + LOADER_VERSION)
            cache.mkdir(parents=True, exist_ok=True)
            destination = cache / 'client-intermediary.jar'
            with zipfile.ZipFile(old_mapped) as mapped, zipfile.ZipFile(ctx['game']) as original:
                assert 'net/minecraft/class_765.class' in mapped.namelist()
                with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as output:
                    for name in mapped.namelist():
                        if name.endswith('.class'):
                            output.writestr(name, mapped.read(name))
                    for name in original.namelist():
                        if not name.endswith('.class') and not name.startswith('META-INF/'):
                            output.writestr(name, original.read(name))
            destination.with_suffix('.jar.tmp').unlink(missing_ok=True)
    return run('java.exe', ['-Djava.awt.headless=true', '--enable-native-access=ALL-UNNAMED',
               '-Dfabric.gameJarPath=' + str(ctx['game']),
               '-Dfabric.addMods=' + os.pathsep.join(map(str, mods or [OUTPUT])),
               '-Dfabric.log.disableAnsi=true', '-Dfullbright.version=' + ctx['version'],
               '-cp', str(TESTS) + os.pathsep + ctx['classpath'], 'de.lenna.fullbright.LoaderCheck',
               '--gameDir', directory, '--version', ctx['version'], '--assetsDir', MC / 'assets'],
               'loader-' + label, java_bin=(HOME / '.jdks/ms-21.0.12.1/bin')
               if ctx['version'] == '1.21.11' and (HOME / '.jdks/ms-21.0.12.1/bin/java.exe').is_file()
               else None)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    CLASSES.mkdir(parents=True, exist_ok=True)
    TESTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    contexts = {v: context(v) for v in ['1.21.11', '26.1.2', '26.2', '26.3']}
    common = ['--release', '21', '-encoding', 'UTF-8', '-proc:none', '-implicit:none']
    run('javac.exe', [*common, '-cp', contexts['26.3']['classpath'], '-d', CLASSES,
                     *sorted((ROOT / 'src/main/java').rglob('*.java'))], 'compile-modern')
    run('javac.exe', [*common, '-cp', contexts['1.21.11']['classpath'], '-d', CLASSES,
                     *sorted((ROOT / 'src/legacy/java').rglob('*.java'))], 'compile-legacy')
    run('javac.exe', [*common, '-cp', contexts['26.3']['classpath'], '-d', TESTS,
                     *sorted((ROOT / 'src/test/java').rglob('*.java'))], 'compile-checks')
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as z:
        def add(path, name):
            info = zipfile.ZipInfo(name, (2026, 11, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
        for path in sorted(CLASSES.rglob('*.class')):
            add(path, path.relative_to(CLASSES).as_posix())
        for path in sorted((ROOT / 'src/main/resources').rglob('*')):
            if path.is_file():
                add(path, path.relative_to(ROOT / 'src/main/resources').as_posix())
        for path in sorted((ROOT / 'src').rglob('*')):
            if path.is_file():
                add(path, 'META-INF/sources/' + path.relative_to(ROOT).as_posix())
        for name in ['README.md', 'LICENSE', 'CHANGELOG.md', 'build_universal.py', 'build.py']:
            add(ROOT / name, name if not name.endswith('.py') else 'META-INF/sources/' + name)
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        metadata = json.loads(z.read('fabric.mod.json'))
        assert metadata['depends']['minecraft'] == SUPPORTED
        assert metadata['version'] == '1.1.0'
        icon = z.read(metadata['icon'])
        assert icon[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', icon[16:24]) == (256, 256)
        for name in z.namelist():
            if name.endswith('.class'):
                assert name.startswith('de/lenna/fullbright/')
                assert struct.unpack('>H', z.read(name)[6:8])[0] == 65
    for ctx in contexts.values():
        smoke(ctx)
    profile = HOME / 'AppData/Roaming/ModrinthApp/profiles/testen 26.3/mods'
    sodium = profile / 'sodium-fabric-0.9.2+mc26.3.jar'
    api = profile / 'fabric-api-0.165.2+26.3.jar'
    if sodium.is_file() and api.is_file():
        smoke(contexts['26.3'], [OUTPUT, sodium, api], '26.3-sodium-0.9.2')
    report = {'file': str(OUTPUT), 'bytes': OUTPUT.stat().st_size,
              'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
              'supported_versions': SUPPORTED, 'runtime_checked': list(contexts),
              'java_bytecode': 21, 'fabric_loader': LOADER_VERSION,
              'sodium_26_3_loader_check': sodium.is_file() and api.is_file(),
              'limitations': ['26.1 and 26.1.1 share the 26.1.x renderer; exact binaries not available locally.',
                              'No graphical playtest of this new release; older Sodium versions not installed.']}
    (BUILD / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
