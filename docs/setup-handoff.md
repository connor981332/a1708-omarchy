# Setup validation and future-session handoff

This document accompanies the experimental unified installer. Keep software
results separate from physical hardware acceptance. It is a solo implementation;
no agent delegation was used and no working-machine installation was performed.

Implementation branch: `feat/unified-setup`.
[Draft PR #2](https://github.com/connor981332/a1708-omarchy/pull/2) targets `master`.
Update that PR; do not open a duplicate or merge without separate instruction.

## Recorded environment and source

Session dates: November 8–9, 2026 America/Denver (test logs also use UTC).
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

- **29 offline decision/transaction tests** cover incompatible hardware/OS, missing
  devices and headers, enabled Secure Boot, source adoption, competing DKMS
  versions, configuration/symlink conflicts, Limine command-line precedence,
  codec detection before ALSA card registration, bundle corruption/path traversal, multiple kernels, package replacement with rollback archives,
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
- Post-install kernel maintenance passed separately: setup initially targeted
  only `7.2.14-arch1-1`, then pacman installed `linux-lts` and matching headers
  (`6.18.60-1-lts`). Its hooks automatically built/installed both selected
  drivers for the added kernel; the test did not call the installer's repair
  helper. `modinfo` paths/vermagic matched. Rollback removed the fix packages
  and their DKMS registrations for both kernels while retaining the added kernel.
  Evidence: `local/setup-cache/kernel-addition.log` (ignored). CI now repeats this
  kernel-addition path with `--exercise-kernel-addition`.
- Read-only planning on the working Mac found no blockers, adopted the matching
  manual audio source, retained the Thunderbolt package and backlight hook, and
  proposed the owned boot drop-in and system-wide WirePlumber rule. Nothing was
  applied. Software verification reported those two not-yet-installed managed
  paths; the other existing software checks passed.

CI in `.github/workflows/setup.yml` repeats offline checks and real package/DKMS
lifecycle tests against Arch linux and linux-lts, including automatic builds
when LTS is added after setup, on PRs and weekly.
[GitHub run 42581654102](https://github.com/connor981332/a1708-omarchy/actions/runs/42581654102)
passed both jobs for implementation commit `4a6c0f5` (29 offline tests and real
Arch package/DKMS lifecycle). Inspect the latest PR checks after later commits.

## Reproducing isolated tests

Host sudo and Docker access were unavailable. The sandbox device view hid
`/dev/kvm`; a later direct host check found KVM available and accessible without
administrator authentication. Rootless user namespaces with subordinate UID/GID
mappings worked; the final VM run explicitly binds only `/dev/kvm` into the
isolated root with `A1708_TEST_KVM=1`. No host packages, drivers, boot entries, user configuration, or power state were changed.

1. Download an official Arch bootstrap archive and signature from
   `https://geo.mirror.pkgbuild.com/iso/latest/`. Verify with the installed Arch
   keyring (dearmor an ASCII keyring before passing it to `gpgv`). This session's
   bootstrap signature verified against Pierre Schmitz's key
   `3E80CA1A8B89F69CBA57D98A76A5EF9054449A5C`.
   Recorded November 1 bootstrap SHA-256:
   `655bc99849b80859173fa39338a6c910185e952173f6a1a61526cfa34ab8339c`.
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
   To test kernel maintenance, start with only `linux`/`linux-headers` installed
   and add `--exercise-kernel-addition`; the test installs LTS/headers after
   setup and requires the package hooks alone to build both drivers.

For a VM, install `qemu-system-x86 qemu-img edk2-ovmf xorriso` in the isolated
root. Obtain the official Arch `cloudimg.qcow2` and published checksum from
`https://geo.mirror.pkgbuild.com/images/latest/`. In this session its SHA-256
matched the HTTPS-published checksum. The downloaded image was
`Arch-Linux-x86_64-cloudimg-20261101.620452.qcow2`, SHA-256
`794eb4889b39e1f0ed7d5ae998b2a1ed2137db8cf8c3476cf2962c7437ecb003`.
Its signing key was not in either local Arch keyring, so independent signature verification was **not** completed.

Run `tests/vm-smoke.sh CLOUDIMG BUNDLE NEW_WORK_DIRECTORY OVMF_DIRECTORY`.
It uses KVM when accessible (otherwise software CPU emulation), a new overlay
disk, UEFI firmware variables, a cloud-init seed containing only the test payload, and outbound user networking.
It passes no host credentials or host directory mounts. Serial output and disk
artifacts stay in the ignored work directory. Each boot pass has a 30-minute
timeout; PASS requires the guest's success marker, not merely QEMU exiting successfully.
The cloud-init seed stops network-time waiting (user-mode networking may not
support NTP) and uses a virtual RNG to avoid entropy starvation.
Each pass also exposes a local Unix monitor socket for headless diagnostics.
The guest first exercises a real boot and package lifecycle with a boot-image
test double. It then runs `tests/limine-vm.py` against real Limine tooling,
using the public Omarchy repository key in `tests/fixtures/omarchy.asc`
(fingerprint `40DFB630FF42BCFFB047046CF0134EE680CAC571`, copied from the
installed `omarchy-keyring` 20251027-1; no private key material). The second
stage makes the guest EFI mount persistent (masking GPT-generated automount),
generates UKIs, checks their embedded s2idle argument without modifying the
images or invalidating their hashes, reboots, verifies
the running argument, rolls back, and reboots again to verify removal. The
harness allows three boot passes, with a 30-minute timeout per pass. Hardware
probes and the OS ID remain test doubles; this is a minimal Arch VM with the
Omarchy boot tooling, not a full Omarchy desktop installation.

## Real UEFI boot result: PASS

The final unattended three-boot run completed successfully on November 9:

1. Fresh Arch cloud image boot; real package installation, DKMS compilation,
   matching module metadata, unchanged rerun and package rollback passed.
2. Real Limine setup generated UKIs containing `mem_sleep_default=s2idle`.
   Inspection preserved image bytes and their recorded hashes. The guest
   rebooted through Limine and verified the argument in `/proc/cmdline`.
3. Installer rollback removed the added packages/configuration and regenerated
   real boot images. A second reboot verified that the argument and both added
   packages were absent. The guest emitted `A1708_VM_LIMINE_BOOT_TEST_PASS` and
   `A1708_VM_FINISHED_OK`; the host harness exited zero and reported PASS.

Observed VM versions: Limine `12.9.6-1`, `limine-mkinitcpio-hook` `1.40.0-2`,
mkinitcpio `42.2-1`, DKMS `3.4.4-1`, Linux/headers `7.2.14.arch1-1`.
All 29 offline tests also passed inside the VM. Host-side syntax/compilation
checks and ShellCheck on the shell harnesses passed.

The real boot check uses a minimal Arch VM plus Omarchy boot tooling. Hardware
probes and OS ID use explicit test doubles; the boot-image command, package
operations, EFI files and reboot transitions are real. It does not establish
working audio, Thunderbolt, backlight or sleep on the physical Mac, and it does
not constitute a full fresh Omarchy desktop installation.

VM fixture adaptations use Limine's double-quoted command-line format, maintain
a regular EFI mount across reboots, preserve image hashes during inspection,
and tolerate terminal/login prefixes on result markers. The installer does not
rewrite the host's EFI mount units or bootloader menu.

Local evidence is retained under `local/setup-cache/vm-final.log` and
`local/test-root/root.x86_64/work/vm-final/serial.log`. The final VM overlay,
base image, build bundle and isolated tools remain available for follow-up.
Retired failed VM images were removed; their logs remain under
`local/setup-cache/retired-vm-logs/`.
These ignored artifacts are not part of the PR; the reproducible sources,
procedures and sanitized results are tracked here. Task-owned test paths are
`local/setup-cache/`, `local/setup-bundle/` and `local/test-root/`. Never remove
the whole `local/` directory: its existing archive/builds/machine notes predate
this implementation and are unrelated user data.

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
- The real Limine apply/reboot/rollback/reboot cycle already passed as recorded
  above. A full fresh Omarchy installation remains untested; the mandatory next
  acceptance gate is the physical Mac installation below. A full Omarchy VM is
  an optional additional check if investigating OS-specific integration. Keep
  hardware test doubles in fixtures, never add a production `--force` bypass.
- Perform fresh Omarchy installation and acceptance on MacBookPro14,1 when the
  owner provides a test disk and is available for physical steps. Do not uninstall
  working fixes from the internal installation to manufacture a clean test.
- Kernel addition after setup and automatic DKMS builds already passed. Continue
  checking new kernel/header releases with CI; a future version-replacement
  upgrade and physical post-upgrade behavior still need their own results.
  Two-kernel compilation and kernel addition do not prove every future update.
- Consider hardening upstream audio's kernel-source retrieval (verified exact
  tarballs and no fallback) as a separate packaging change with provenance and
  tests. The present package intentionally retains upstream behavior.
- Consider multi-generation transaction history and automatic prerequisite
  provisioning after the first clean-machine validation. Current apply requires
  prerequisites and keeps one rollback baseline; it refuses changed follow-up
  transactions until that baseline is rolled back. Do not describe this as a
  complete unattended upgrade manager.
- Record fresh results with date, OS/kernel/package versions and tests performed.
  Keep the PR draft until fresh-Omarchy and hardware acceptance pass; report remaining
  gaps explicitly. Follow the authorized commit/push/PR workflow for fixes.
