# Setup validation and future-session handoff

This document accompanies the experimental unified installer. Keep software
results separate from physical hardware acceptance. It is a solo implementation;
no agent delegation was used and no working-machine installation was performed.

## Recorded environment and source

Session date: November 8, 2026 America/Denver (some test logs use November 9 UTC).
The observed machine is a 2017 MacBookPro14,1, Omarchy 4.5.0 / package 4.5.0-3,
with `linux` 7.2.11.arch1-1 and `linux-omarchy` 7.2.15-1, matching headers,
DKMS 3.4.4-1, and WirePlumber 0.5.18-1. The running kernel is 7.2.15-1-omarchy.
Relevant hardware: Intel Alpine Ridge bridge `8086:1578`, Intel HDA controller
`8086:9d71`, CS8409 codec `0x10138409`, and SPI keyboard backlight. The amplifier
initialization, Apple EFI deep-sleep behavior, and SPI LED behavior motivate the
model-specific selection; other A1708 revisions have not been verified.

The missing capability was a unified, repeatable fresh-machine installation of
all preserved fixes. The implementation does not change the audio or Thunderbolt
module algorithms or backlight-hook behavior. Audio is still upstream
`89b22ff90b86468b186706861dd18663562defa7` plus the tracked resume patch;
Thunderbolt is still `155ffe3a4a963bc8d84df72fa53f14eb16ea9a60`.

## Completed automated checks

- **26 offline decision/transaction tests** cover incompatible hardware/OS, missing
  devices and headers, enabled Secure Boot, source adoption, competing DKMS
  versions, configuration/symlink conflicts, bundle corruption and path
  traversal, multiple kernels, package replacement with rollback archives,
  package/file drift, private journal versus readable system-config permissions,
  reruns, failed builds/package hooks/boot rebuilding, and rollback retries.
- Both Arch packages built on the working host **without installation** and in
  a separate, initialized Arch bootstrap environment without host source mounts.
  Source checksums and zero-fuzz patch application passed.
- Real package installation, DKMS builds and module installation passed in the
  rootless Arch environment for **7.2.14-arch1-1** and **6.18.60-1-lts**, using
  GCC 16.2.1+r23+gd564253eb6c8-1, DKMS 3.4.4-1 and Python 3.14.9-1.
  `modinfo` resolved both drivers through `updates/` with matching vermagic.
  A second apply was unchanged; rollback removed the newly added packages and
  managed files; a second rollback was unchanged. Hardware probes and
  `limine-mkinitcpio` were explicit test doubles in this test.
- Read-only planning on the working Mac found no blockers, adopted the matching
  manual audio source, retained the Thunderbolt package and backlight hook, and
  proposed the owned boot drop-in and system-wide WirePlumber rule. Nothing was
  applied. Software verification reported those two not-yet-installed managed
  paths; the other existing software checks passed.

CI in `.github/workflows/setup.yml` repeats offline checks and real package/DKMS
lifecycle tests against Arch linux and linux-lts, on PRs and weekly. A successful
local run is not a claim that remote CI has run or passed; inspect the PR checks.

## Reproducing isolated tests

Host sudo and Docker access were unavailable; `/dev/kvm` was absent. Rootless
user namespaces with subordinate UID/GID mappings worked. No host packages,
drivers, boot entries, user configuration, or power state were changed.

1. Download an official Arch bootstrap archive and signature from
   `https://geo.mirror.pkgbuild.com/iso/latest/`. Verify with the installed Arch
   keyring (dearmor an ASCII keyring before passing it to `gpgv`). This session's
   bootstrap signature verified against Pierre Schmitz's key
   `3E80CA1A8B89F69CBA57D98A76A5EF9054449A5C`.
2. Extract into an ignored `local/` directory inside a user namespace. Configure
   the disposable root's mirrorlist, initialize/populate its pacman keyring,
   and install `base-devel python git dkms wget patch wireplumber linux
   linux-headers linux-lts linux-lts-headers`. Updating this root is intentional;
   never substitute `/` for the disposable root.
3. Use `tests/with-arch-root.sh ABSOLUTE_ROOT command...` to enter it. The helper
   mounts its own proc and individual harmless device nodes. It passes no host
   sysfs, block devices, ESP, or working-machine source tree. It requires working
   unprivileged user namespaces plus subordinate UID/GID mappings.
4. Copy a sanitized repository snapshot into `/work/repo` inside that root,
   excluding `.git`, `local`, and Python caches. Add an ordinary build user,
   give that user ownership of the snapshot, and run `./a1708-setup build` there.
5. As namespace root, from `/work/repo`, run
   `A1708_DISPOSABLE_TEST=1 python3 tests/arch-integration.py local/setup-bundle`.
   This is intentionally destructive inside that disposable installation. It
   refuses the actual Mac model, installed fix packages, an existing setup
   journal, or installed Limine tooling. Use a new test root for a fresh run.

