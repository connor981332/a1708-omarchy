#!/usr/bin/env python3
"""Destructive package integration test: DISPOSABLE ARCH ENVIRONMENTS ONLY.

Uses real pacman, DKMS, modules and config files. The model/PCI/codec/OS probes
and boot-image command are test doubles; this cannot validate Omarchy booting.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup.a1708_setup import BOOT, MODULES, PACKAGES, Machine, SetupError, run


class TestMachine(Machine):
    def read(self, name):
        if name == '/sys/class/dmi/id/product_name':
            return 'MacBookPro14,1'
        if name == '/etc/os-release':
            return 'ID=omarchy'
        return super().read(name)

    def plan(self, directory):
        plan = super().plan(directory)
        # Narrow, explicit test substitutions. All other real preflight checks remain.
        simulated = {'Expected Alpine Ridge PCI bridge 8086:1578 is absent.',
                     'Expected CS8409 codec ID 0x10138409 is absent.'}
        plan['blockers'] = [b for b in plan['blockers'] if b not in simulated]
        return plan


def main():
    if os.geteuid() != 0 or os.environ.get('A1708_DISPOSABLE_TEST') != '1':
        raise SystemExit('Run as root with A1708_DISPOSABLE_TEST=1 in a disposable environment only.')
    # Refuse the real model even if the environment variable was set by mistake.
    real_model = Path('/sys/class/dmi/id/product_name')
    if real_model.exists() and real_model.read_text().strip() == 'MacBookPro14,1':
        raise SystemExit('Refusing integration tests on the physical Mac.')
    bundle = Path(sys.argv[1]).resolve()
    if Path('/var/lib/a1708-setup/transaction.json').exists():
        raise SystemExit('Test requires an unused setup state directory.')
    os.umask(0o077)  # Match the privileged CLI's private state-directory policy.
    machine = TestMachine()
    initial = machine.packages()
    if any(p in initial for p in PACKAGES):
        raise SystemExit('Test requires no existing fix packages.')
    # Isolated test-only executable, never installed on the working Mac.
    boot = Path('/usr/bin/limine-mkinitcpio')
    if boot.exists():
        raise SystemExit('Refusing to replace installed boot tooling.')
    Path('/run/a1708-test-rebuilds').unlink(missing_ok=True)
    boot.write_text('#!/bin/sh\necho test-boot-rebuild >> /run/a1708-test-rebuilds\n')
    boot.chmod(0o755)
    try:
        assert not machine.plan(bundle)['blockers']
        assert machine.apply(bundle)['status'] == 'complete'
        assert Path('/etc/wireplumber/wireplumber.conf.d').stat().st_mode & 0o777 == 0o755
        for kernel in machine.kernels():
            for module, version, modname in MODULES:
                assert machine.installed(module, version, kernel['version'])
                filename = run(['modinfo', '-k', kernel['version'], '-F', 'filename', modname]).stdout.strip()
                assert '/updates/' in filename, filename
                vermagic = run(['modinfo', '-k', kernel['version'], '-F', 'vermagic', modname]).stdout.strip()
                assert vermagic.startswith(kernel['version'] + ' '), vermagic
        assert machine.apply(bundle)['status'] == 'unchanged'
        assert Path('/run/a1708-test-rebuilds').read_text().count('test-boot-rebuild') == 1
        assert not machine.verify()['passed']  # no real hardware or active sleep configuration
        assert machine.rollback()['status'] == 'rolled-back'
        assert not machine.path(BOOT).exists()
        assert not any(p in machine.packages() for p in PACKAGES)
        assert machine.rollback()['status'] == 'unchanged'
        print(json.dumps({'result': 'PASS', 'kernels': machine.kernels(),
                          'scope': 'real package install, DKMS build, module metadata, rerun, rollback',
                          'simulated': 'model, PCI, codec, Omarchy ID, boot-image rebuild'}, indent=2))
    finally:
        boot.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
