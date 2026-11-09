"""Conservative Arch package orchestration; no third-party Python dependencies.

The filesystem and command runner are injectable for offline transaction tests.
The public CLI only mutates the running root, never an arbitrary mounted root.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
STATE = '/var/lib/a1708-setup'
BOOT = '/etc/limine-entry-tool.d/90-a1708-sleep.conf'
FILES = {
    BOOT: (b'# Managed by a1708-setup: MacBookPro14,1 EFI S3 workaround.\n'
           b'KERNEL_CMDLINE[default]+=" mem_sleep_default=s2idle"\n', 0o644),
    '/etc/wireplumber/wireplumber.conf.d/51-cs8409-no-suspend.conf':
        ((REPO / 'audio/51-cs8409-no-suspend.conf').read_bytes(), 0o644),
    '/usr/lib/systemd/system-sleep/macbook-keyboard-backlight':
        ((REPO / 'keyboard-backlight/macbook-keyboard-backlight').read_bytes(), 0o755),
}
MODULES = [('snd_hda_macbookpro', '0.1.resume1', 'snd_hda_codec_cs8409'),
           ('tb-ar-shim', '1.0.0', 'tb_ar_shim')]
PACKAGES = {'a1708-audio-dkms': '0.1.resume1-1', 'tb-ar-shim-dkms': '1.0.0-1'}
DEPENDENCIES = ['dkms', 'wget', 'patch', 'wireplumber']


class SetupError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(argv, check=True, cwd=None, env=None):
    try:
        result = subprocess.run([str(a) for a in argv], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=cwd, env=env)
    except FileNotFoundError as error:
        if check:
            raise SetupError(str(error)) from error
        return subprocess.CompletedProcess(argv, 127, '', str(error))
    if check and result.returncode:
        raise SetupError(f"Command failed ({result.returncode}): {' '.join(map(str, argv))}\n"
                         f'{result.stdout}{result.stderr}')
    return result


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def build(output):
    if os.geteuid() == 0:
        raise SetupError('Build as an ordinary user; makepkg must not run as root.')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packages = []
    # Each staged recipe stands alone, including in a clean build chroot.
    for name, recipe in [('a1708-audio-dkms', 'audio'), ('tb-ar-shim-dkms', 'thunderbolt')]:
        stage = output / name
        stage.mkdir(exist_ok=True)
        shutil.copy2(REPO / recipe / 'packaging/arch/PKGBUILD', stage / 'PKGBUILD')
        if recipe == 'audio':
            shutil.copy2(REPO / 'audio/patches/audio-system-resume.diff', stage)
        env = os.environ.copy()
        env['PKGDEST'] = str(output)
        env['SRCDEST'] = str(output / 'sources')
        Path(env['SRCDEST']).mkdir(exist_ok=True)
        result = run(['makepkg', '--cleanbuild', '--force', '--nodeps'], cwd=stage, env=env)
        print(result.stdout, end='', file=sys.stderr)
        paths = run(['makepkg', '--packagelist'], cwd=stage, env=env).stdout.splitlines()
        for entry in paths:
            package = Path(entry)
            info = run(['pacman', '-Qp', package]).stdout.split()
            if info != [name, PACKAGES[name]]:
                raise SetupError(f'Unexpected package metadata: {info}')
            packages.append({'name': name, 'version': info[1], 'file': package.name,
                             'sha256': digest(package)})
    # Fingerprints let an existing manual audio source be adopted without moving it.
    with tempfile.TemporaryDirectory() as tmp:
        run(['bsdtar', '-xf', output / packages[0]['file'], '-C', tmp])
        source = Path(tmp) / 'usr/src/snd_hda_macbookpro-0.1.resume1'
        fingerprints = {str(p.relative_to(source)): digest(p)
                        for p in sorted(source.rglob('*')) if p.is_file()}
    manifest = {'schema': 1, 'packages': packages, 'audio_source': fingerprints,
                'configuration': {p: hashlib.sha256(data).hexdigest()
                                  for p, (data, _) in FILES.items()}}
    atomic_json(output / 'bundle.json', manifest)
    print(json.dumps({'bundle': str(output / 'bundle.json')}, indent=2))


class Machine:
    def __init__(self, root=Path('/'), runner=run):
        self.root = Path(root)
        self.run = runner

    def path(self, name):
        return self.root / name.lstrip('/')

    def read(self, name):
        try:
            return self.path(name).read_text().strip()
        except (FileNotFoundError, PermissionError):
            return ''

    def packages(self):
        result = self.run(['pacman', '-Q'], check=False)
        if result.returncode:
            raise SetupError('Cannot read the package database: ' + result.stderr)
        return dict(line.split(maxsplit=1) for line in result.stdout.splitlines())

    def kernels(self):
        result = []
        for tree in sorted(self.path('/usr/lib/modules').glob('*')):
            base = tree / 'pkgbase'
            if base.is_file():
                result.append({'version': tree.name, 'package': base.read_text().strip(),
                               'headers': (tree / 'build/Makefile').is_file()})
        return result

    def inspect(self):
        return {'model': self.read('/sys/class/dmi/id/product_name'),
                'os': self.read('/etc/os-release'),
                'kernels': self.kernels(), 'packages': {k: v for k, v in self.packages().items()
                    if k in set(PACKAGES) | set(DEPENDENCIES) | {'omarchy', 'wireplumber'}
                    | {x['package'] for x in self.kernels()}
                    | {x['package'] + '-headers' for x in self.kernels()}},
                'dkms': self.run(['dkms', 'status'], check=False).stdout,
                'sleep': self.read('/sys/power/mem_sleep')}

    def bundle(self, directory):
        directory = Path(directory).resolve()
        manifest = json.loads((directory / 'bundle.json').read_text())
        if manifest.get('schema') != 1:
            raise SetupError('Unsupported bundle schema')
        if manifest.get('configuration') != {p: hashlib.sha256(d).hexdigest()
                                             for p, (d, _) in FILES.items()}:
            raise SetupError('Bundle configuration differs from this checkout; rebuild it.')
        expected = dict(PACKAGES)
        for item in manifest.get('packages', []):
            name = item['name']
            if expected.pop(name, None) != item['version']:
                raise SetupError('Unexpected/duplicate package in bundle')
            if Path(item['file']).name != item['file']:
                raise SetupError('Package filename must be a basename')
            package = directory / item['file']
            if digest(package) != item['sha256']:
                raise SetupError(f'Package checksum mismatch: {name}')
            if self.run(['pacman', '-Qp', package]).stdout.split() != [name, item['version']]:
                raise SetupError(f'Package identity mismatch: {name}')
        if expected or not manifest.get('audio_source'):
            raise SetupError('Incomplete bundle')
        return manifest

    def manual_audio(self, fingerprints):
        source = self.path('/usr/src/snd_hda_macbookpro-0.1.resume1')
        if not source.exists():
            return False
        # Do not accept a modified or incomplete source tree based only on its name.
        for relative, checksum in fingerprints.items():
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise SetupError('Invalid source fingerprint path')
            path = source / relative
            if not path.is_file() or digest(path) != checksum:
                return False
        return True

    def previous_archive(self, name, version):
        for path in sorted(self.path('/var/cache/pacman/pkg').glob(f'{name}-*.pkg.tar.*')):
            if path.name.endswith('.sig'):
                continue
            if self.run(['pacman', '-Qp', path], check=False).stdout.split() == [name, version]:
                return path
        return None

    def plan(self, directory):
        manifest = self.bundle(directory)
        facts = self.inspect()
        blockers = []
        for variable in self.path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
            data = variable.read_bytes()
            if len(data) > 4 and data[4] == 1:
                blockers.append('Secure Boot is enabled; module signing is not supported by this installer.')
        if facts['model'] != 'MacBookPro14,1':
            blockers.append('Only MacBookPro14,1 is supported; hardware override is unavailable.')
        if not re.search(r'^ID=\"?omarchy\"?$', facts['os'], re.M):
            blockers.append('This installer supports Omarchy only.')
        pci = {(self.read(str(p.relative_to(self.root)) + '/vendor'),
                self.read(str(p.relative_to(self.root)) + '/device'))
               for p in self.path('/sys/bus/pci/devices').glob('*')}
        if ('0x8086', '0x1578') not in pci:
            blockers.append('Expected Alpine Ridge PCI bridge 8086:1578 is absent.')
        codecs = list(self.path('/proc/asound').glob('card*/codec*'))
        if not any('0x10138409' in p.read_text() for p in codecs if p.is_file()):
            blockers.append('Expected CS8409 codec ID 0x10138409 is absent.')
        if not self.path('/usr/bin/limine-mkinitcpio').is_file():
            blockers.append('limine-mkinitcpio is required.')
        if not facts['kernels']:
            blockers.append('No installed kernel with pkgbase was found.')
        for kernel in facts['kernels']:
            if not kernel['headers']:
                blockers.append(f"Missing matching headers for {kernel['version']} "
                                f"(usually {kernel['package']}-headers).")
        for dep in DEPENDENCIES:
            if dep not in facts['packages']:
                blockers.append(f'Missing prerequisite package: {dep}')
        package_actions = []
        adopted = False
        for item in manifest['packages']:
            previous = facts['packages'].get(item['name'])
            action = 'keep' if previous == item['version'] else 'install'
            archive = None
            if previous and action == 'install':
                archive = self.previous_archive(item['name'], previous)
                if archive is None:
                    blockers.append(f"Rollback archive missing for {item['name']} {previous}")
            if item['name'] == 'a1708-audio-dkms' and not previous:
                audio_lines = [line for line in facts['dkms'].splitlines()
                               if line.startswith('snd_hda_macbookpro/')]
                if audio_lines or self.path('/usr/src/snd_hda_macbookpro-0.1.resume1').exists():
                    if self.manual_audio(manifest['audio_source']) and all(
                            line.startswith('snd_hda_macbookpro/0.1.resume1,')
                            for line in audio_lines):
                        action = 'adopt'
                        adopted = True
                        for kernel in facts['kernels']:
                            if not self.installed('snd_hda_macbookpro', '0.1.resume1', kernel['version']):
                                blockers.append('Manual audio must already be installed for ' + kernel['version']
                                                + '; rebuild it using docs/installation.md before adoption.')
                    else:
                        blockers.append('Existing manual audio source/version differs; preserve and resolve it before apply.')
            package_actions.append({**item, 'action': action, 'previous': previous,
                                    'previous_archive': str(archive) if archive else None})
        # Reject competing audio DKMS versions even when a package is present.
        for line in facts['dkms'].splitlines():
            if line.startswith('snd_hda_macbookpro/') and not line.startswith('snd_hda_macbookpro/0.1.resume1,'):
                blockers.append('Competing audio DKMS version: ' + line)
            if line.startswith('tb-ar-shim/') and not line.startswith('tb-ar-shim/1.0.0,'):
                blockers.append('Competing Thunderbolt DKMS version: ' + line)
        file_actions = []
        for name, (content, mode) in FILES.items():
            path = self.path(name)
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != self.root):
                blockers.append(f'Symlink at managed path or parent: {name}')
                continue
            if path.exists() and not path.is_file():
                blockers.append(f'Not a regular file: {name}')
                continue
            if path.is_file() and path.read_bytes() != content:
                # Preserve and stop on unknown content; do not overwrite custom configuration.
                blockers.append(f'Conflicting configuration: {name}')
            file_actions.append({'path': name, 'action': 'keep' if path.is_file()
                                 and path.read_bytes() == content and path.stat().st_mode & 0o777 == mode
                                 else 'write'})
        # Limine loads /etc/default/limine after all drop-ins. A replacement
        # assignment there discards the s2idle argument installed above.
        default_config = self.read('/etc/default/limine')
        if re.search(r'^\s*KERNEL_CMDLINE\[default\]\s*=', default_config, re.M):
            blockers.append('/etc/default/limine replaces the default command line after drop-ins; '
                            'review its KERNEL_CMDLINE[default]= assignment and use += to retain drop-in arguments.')
        for path in self.path('/etc/limine-entry-tool.d').glob('*.conf'):
            if path == self.path(BOOT):
                continue
            values = re.findall(r'mem_sleep_default=([^\s\"\'\\]+)', path.read_text())
            if any(value != 's2idle' for value in values):
                blockers.append('Conflicting sleep default in ' + str(path))
        return {'schema': 1, 'facts': facts, 'blockers': sorted(set(blockers)),
                'packages': package_actions, 'files': file_actions,
                'adopt_manual_audio': adopted,
                'note': 'No changes made. Apply never reboots, suspends, or reloads live audio.'}

    def installed(self, module, version, kernel):
        lines = self.run(['dkms', 'status', '-m', module, '-v', version, '-k', kernel], check=False).stdout
        return any(line.startswith(f'{module}/{version}, {kernel}, ') and
                   ': installed' in line for line in lines.splitlines())

    def ensure_modules(self, kernels):
        for kernel in kernels:
            for module, version, _ in MODULES:
                if not self.installed(module, version, kernel['version']):
                    self.run(['dkms', 'install', '-m', module, '-v', version, '-k', kernel['version']])
                if not self.installed(module, version, kernel['version']):
                    raise SetupError(f'DKMS did not install {module}/{version} for {kernel["version"]}')

    def save(self, state):
        atomic_json(self.path(STATE + '/transaction.json'), state)

    def apply(self, directory):
        plan = self.plan(directory)
        if plan['blockers']:
            raise SetupError('Preflight blocked:\n' + '\n'.join(plan['blockers']))
        journal = self.path(STATE + '/transaction.json')
        if journal.exists():
            old = json.loads(journal.read_text())
            if old['status'] != 'rolled-back':
                if old['status'] == 'complete' and old.get('kernels') == plan['facts']['kernels'] and all(p['action'] in ('keep', 'adopt') for p in plan['packages']) and all(f['action'] == 'keep' for f in plan['files']):
                    if any(not self.installed(m, v, k['version'])
                           for k in plan['facts']['kernels'] for m, v, _ in MODULES):
                        raise SetupError('DKMS state changed since apply; investigate before repairing.')
                    return {'status': 'unchanged', 'message': 'Existing rollback baseline preserved.'}
                raise SetupError('Existing transaction needs rollback before another changed apply; see transaction.json.')
        state = {'schema': 1, 'status': 'in-progress', 'started': int(time.time()),
                 'packages': [], 'files': [], 'kernels': plan['facts']['kernels'],
                 'adopt_manual_audio': plan['adopt_manual_audio'], 'error': None}
        self.save(state)
        try:
            packages = []
            for item in plan['packages']:
                if item['action'] != 'install':
                    continue
                record = dict(item)
                if item['previous_archive']:
                    archive = self.path(STATE + '/previous-' + Path(item['previous_archive']).name)
                    shutil.copy2(item['previous_archive'], archive)
                    record['previous_archive'] = str(archive)
                    record['previous_sha256'] = digest(archive)
                state['packages'].append(record)
                self.save(state)  # intent is durable before pacman (including hook failure)
                packages.append(str(Path(directory).resolve() / item['file']))
            if packages:
                self.run(['pacman', '-U', '--noconfirm', *packages])
            self.ensure_modules(state['kernels'])
            state['status'] = 'modules-installed'
            self.save(state)
            for item in plan['files']:
                if item['action'] == 'keep':
                    continue
                name = item['path']
                path = self.path(name)
                content, mode = FILES[name]
                previous = None
                if path.exists():
                    previous = {'data': base64.b64encode(path.read_bytes()).decode(),
                                'mode': path.stat().st_mode & 0o777}
                state['files'].append({'path': name, 'previous': previous,
                                       'sha256': hashlib.sha256(content).hexdigest(), 'mode': mode})
                self.save(state)
                missing = []
                parent = path.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir(mode=0o755)
                    parent.chmod(0o755)  # system config must remain readable despite root-only journal umask
                temp = path.with_name(path.name + '.a1708-new')
                with open(temp, 'xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                temp.chmod(mode)
                os.replace(temp, path)
            state['status'] = 'boot-rebuild-pending'
            self.save(state)
            # Package hooks may have rebuilt earlier; this rebuild includes our boot drop-in.
            self.run(['limine-mkinitcpio'])
            state['status'] = 'complete'
            self.save(state)
            return {'status': 'complete', 'reboot_required': True,
                    'message': 'Reboot before sleep testing, log into the desktop, then run verify.'}
        except Exception as error:
            state['error'] = str(error)
            self.save(state)
            raise

    def rollback(self):
        journal = self.path(STATE + '/transaction.json')
        if not journal.exists():
            raise SetupError('No transaction to roll back.')
        state = json.loads(journal.read_text())
        if state['status'] == 'rolled-back':
            return {'status': 'unchanged'}
        # Check all drift before the first rollback mutation.
        installed = self.packages()
        for item in state['packages']:
            current = installed.get(item['name'])
            if current not in (None, item['version'], item['previous']):
                raise SetupError('Package changed since apply: ' + item['name'])
            if item['previous']:
                archive = Path(item['previous_archive'])
                if not archive.is_file() or digest(archive) != item['previous_sha256']:
                    raise SetupError('Previous package archive is missing or modified: ' + str(archive))
        for item in state['files']:
            path = self.path(item['path'])
            previous = item['previous']
            if path.is_symlink():
                raise SetupError('Managed file became a symlink: ' + str(path))
            if path.exists():
                current_mode = path.stat().st_mode & 0o777
                applied = digest(path) == item['sha256'] and current_mode == item['mode']
                restored = (previous and path.read_bytes() == base64.b64decode(previous['data'])
                            and current_mode == previous['mode'])
                if not applied and not restored:
                    raise SetupError('File changed since apply: ' + str(path))
        state['status'] = 'rollback-in-progress'
        self.save(state)
        try:
            for item in reversed(state['packages']):
                current = self.packages().get(item['name'])
                if current == item['previous']:
                    continue
                if item['previous']:
                    self.run(['pacman', '-U', '--noconfirm', item['previous_archive']])
                elif current:
                    self.run(['pacman', '-R', '--noconfirm', item['name']])
            for item in reversed(state['files']):
                path = self.path(item['path'])
                if item['previous']:
                    path.write_bytes(base64.b64decode(item['previous']['data']))
                    path.chmod(item['previous']['mode'])
                else:
                    path.unlink(missing_ok=True)
                path.with_name(path.name + '.a1708-new').unlink(missing_ok=True)
            self.run(['limine-mkinitcpio'])
            state['status'] = 'rolled-back'
            state['error'] = None
            self.save(state)
        except Exception as error:
            state['error'] = str(error)
            self.save(state)
            raise
        return {'status': 'rolled-back', 'reboot_required': True,
                'message': 'Pre-existing packages, manual drivers and unrelated configuration were retained.'}

    def verify(self):
        facts = self.inspect()
        checks = []
        def check(name, passed):
            checks.append({'check': name, 'passed': bool(passed)})
        check('model MacBookPro14,1', facts['model'] == 'MacBookPro14,1')
        check('installed kernels found', facts['kernels'])
        for kernel in facts['kernels']:
            check('headers ' + kernel['version'], kernel['headers'])
            for module, version, modname in MODULES:
                check(f'{module}/{version} installed for {kernel["version"]}',
                      self.installed(module, version, kernel['version']))
                info = self.run(['modinfo', '-k', kernel['version'], '-F', 'filename', modname], check=False)
                check(f'{modname} resolves to DKMS for {kernel["version"]}',
                      info.returncode == 0 and '/updates/' in info.stdout)
        for name, (data, mode) in FILES.items():
            path = self.path(name)
            check(name, path.is_file() and not path.is_symlink() and path.read_bytes() == data
                  and path.stat().st_mode & 0o777 == mode)
        check('s2idle active', '[s2idle]' in facts['sleep'])
        check('s2idle in running command line', 'mem_sleep_default=s2idle' in self.read('/proc/cmdline').split())
        for _, _, module in MODULES:
            check(module + ' loaded', self.path('/sys/module/' + module).is_dir())
        return {'checks': checks, 'passed': all(c['passed'] for c in checks),
                'hardware_tests': 'PENDING: acoustics, lid close/wake, USB-C peripherals, battery drain.',
                'facts': facts}


def main():
    parser = argparse.ArgumentParser(description='Experimental MacBookPro14,1 Omarchy setup (see docs/setup.md).')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'verify', 'rollback'):
        sub.add_parser(name)
    p = sub.add_parser('build', help='Build packages as a normal user; changes no host packages')
    p.add_argument('--output', type=Path, default=REPO / 'local/setup-bundle')
    for name in ('plan', 'apply'):
        p = sub.add_parser(name)
        p.add_argument('--bundle', type=Path, default=REPO / 'local/setup-bundle')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            build(args.output)
            return
        machine = Machine()
        if args.command in ('apply', 'rollback'):
            if os.geteuid() != 0:
                raise SetupError('Run apply/rollback through sudo in your terminal; other commands need no root.')
            os.umask(0o077)
            state_dir = machine.path(STATE)
            if state_dir.is_symlink():
                raise SetupError('State directory must not be a symlink.')
            state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            if state_dir.stat().st_uid != 0 or state_dir.stat().st_mode & 0o077:
                raise SetupError('State directory must be owned by root with mode 0700.')
            lock_fd = os.open(state_dir / 'lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(lock_fd, 'a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise SetupError('Another setup operation is running.') from None
                result = machine.apply(args.bundle) if args.command == 'apply' else machine.rollback()
        elif args.command == 'plan':
            result = machine.plan(args.bundle)
        elif args.command == 'verify':
            result = machine.verify()
        else:
            result = machine.inspect()
        print(json.dumps(result, indent=2, sort_keys=True))
        if result.get('blockers') or result.get('passed') is False:
            sys.exit(1)
    except (SetupError, OSError, ValueError, KeyError) as error:
        print('a1708-setup: ' + str(error), file=sys.stderr)
        sys.exit(1)
