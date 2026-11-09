#!/usr/bin/env python3
"""DISPOSABLE VM ONLY: real Limine generation, apply/reboot/rollback/reboot.

OS/model/PCI/codec checks use the explicit integration-test double. Limine,
package operations, DKMS, ESP files and the two boot transitions are real.
"""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup.a1708_setup import PACKAGES, Machine, run

REPO = Path(__file__).resolve().parents[1]
PHASE = Path('/var/lib/a1708-vm-boot-test/phase')


def say(text):
    print(text, flush=True)


def reboot():
    run(['systemctl', '--no-block', 'reboot'])


def prepare():
    spec = importlib.util.spec_from_file_location('arch_integration', REPO / 'tests/arch-integration.py')
    integration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(integration)
    journal = Path('/var/lib/a1708-setup/transaction.json')
    if json.loads(journal.read_text())['status'] != 'rolled-back':
        raise RuntimeError('Package integration test must have rolled back first.')
    journal.rename(journal.with_suffix('.package-test.json'))
    # Trust only the public key already used by the recorded Omarchy installation.
    key = REPO / 'tests/fixtures/omarchy.asc'
    info = run(['gpg', '--batch', '--with-colons', '--show-keys', key]).stdout
    fingerprint = '40DFB630FF42BCFFB047046CF0134EE680CAC571'
    if f':{fingerprint}:' not in info:
        raise RuntimeError('Omarchy key fingerprint mismatch')
    run(['pacman-key', '--add', key])
    run(['pacman-key', '--lsign-key', fingerprint])
    with open('/etc/pacman.conf', 'a') as stream:
        stream.write('\n[omarchy]\nServer = https://pkgs.omarchy.org/stable/$arch\n')
    # The cloud image's root cmdline is reused only inside the disposable guest.
    cmdline = ' '.join(x for x in Path('/proc/cmdline').read_text().split()
                       if not x.startswith(('initrd=', 'BOOT_IMAGE=', 'mem_sleep_default=')))
    if 'root=' not in cmdline:
        raise RuntimeError('No root= in guest command line')
    devices = json.loads(run(['lsblk', '--json', '--paths', '-o', 'PATH,PARTTYPE']).stdout)
    def flatten(entries):
        for entry in entries:
            yield entry
            yield from flatten(entry.get('children', []))
    partitions = [d['path'] for d in flatten(devices['blockdevices'])
                  if (d.get('parttype') or '').upper() == 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B']
    if len(partitions) != 1:
        raise RuntimeError('Expected exactly one disposable guest ESP')
    esp = '/efi'
    # Limine's mount validator sees the autofs layer instead of vfat. Normalize
    # this disposable cloud image to a regular EFI mount, as on recorded Omarchy.
    run(['systemctl', 'stop', 'efi.automount', 'efi.mount'], check=False)
    run(['umount', esp], check=False)
    fstab = Path('/etc/fstab')
    lines = []
    for line in fstab.read_text().splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[1] == esp:
            options = [x for x in fields[3].split(',') if x != 'noauto'
                       and not x.startswith(('x-systemd.automount', 'x-systemd.idle-timeout'))]
            fields[3] = ','.join(options) or 'defaults'
            line = '\t'.join(fields)
        lines.append(line)
    fstab.write_text('\n'.join(lines) + '\n')
    run(['systemctl', 'daemon-reload'])
    Path(esp).mkdir(exist_ok=True)
    run(['mount', '-t', 'vfat', partitions[0], esp])
    filesystem = run(['findmnt', '-n', '-o', 'FSTYPE', esp]).stdout.strip()
    if filesystem != 'vfat':
        raise RuntimeError('Guest ESP is not a regular vfat mount: ' + filesystem)
    say('A1708_VM_ESP ' + esp + ' ' + filesystem)
    Path('/etc/default/limine').write_text(
        f'ESP_PATH={shlex.quote(esp)}\nKERNEL_CMDLINE[default]+={shlex.quote(cmdline)}\n'
        'ENABLE_UKI=yes\nMKINITCPIO_FALLBACK=no\nENABLE_LIMINE_FALLBACK=yes\n'
        'BOOT_ORDER="linux, *"\n')
    run(['pacman', '-Syu', '--noconfirm', '--needed', 'limine', 'limine-mkinitcpio-hook', 'efibootmgr'])
    run(['limine-install', '--fallback'])
    os.umask(0o077)
    machine = integration.TestMachine()
    if machine.plan(REPO / 'local/setup-bundle')['blockers']:
        raise RuntimeError('Unexpected real boot-tool preflight blockers')
    machine.apply(REPO / 'local/setup-bundle')
    images = list(Path(esp).glob('EFI/Linux/*.efi'))
    if not images:
        raise RuntimeError('No generated UKIs')
    for image in images:
        section = Path('/run/a1708-vm-cmdline')
        run(['objcopy', '--dump-section', f'.cmdline={section}', image])
        if 'mem_sleep_default=s2idle' not in section.read_text().replace('\x00', '').split():
            raise RuntimeError('Generated UKI lacks s2idle')
    PHASE.parent.mkdir(mode=0o700, parents=True)
    PHASE.write_text('applied')
    Path('/etc/systemd/system/a1708-vm-accept.service').write_text(
        '[Unit]\nDescription=Disposable A1708 Limine boot acceptance\nAfter=local-fs.target\n'
        '[Service]\nType=oneshot\nEnvironment=A1708_DISPOSABLE_TEST=1\n'
        'ExecStart=/usr/bin/python3 /work/repo/tests/limine-vm.py advance\n'
        'StandardOutput=tty\nStandardError=tty\nTTYPath=/dev/console\n'
        'TimeoutStartSec=900\n[Install]\nWantedBy=multi-user.target\n')
    run(['systemctl', 'enable', 'a1708-vm-accept.service'])
    say('A1708_VM_REBOOT_AFTER_APPLY')


def advance():
    stage = PHASE.read_text()
    token = 'mem_sleep_default=s2idle' in Path('/proc/cmdline').read_text().split()
    if stage == 'applied':
        if not token:
            raise RuntimeError('Applied s2idle absent after real reboot')
        Machine().rollback()
        PHASE.write_text('rolled-back')
        say('A1708_VM_REBOOT_AFTER_ROLLBACK')
        reboot()
    elif stage == 'rolled-back':
        if token or any(p in Machine().packages() for p in PACKAGES):
            raise RuntimeError('Rollback not reflected after real reboot')
        PHASE.write_text('passed')
        say('A1708_VM_LIMINE_BOOT_TEST_PASS')
        say('A1708_VM_FINISHED_OK')
        run(['systemctl', '--no-block', 'poweroff'])
    else:
        raise RuntimeError('Unexpected VM test phase: ' + stage)


def main():
    if os.geteuid() != 0 or os.environ.get('A1708_DISPOSABLE_TEST') != '1':
        raise SystemExit('Disposable VM test only')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() == 'MacBookPro14,1':
        raise SystemExit('Refusing physical Mac')
    try:
        if sys.argv[1] == 'prepare':
            prepare()
        elif sys.argv[1] == 'advance':
            advance()
        else:
            raise RuntimeError('Unknown phase')
    except Exception as error:
        say('A1708_VM_FINISHED_FAILED: ' + str(error))
        if sys.argv[1] == 'advance':
            run(['systemctl', '--no-block', 'poweroff'])
        raise


if __name__ == '__main__':
    main()
