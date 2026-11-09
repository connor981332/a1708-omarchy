#!/bin/bash
# Invoked by cloud-init only in the disposable VM created by vm-smoke.sh.
set -euo pipefail
[[ ${A1708_DISPOSABLE_TEST:-} == 1 ]] || exit 2
[[ $(cat /sys/class/dmi/id/product_name) != MacBookPro14,1 ]] || exit 2
cd /work/repo
pacman -Syu --noconfirm --needed base-devel python dkms wget patch linux linux-headers wireplumber
python3 -m unittest discover -s tests -v
A1708_DISPOSABLE_TEST=1 python3 tests/arch-integration.py local/setup-bundle
printf '\nA1708_VM_PACKAGE_TEST_PASS\n'
python3 tests/limine-vm.py prepare