For a VM, install `qemu-system-x86 qemu-img edk2-ovmf xorriso` in the isolated
root. Obtain the official Arch `cloudimg.qcow2` and published checksum from
`https://geo.mirror.pkgbuild.com/images/latest/`. In this session its SHA-256
matched the HTTPS-published checksum; its signing key was not in either local
Arch keyring, so independent signature verification was **not** completed.

Run `tests/vm-smoke.sh CLOUDIMG BUNDLE NEW_WORK_DIRECTORY OVMF_DIRECTORY`.
It uses software CPU emulation, a new overlay disk, UEFI firmware variables,
a cloud-init seed containing only the test payload, and outbound user networking.
It passes no host credentials or host directory mounts. Serial output and disk
artifacts stay in the ignored work directory. Each boot pass has a 30-minute timeout;
PASS requires the guest's success marker, not merely QEMU exiting successfully.
The cloud-init seed stops network-time waiting (user-mode networking may not
support NTP) and uses a virtual RNG to avoid entropy starvation.
The guest first exercises a real boot and package lifecycle with a boot-image
test double. It then runs `tests/limine-vm.py` against real Limine tooling,
using the public Omarchy repository key in `tests/fixtures/omarchy.asc`
(fingerprint `40DFB630FF42BCFFB047046CF0134EE680CAC571`, copied from the
installed `omarchy-keyring` 20251027-1; no private key material). The second
stage generates UKIs, checks their embedded s2idle argument, reboots, verifies
the running argument, rolls back, and reboots again to verify removal. The
harness allows three boot passes, with a 30-minute timeout per pass. Hardware
probes and the OS ID remain test doubles; this is a minimal Arch VM with the
Omarchy boot tooling, not a full Omarchy desktop installation.

## VM result status

The UEFI VM harness and real Limine acceptance test are implemented. Final
execution results are recorded below when available; implementation alone is
not a passing boot test. Early attempts reached UEFI/Linux boot but were stopped
while guest startup waited for time synchronization. The final seed explicitly
stops that wait and supplies virtual entropy.

## What the owner needs to do

No action is needed to preserve or review this implementation. For hardware
acceptance, at a convenient time:

1. Supply an external SSD whose contents may be erased, identify it explicitly,
   and prepare recovery media. Do not allow any agent to infer a disk to erase.
2. Have a future session install fresh Omarchy onto that SSD with its own EFI
   partition and bootloader, leaving the internal installation available as the
   working reference. You must approve the concrete disk operation and select
   the external installation in the Mac's boot picker.
3. Run setup on that clean installation, reboot, and complete software checks
   before attempting suspend. Because USB-C is being repaired, the external
   system disk itself may be affected by a Thunderbolt failure.
4. Connect/position Yeti X and Sound Blaster Play! 3 for the existing acoustic
   tests, confirm audio quality, close/open the lid for repeated sleep checks,
   and confirm actual backlight blanking/restoration and peripheral behavior.
   Record battery drain over a deliberate sleep interval. Software counters
   alone do not establish these results.

## What the next agent needs to do

Read `AGENTS.md`, `README.md`, `docs/setup.md`, this file, and the PR discussion
before acting. Keep the existing branch/PR; do not create a duplicate or merge.

- Inspect current Git status, PR checks, source pins and target kernel versions.
  Read local test artifacts only if needed; do not publish raw logs or private
  notes. Rerun offline tests after changes and real integration when behavior
  changes. Preserve the user's working installation.
- Finish **actual Omarchy/Limine boot-image integration** in a disposable full
  Omarchy VM if feasible: apply, inspect generated command lines/images, reboot,
  check the active command line, rollback, and reboot again. An Arch cloud VM
  using the test double does not satisfy this check. Add an explicit test fixture
  around hardware probing, rather than a production `--force` hardware bypass.
- Perform fresh Omarchy installation and acceptance on MacBookPro14,1 when the
  owner provides a test disk and is available for physical steps. Do not uninstall
  working fixes from the internal installation to manufacture a clean test.
- Validate a real rolling kernel upgrade and recovery with the installer-managed
  packages; current two-kernel compilation does not prove all future updates.
- Consider hardening upstream audio's kernel-source retrieval (verified exact
  tarballs and no fallback) as a separate packaging change with provenance and
  tests. The present package intentionally retains upstream behavior.
- Consider multi-generation transaction history and automatic prerequisite
  provisioning after the first clean-machine validation. Current apply requires
  prerequisites and keeps one rollback baseline; it refuses changed follow-up
  transactions until that baseline is rolled back. Do not describe this as a
  complete unattended upgrade manager.
- Record fresh results with date, OS/kernel/package versions and tests performed.
  Keep the PR draft until the boot and hardware checks pass; report remaining
  gaps explicitly. Follow the authorized commit/push/PR workflow for fixes.
