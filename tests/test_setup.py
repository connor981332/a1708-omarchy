"""Offline tests exercise decisions and failure recovery, never the host root."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from setup.a1708_setup import BOOT, FILES, MODULES, PACKAGES, STATE, Machine, SetupError, atomic_json, digest


class FakeCommands:
    def __init__(self):
        self.packages = {'dkms': '3.4', 'wget': '1.25', 'patch': '2.8', 'wireplumber': '0.5'}
        self.archives = {}
        self.modules = set()
        self.calls = []
        self.fail_build = False
        self.fail_boot = False
        self.fail_pacman_hook = False

    def __call__(self, args, check=True, **kwargs):
        args = list(map(str, args))
        self.calls.append(args)
        out, code = '', 0
        if args[:2] == ['pacman', '-Q']:
            out = ''.join(f'{n} {v}\n' for n, v in self.packages.items())
        elif args[:2] == ['pacman', '-Qp']:
            info = self.archives.get(args[2])
            out, code = (' '.join(info), 0) if info else ('', 1)
        elif args[:2] == ['pacman', '-U']:
            for path in args[3:]:
                name, version = self.archives.get(path, ('tb-ar-shim-dkms', '0.9-1'))
                self.packages[name] = version
            if self.fail_pacman_hook:
                code = 1
        elif args[:2] == ['pacman', '-R']:
            self.packages.pop(args[3], None)
            if args[3] == 'a1708-audio-dkms':
                self.modules = {m for m in self.modules if m[0] != MODULES[0][0]}
            if args[3] == 'tb-ar-shim-dkms':
                self.modules = {m for m in self.modules if m[0] != MODULES[1][0]}
        elif args[:2] == ['dkms', 'install']:
            if self.fail_build:
                code = 1
            else:
                self.modules.add((args[3], args[5], args[7]))
        elif args[:2] == ['dkms', 'status']:
            entries = self.modules
            if len(args) > 2:
                entries = {m for m in entries if m == (args[3], args[5], args[7])}
            out = ''.join(f'{m}/{v}, {k}, x86_64: installed\n' for m, v, k in sorted(entries))
        elif args[0] == 'modinfo':
            out = '/lib/modules/test/updates/dkms/module.ko.zst\n'
        elif args == ['limine-mkinitcpio']:
            code = int(self.fail_boot)
        else:
            raise AssertionError(args)
        if code and check:
            raise SetupError('injected failure: ' + ' '.join(args))
        return subprocess.CompletedProcess(args, code, out, 'injected failure' if code else '')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'root'
        self.bundle = Path(self.tmp.name) / 'bundle'
        self.bundle.mkdir()
        self.commands = FakeCommands()
        self.machine = Machine(self.root, self.commands)
        self.write('/sys/class/dmi/id/product_name', 'MacBookPro14,1')
        self.write('/etc/os-release', 'ID=omarchy\n')
        self.write('/sys/bus/pci/devices/0000:04:00.0/vendor', '0x8086')
        self.write('/sys/bus/pci/devices/0000:04:00.0/device', '0x1578')
        self.write('/proc/asound/card0/codec#0', 'Vendor Id: 0x10138409\n')
        self.write('/usr/bin/limine-mkinitcpio', '')
        self.write('/usr/lib/modules/test/pkgbase', 'linux')
        self.write('/usr/lib/modules/test/build/Makefile', '')
        self.write('/sys/power/mem_sleep', '[s2idle] deep')
        self.write('/proc/cmdline', 'root=example mem_sleep_default=s2idle')
        items = []
        for name, version in PACKAGES.items():
            path = self.bundle / (name + '.pkg.tar.zst')
            path.write_text(name)
            self.commands.archives[str(path)] = (name, version)
            items.append({'name': name, 'version': version, 'file': path.name, 'sha256': digest(path)})
        self.manifest = {'schema': 1, 'packages': items,
                         'audio_source': {'dkms.conf': hashlib.sha256(b'source').hexdigest()},
                         'configuration': {p: hashlib.sha256(d).hexdigest() for p, (d, _) in FILES.items()}}
        self.save_bundle()

    def write(self, path, text):
        p = self.machine.path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def save_bundle(self):
        atomic_json(self.bundle / 'bundle.json', self.manifest)

    def state(self):
        return json.loads(self.machine.path(STATE + '/transaction.json').read_text())

    def test_plan_is_read_only(self):
        plan = self.machine.plan(self.bundle)
        self.assertEqual(plan['blockers'], [])
        self.assertFalse(self.machine.path(STATE).exists())
        self.assertFalse(any(a[1] in ('-U', '-R', 'install') for a in self.commands.calls if len(a) > 1))

    def test_system_configuration_readable_with_private_journal_umask(self):
        previous = os.umask(0o077)
        try:
            self.machine.apply(self.bundle)
        finally:
            os.umask(previous)
        path = self.machine.path('/etc/wireplumber/wireplumber.conf.d')
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.machine.path(STATE).stat().st_mode & 0o777, 0o700)

    def test_adoption_refuses_incomplete_manual_dkms_installation(self):
        self.write('/usr/src/snd_hda_macbookpro-0.1.resume1/dkms.conf', 'source')
        with self.assertRaisesRegex(SetupError, 'Manual audio must already be installed'):
            self.machine.apply(self.bundle)

    def test_enabled_secure_boot_blocked(self):
        p = self.machine.path('/sys/firmware/efi/efivars/SecureBoot-test')
        p.parent.mkdir(parents=True)
        p.write_bytes(b'\x07\x00\x00\x00\x01')
        with self.assertRaisesRegex(SetupError, 'Secure Boot is enabled'):
            self.machine.apply(self.bundle)

    def test_wrong_model_and_os_block_apply(self):
        self.write('/sys/class/dmi/id/product_name', 'MacBookPro13,1')
        self.write('/etc/os-release', 'ID=arch')
        with self.assertRaisesRegex(SetupError, 'Only MacBookPro14,1'):
            self.machine.apply(self.bundle)
        self.assertFalse(self.machine.path(STATE).exists())

    def test_missing_devices_block(self):
        self.write('/sys/bus/pci/devices/0000:04:00.0/device', '0xffff')
        self.write('/proc/asound/card0/codec#0', 'Vendor Id: 0xdeadbeef')
        blockers = self.machine.plan(self.bundle)['blockers']
        self.assertTrue(any('8086:1578' in b for b in blockers))
        self.assertTrue(any('CS8409' in b for b in blockers))

    def test_codec_detection_does_not_require_registered_alsa_card(self):
        self.machine.path('/proc/asound/card0/codec#0').unlink()
        self.write('/sys/bus/hdaudio/devices/hdaudioC0D0/vendor_id', '0x10138409')
        self.assertEqual(self.machine.plan(self.bundle)['blockers'], [])

    def test_missing_headers_never_silently_skipped(self):
        self.machine.path('/usr/lib/modules/test/build/Makefile').unlink()
        with self.assertRaisesRegex(SetupError, 'Missing matching headers'):
            self.machine.apply(self.bundle)

    def test_all_kernels_built(self):
        self.write('/usr/lib/modules/second/pkgbase', 'linux-lts')
        self.write('/usr/lib/modules/second/build/Makefile', '')
        self.machine.apply(self.bundle)
        self.assertEqual(len(self.commands.modules), 4)

    def test_bundle_tampering_rejected(self):
        (self.bundle / self.manifest['packages'][0]['file']).write_text('tampered')
        with self.assertRaisesRegex(SetupError, 'checksum mismatch'):
            self.machine.apply(self.bundle)

    def test_duplicate_and_traversal_bundle_rejected(self):
        self.manifest['packages'][1] = dict(self.manifest['packages'][0])
        self.save_bundle()
        with self.assertRaisesRegex(SetupError, 'duplicate'):
            self.machine.plan(self.bundle)
        self.manifest['packages'][0]['file'] = '../escape'
        self.save_bundle()
        with self.assertRaisesRegex(SetupError, 'basename'):
            self.machine.plan(self.bundle)

    def test_configuration_conflict_preserved(self):
        path = self.write(BOOT, 'user customization')
        with self.assertRaisesRegex(SetupError, 'Conflicting configuration'):
            self.machine.apply(self.bundle)
        self.assertEqual(path.read_text(), 'user customization')

    def test_symlink_target_and_parent_blocked(self):
        path = self.machine.path(BOOT)
        path.parent.mkdir(parents=True)
        elsewhere = self.write('/elsewhere', 'private')
        path.symlink_to(elsewhere)
        with self.assertRaisesRegex(SetupError, 'Symlink'):
            self.machine.apply(self.bundle)
        path.unlink()
        path.parent.rmdir()
        path.parent.symlink_to(elsewhere.parent)
        self.assertTrue(any('Symlink' in b for b in self.machine.plan(self.bundle)['blockers']))

    def test_conflicting_sleep_default_blocked(self):
        self.write('/etc/limine-entry-tool.d/custom.conf', 'KERNEL_CMDLINE[default]+=" mem_sleep_default=deep"')
        self.assertTrue(any('Conflicting sleep' in b for b in self.machine.plan(self.bundle)['blockers']))

    def test_high_priority_cmdline_replacement_blocks_before_installation(self):
        self.write('/etc/default/limine', 'KERNEL_CMDLINE[default]="root=example rw"')
        with self.assertRaisesRegex(SetupError, 'replaces the default command line'):
            self.machine.apply(self.bundle)
        self.assertFalse(self.machine.path(STATE).exists())

    def test_high_priority_cmdline_append_keeps_dropins(self):
        self.write('/etc/default/limine', 'KERNEL_CMDLINE[default]+=" root=example rw"')
        self.assertEqual(self.machine.plan(self.bundle)['blockers'], [])

    def test_matching_manual_source_adopted_and_preserved(self):
        self.write('/usr/src/snd_hda_macbookpro-0.1.resume1/dkms.conf', 'source')
        self.commands.modules.add(('snd_hda_macbookpro', '0.1.resume1', 'test'))
        plan = self.machine.plan(self.bundle)
        self.assertTrue(plan['adopt_manual_audio'])
        self.machine.apply(self.bundle)
        self.assertNotIn('a1708-audio-dkms', self.commands.packages)
        self.machine.rollback()
        self.assertTrue(self.machine.path('/usr/src/snd_hda_macbookpro-0.1.resume1/dkms.conf').exists())
        self.assertIn(('snd_hda_macbookpro', '0.1.resume1', 'test'), self.commands.modules)

    def test_unknown_manual_source_rejected(self):
        self.write('/usr/src/snd_hda_macbookpro-0.1.resume1/dkms.conf', 'modified')
        with self.assertRaisesRegex(SetupError, 'manual audio source/version differs'):
            self.machine.apply(self.bundle)

    def test_competing_dkms_rejected(self):
        self.commands.modules.add(('snd_hda_macbookpro', '0.1', 'test'))
        self.assertTrue(any('Competing audio' in b for b in self.machine.plan(self.bundle)['blockers']))

    def test_rerun_no_mutations_and_preserves_baseline(self):
        self.machine.apply(self.bundle)
        before = self.state()
        self.commands.calls.clear()
        self.assertEqual(self.machine.apply(self.bundle)['status'], 'unchanged')
        self.assertEqual(self.state(), before)
        self.assertFalse(any(a[:2] == ['pacman', '-U'] or a == ['limine-mkinitcpio'] for a in self.commands.calls))

    def test_build_failure_leaves_boot_unmodified_and_can_rollback(self):
        self.commands.fail_build = True
        with self.assertRaises(SetupError):
            self.machine.apply(self.bundle)
        self.assertFalse(self.machine.path(BOOT).exists())
        self.assertNotEqual(self.state()['status'], 'complete')
        self.machine.rollback()
        self.assertEqual(self.commands.packages, {'dkms': '3.4', 'wget': '1.25', 'patch': '2.8', 'wireplumber': '0.5'})

    def test_pacman_hook_failure_still_records_installed_packages(self):
        self.commands.fail_pacman_hook = True
        with self.assertRaises(SetupError):
            self.machine.apply(self.bundle)
        self.assertEqual(len(self.state()['packages']), 2)
        self.machine.rollback()
        self.assertNotIn('a1708-audio-dkms', self.commands.packages)

    def test_boot_failure_recoverable_and_second_rollback_noop(self):
        self.commands.fail_boot = True
        with self.assertRaises(SetupError):
            self.machine.apply(self.bundle)
        self.assertEqual(self.state()['status'], 'boot-rebuild-pending')
        with self.assertRaisesRegex(SetupError, 'needs rollback'):
            self.machine.apply(self.bundle)
        self.commands.fail_boot = False
        self.assertEqual(self.machine.rollback()['status'], 'rolled-back')
        self.assertFalse(self.machine.path(BOOT).exists())
        self.assertEqual(self.machine.rollback()['status'], 'unchanged')

    def test_user_file_edit_blocks_entire_rollback(self):
        self.machine.apply(self.bundle)
        self.machine.path(BOOT).write_text('user edit')
        self.commands.calls.clear()
        with self.assertRaisesRegex(SetupError, 'File changed'):
            self.machine.rollback()
        self.assertFalse(any(a[1] == '-R' for a in self.commands.calls if len(a) > 1))

    def test_user_permission_edit_blocks_rollback(self):
        self.machine.apply(self.bundle)
        self.machine.path(BOOT).chmod(0o600)
        with self.assertRaisesRegex(SetupError, 'File changed'):
            self.machine.rollback()

    def test_package_drift_blocks_rollback(self):
        self.machine.apply(self.bundle)
        self.commands.packages['a1708-audio-dkms'] = 'future-version'
        with self.assertRaisesRegex(SetupError, 'Package changed'):
            self.machine.rollback()

    def test_preexisting_files_and_packages_retained(self):
        self.commands.packages['tb-ar-shim-dkms'] = PACKAGES['tb-ar-shim-dkms']
        path = self.write(BOOT, FILES[BOOT][0].decode())
        path.chmod(0o644)
        self.machine.apply(self.bundle)
        self.machine.rollback()
        self.assertTrue(path.exists())
        self.assertIn('tb-ar-shim-dkms', self.commands.packages)

    def test_upgrade_requires_exact_rollback_archive(self):
        self.commands.packages['tb-ar-shim-dkms'] = '0.9-1'
        with self.assertRaisesRegex(SetupError, 'Rollback archive missing'):
            self.machine.apply(self.bundle)
        archive = self.write('/var/cache/pacman/pkg/tb-ar-shim-dkms-0.9-1-x86_64.pkg.tar.zst', 'previous')
        self.commands.archives[str(archive)] = ('tb-ar-shim-dkms', '0.9-1')
        self.machine.apply(self.bundle)
        self.machine.rollback()
        self.assertEqual(self.commands.packages['tb-ar-shim-dkms'], '0.9-1')

    def test_verify_never_claims_hardware_pass(self):
        self.assertFalse(self.machine.verify()['passed'])
        self.machine.apply(self.bundle)
        for _, _, module in MODULES:
            self.machine.path('/sys/module/' + module).mkdir(parents=True)
        report = self.machine.verify()
        self.assertTrue(report['passed'])
        self.assertIn('PENDING', report['hardware_tests'])


if __name__ == '__main__':
    unittest.main()
