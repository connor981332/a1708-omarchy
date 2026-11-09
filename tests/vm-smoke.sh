#!/bin/bash
# Requires qemu-system-x86_64, qemu-img, xorriso, Python and OVMF.
# Use a downloaded official Arch cloudimg. Checksums/signatures must be checked
# by the caller before invoking this script. It creates only new files in WORK.
set -euo pipefail
if (( $# != 4 )); then
  echo "Usage: $0 CLOUDIMG BUNDLE WORK OVMF_DIRECTORY" >&2
  exit 2
fi
image=$(realpath "$1")
bundle=$(realpath "$2")
work=$(realpath -m "$3")
firmware=$(realpath "$4")
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ ! -e $work ]] || { echo 'WORK must not exist' >&2; exit 2; }
mkdir -p "$work/seed"
python3 - "$repo" "$bundle" "$work/seed/payload.tar.gz" <<'PY'
import json
from pathlib import Path
import sys
import tarfile
repo, bundle, target = map(Path, sys.argv[1:])
with tarfile.open(target, 'w:gz') as archive:
    for entry in ['a1708-setup', 'setup', 'tests', 'audio/51-cs8409-no-suspend.conf',
                  'keyboard-backlight/macbook-keyboard-backlight']:
        archive.add(repo / entry, arcname=entry, filter=lambda x: None if '__pycache__' in x.name else x)
    archive.add(bundle / 'bundle.json', arcname='local/setup-bundle/bundle.json')
    for package in json.loads((bundle / 'bundle.json').read_text())['packages']:
        archive.add(bundle / package['file'], arcname='local/setup-bundle/' + package['file'])
PY
cat > "$work/seed/meta-data" <<'EOF'
instance-id: a1708-disposable-package-test
local-hostname: a1708-test
EOF
cat > "$work/seed/user-data" <<'EOF'
#cloud-config
locale: C.UTF-8
bootcmd:
  - [systemctl, stop, systemd-time-wait-sync.service]
runcmd:
  - |
    exec > /dev/console 2>&1
    mkdir -p /mnt/seed /work/repo
    mount -o ro /dev/sr0 /mnt/seed
    tar -xzf /mnt/seed/payload.tar.gz -C /work/repo
    if A1708_DISPOSABLE_TEST=1 bash /work/repo/tests/vm-guest.sh; then
      systemctl reboot
      exit 0
    else
      echo A1708_VM_FINISHED_FAILED
    fi
    systemctl poweroff
EOF
xorriso -as mkisofs -quiet -volid cidata -joliet -rock -output "$work/seed.iso" "$work/seed"
qemu-img create -f qcow2 -F qcow2 -b "$image" "$work/disk.qcow2" 16G
cp "$firmware/OVMF_VARS.4m.fd" "$work/vars.fd"
# No host directories, USB devices, credentials or privileged acceleration are passed through.
for ((pass = 1; pass <= 3; pass++)); do
timeout 1800 qemu-system-x86_64 \
  -machine q35 -accel tcg,thread=multi -cpu max -smp 2 -m 3072 \
  -drive if=pflash,format=raw,readonly=on,file="$firmware/OVMF_CODE.4m.fd" \
  -drive if=pflash,format=raw,file="$work/vars.fd" \
  -drive if=virtio,format=qcow2,file="$work/disk.qcow2" \
  -drive media=cdrom,format=raw,readonly=on,file="$work/seed.iso" \
  -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0 \
  -nic user,model=virtio-net-pci -display none -monitor none -serial stdio -no-reboot \
  >> "$work/serial.log" 2>&1
if grep -q "^A1708_VM_FINISHED_OK" "$work/serial.log"; then break; fi
if grep -q "^A1708_VM_FINISHED_FAILED" "$work/serial.log"; then break; fi
done
grep -q '^A1708_VM_FINISHED_OK' "$work/serial.log" || {
  tail -80 "$work/serial.log" >&2
  exit 1
}
echo "PASS: UEFI Arch VM package lifecycle and real Limine apply/rollback reboots; see $work/serial.log"
