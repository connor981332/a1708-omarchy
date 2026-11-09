# Unified setup (experimental)

`a1708-setup` installs the selected fixes for **2017 MacBookPro14,1 on
x86_64 Omarchy with Limine**. It does not install Omarchy, partition disks,
change firmware, or claim support for the 2016 A1708 / MacBookPro13,1.
Keep the PR draft until the hardware acceptance checks in
[the handoff](setup-handoff.md) pass.

## Installation

Start with an installed, updated Omarchy system and a clone of this repository.
Python 3 is required. Install build prerequisites (`base-devel`, `git`, `dkms`,
`wget`, `patch`) and the headers matching **every installed kernel** using your
normal Omarchy maintenance process. WirePlumber must already be installed.
Do not synchronize package databases without completing a full system upgrade.
If updating kernels, retain a working boot option and reboot into the updated
kernel before hardware acceptance testing.

For the recorded `linux` and `linux-omarchy` combination, the header packages
are `linux-headers` and `linux-omarchy-headers`. Other kernel packages need their
corresponding headers. The planner reports missing prerequisites; it does not
perform an unrelated system upgrade or silently skip kernels without headers.

From the project root, as your ordinary desktop user:

```sh
./a1708-setup status
./a1708-setup build
./a1708-setup plan
sudo ./a1708-setup apply
```

`build` uses `makepkg` without installing host packages. It stages self-contained
recipes, checks upstream archives and the audio patch against SHA-256 checksums,
applies the patch without fuzz, and writes packages plus `bundle.json` to
`local/setup-bundle/`. The source archives are pinned to the revisions in
[third-party notices](../THIRD-PARTY.md). Audio's upstream DKMS pre-build script
also downloads kernel.org source at module-build time; internet is required.
That upstream download uses HTTPS but has no independent checksum/signature
verification and can fall back to the base kernel release. This remaining
upstream limitation is not hidden by the bundle checksum.

Custom output directories are supported with `build --output DIR` followed by
`plan --bundle DIR` and `apply --bundle DIR`.

Only use bundles built from reviewed source. The bundle checksums detect
corruption/mismatches, not malicious replacement of a bundle and its manifest.
Packages contain privileged build scripts and are not signed by this project.
Sources and configuration are reproducible; package archives are not promised
to be byte-identical across toolchain versions and build dates.

`plan`, `status`, and `verify` are read-only. JSON output contains relevant
package versions and device class/model information, not serial numbers or raw
journals. Exit status is nonzero for blocked plans or failed verification.

## What apply does

1. Validates the bundle, model, Omarchy ID, Alpine Ridge bridge `8086:1578`,
   CS8409 codec `0x10138409`, Limine tooling, prerequisites, and kernel headers.
   Secure Boot with unsigned modules is blocked.
2. Installs `a1708-audio-dkms` and `tb-ar-shim-dkms` where needed. Existing exact
   package versions are retained. A replacement requires the exact previous
   package archive in `/var/cache/pacman/pkg`, copied to the root-only state
   directory before installation.
3. Verifies both DKMS modules are installed for every kernel. A successful
   `pacman` return alone is insufficient because post-transaction hooks can fail.
4. Installs the system WirePlumber rule, the backlight sleep hook, and a dedicated
   Limine drop-in for `mem_sleep_default=s2idle`. Unknown file contents, symlinks
   at managed paths, and conflicting sleep defaults in other Limine drop-ins
   block installation rather than overwrite user configuration.
5. Runs `limine-mkinitcpio` after configuration is in place. Package hooks may
   also rebuild initramfs earlier; this final rebuild includes the boot setting.

The WirePlumber rule is system-wide for this model. An existing identical
per-user rule can remain. Inspect per-user WirePlumber overrides if behavior
still differs; this tool does not edit users' home directories or start their
session services from root.

No automatic reboot, suspend, module unload/reload, or audio-service restart
occurs. Reboot at a convenient time and log into the desktop, then run:

```sh
./a1708-setup verify
```

A passing software check is **not** a passing acoustic or sleep test. Follow
[hardware verification](verification.md) afterward.

## Existing manually configured machines

The known audio source at `/usr/src/snd_hda_macbookpro-0.1.resume1` may be a
symlink to `/usr/local/src/snd_hda_macbookpro-resume`. The installer compares all
packaged source-file hashes and requires the selected DKMS version to be
installed for every kernel before adopting it. It does not move the source,
replace its symlink, or take ownership of the manual driver. Unknown sources
or competing DKMS versions stop the operation with a diagnostic.

Matching existing configuration and matching packages are retained, and rollback
does not remove them. This includes the earlier `macbook-s2idle.conf`; the new
owned drop-in can coexist with its identical setting. Removing the owned
setting later does not remove the earlier workaround.

## Transactions, reruns, and recovery

State lives under `/var/lib/a1708-setup/` (root, mode 0700). The journal records
intent before package and file changes. Concurrent setup operations are locked.
On failure, the command returns nonzero, records the error, and leaves the
journal for deliberate recovery. It does not attempt an unattended reboot.

A completed installation can be rerun with the same bundle and unchanged
kernel/DKMS/configuration state without reinstalling packages or rebuilding boot
images. A failed/interrupted transaction must be rolled back before another
changed apply. One rollback baseline is retained at a time: roll it back before
applying a different release. Future multi-generation upgrades are not yet
implemented. Normal pacman kernel updates use the DKMS `AUTOINSTALL` mechanism;
repeat verification afterward.

To undo the setup transaction:

```sh
sudo ./a1708-setup rollback
```

Rollback restores previous package archives or removes only packages added by
this transaction, restores previous file contents/modes or removes newly created
files, and regenerates boot images. It leaves prerequisite packages and adopted
manual fixes in place. User edits to managed file contents or modes, unexpected package
versions, and missing/modified rollback archives block rollback before it makes
changes. Resolve that drift deliberately; do not delete the journal to bypass it.
Rollback itself can be retried after a boot-image regeneration failure.

If boot-image generation fails, do not reboot until it succeeds. Inspect the
reported error (for example ESP free space, kernel headers, DKMS build logs),
then use rollback or repair the underlying problem. If the machine cannot boot,
use a previously working entry or Arch recovery media, mount root **and its ESP**,
enter the installation with `arch-chroot`, and inspect the journal. Run rollback
from a reviewed checkout inside that installation. If Limine is unavailable,
repair that tooling/mounts before regeneration; changing config files alone does
not update existing boot images. Full power-off/cold boot is the recorded recovery
for firmware-disabled Thunderbolt after unsafe deep sleep.

Rollback restores the previous configuration; on a fresh machine that can mean
returning to broken stock audio/sleep. It is not a guarantee of working hardware.

## Automated tests

```sh
python3 -m unittest discover -s tests -v
```

The tests use temporary roots and fake command results. They never invoke host
package installation, suspend, or reboot. `tests/arch-integration.py` additionally
exercises real package/DKMS operations and rollback in a **disposable** Arch
container/chroot/VM, with explicit doubles for hardware detection and boot-image
regeneration. Never run it on a working machine. It refuses MacBookPro14,1.
See [infrastructure and handoff](setup-handoff.md) for reproduction and limits.
