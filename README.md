# Omarchy on the A1708 MacBook Pro

Fixes, installation notes, and recovery tools for running **Omarchy Linux on an
Apple A1708 MacBook Pro**. This repository documents the hardware issues found
along the way, preserves the patches used to address them, and provides an
experimental setup CLI to apply them together.

The recorded setup is a **2017 13-inch MacBook Pro, MacBookPro14,1** (two
Thunderbolt 3 ports, no Touch Bar), running Omarchy / Arch Linux. Other A1708
revisions have not been verified. These fixes may also apply to other Linux
distributions, but this project has only tested them on Omarchy.

## Fixes covered

| Component | Problem and approach | Recorded results |
| --- | --- | --- |
| [Internal audio](audio/README.md) | Use the patched CS8409 driver to initialize the internal speakers and microphone and restore amplifier setup after system sleep. A WirePlumber rule prevents idle suspension of the internal audio nodes. | Speakers and microphone passed acoustic tests with the original driver fix. The additional resume patch was built and loaded; acoustic checks after sleep are still pending. |
| [Thunderbolt / USB-C](thunderbolt/README.md) | Use the `tb_ar_shim` DKMS module to preserve controller PCI configuration across sleep, together with `mem_sleep_default=s2idle` to avoid a separate firmware issue with deep sleep. | Installed for both kernels in the recorded setup; successful sleep/wake reported by the user. Repeated peripheral checks and sleep battery measurements remain to be done. |
| [Keyboard backlight](keyboard-backlight/README.md) | Install a systemd sleep hook that saves brightness, blanks the backlight before sleep, and restores it after wake. The hook only runs on MacBookPro14,1. | Manual pre/post test passed (255 → 0 → 255); actual lid-close/wake verification is pending. |

These are recorded results, not a claim that every fix has passed a fresh
end-to-end hardware test. The Thunderbolt upstream project's own 28-cycle
validation is separate from this machine's results. See
[verification and recorded results](docs/verification.md) for the remaining
checks.

## Getting started

The unified installer targets **MacBookPro14,1 on x86_64 Omarchy with Limine**.
It applies the selected fixes to an existing Omarchy installation; it does not
install the OS or partition disks. Fresh installation on the physical Mac is
still awaiting acceptance testing.

Clone with submodules to include the pinned Thunderbolt reference source:

```sh
git clone --recurse-submodules https://github.com/connor981332/a1708-omarchy.git
cd a1708-omarchy
```

For an existing clone, run `git submodule update --init --recursive`.
The package recipes fetch their own pinned source archives; they do not depend
on local submodule modifications.

Read [installation and recovery](docs/setup.md) before applying changes. Start
with an updated Omarchy installation, Python 3, WirePlumber, `base-devel`, `git`,
`dkms`, `wget`, `patch`, and headers matching **every installed kernel**.
Internet access is required for upstream source and kernel-source downloads.
Prerequisite provisioning is currently a separate maintenance step.

From the repository root, as your ordinary desktop user:

```sh
./a1708-setup status
./a1708-setup build
./a1708-setup plan
```

`status` and `plan` are read-only. `build` creates packages and a checksum manifest
under ignored `local/setup-bundle/` without installing host packages. Review the
plan and resolve any reported blockers before applying:

```sh
sudo ./a1708-setup apply
```

The installer builds/verifies both DKMS drivers for every installed kernel,
installs the WirePlumber rule and backlight hook, sets the s2idle boot default,
and regenerates Limine boot images. It does not reboot, suspend, reload live
audio, or restart desktop audio services automatically.

After a successful apply, reboot before testing sleep, log into the desktop,
and run:

```sh
./a1708-setup verify
```

Then follow [hardware verification](docs/verification.md). Software verification
alone does not establish working speakers, microphone, backlight, or peripherals
after sleep. If applying or rebuilding boot images fails, follow the recovery
guide before rebooting.

To undo the recorded setup transaction:

```sh
sudo ./a1708-setup rollback
```

Rollback restores recorded package/file changes and regenerates boot images.
Matching pre-existing packages, configuration, and adopted manual audio sources
are retained. See [transactions and recovery](docs/setup.md#transactions-reruns-and-recovery)
for drift checks, interrupted installations, and recovery-media instructions.
The [manual installation guide](docs/installation.md) remains available for
component-specific installation and repair.

## Installer behavior and limits

| Capability | Behavior |
| --- | --- |
| Compatibility checks | Requires MacBookPro14,1, the expected Alpine Ridge bridge and CS8409 codec, Omarchy/Limine, prerequisites, and matching kernel headers. |
| Existing installations | Retains matching packages/files and adopts matching manual audio sources after checking their hashes and DKMS installation for every kernel. |
| Configuration conflicts | Stops on unknown managed-file contents, competing DKMS versions, enabled Secure Boot, or a replacing Limine command-line assignment that would erase drop-in arguments. |
| Reruns and rollback | An unchanged completed setup can be rerun without reinstalling packages or rebuilding images. One rollback baseline is retained at a time. |
| Kernel maintenance | DKMS hooks build the drivers for added kernels. Repeat verification after kernel updates; future kernel compatibility is not guaranteed. |

This remains experimental pending fresh Omarchy and physical hardware acceptance.
Automatic prerequisite provisioning and multi-generation installer upgrades are
not implemented. Audio's upstream kernel-source download retains its HTTPS and
fallback behavior without independent checksum/signature verification; the
[setup guide](docs/setup.md) explains this limitation and bundle trust.

The audio reload/acoustic test scripts remain separate deliberate tools.
`audio/historical/install-original.sh` restores the original audio driver; it
is not the unified installer's rollback command or the current installer.
Do not combine the historical audio patch with the selected resume patch.
The bundled upstream Thunderbolt installer targets other distributions; use
unified setup or the local Arch recipe on Omarchy. The Thunderbolt module and
`s2idle` setting address separate problems and are both part of this setup.

## Validation and remaining work

The [validation record and handoff](docs/setup-handoff.md) documents the completed
November 8–9, 2026 checks, source pins, environment versions, and reproduction
steps:

- **29 automated decision/transaction tests passed**, including compatibility,
  conflicts, source adoption, failure recovery, reruns, and rollback.
- Clean Arch builds and real DKMS installation passed for
  **7.2.14-arch1-1** and **6.18.60-1-lts**, with matching module metadata.
- Adding LTS after setup automatically built both drivers through pacman's hooks;
  rollback removed their DKMS registrations for both kernels.
- A complete unattended **UEFI apply → reboot → rollback → reboot** cycle passed
  with real Limine boot-image generation and verification of the running s2idle
  argument before rollback and its removal afterward.
- [CI](https://github.com/connor981332/a1708-omarchy/actions/workflows/setup.yml)
  passed and repeats offline/package/kernel-addition checks on pushes, PRs, and
  weekly. The UEFI VM harness is available separately under `tests/`.

The boot test used a minimal Arch VM with Omarchy boot tooling and explicit
hardware/OS test doubles. It did not install a full Omarchy desktop or test the
Mac's physical audio, Thunderbolt, backlight, or sleep behavior. The working
Mac's drivers, boot configuration, and power state were unchanged during these
automation tests.

The mandatory next acceptance gate is **fresh Omarchy on the physical
MacBookPro14,1**, preferably on a separate test SSD with its own EFI partition.
The owner needs to provide and identify a disk whose contents may be erased,
select the test installation at boot, and help with acoustic equipment and
physical observations. Remaining checks include audio before/after sleep,
actual lid-close/backlight restoration, USB-C peripherals, and sleep battery
measurements. Because USB-C is being repaired, an external system disk can
itself be affected by a controller failure.

Future agents should read the [owner and agent handoff](docs/setup-handoff.md),
check current PR/CI state, and preserve the working internal installation.
Treat that document's branch/PR references as the implementation session's
historical record; check whether they have merged before starting new work.

## Repository layout

- [`audio/`](audio/README.md): current audio patch, WirePlumber configuration,
  recovery/test scripts, and historical alternatives.
- [`thunderbolt/`](thunderbolt/README.md): pinned upstream submodule and local
  Arch package recipe for the suspend/resume module.
- [`keyboard-backlight/`](keyboard-backlight/README.md): systemd sleep hook and
  installation/removal instructions.
- [`setup/`](docs/setup.md): unified installer, transaction handling, and build staging.
- [`tests/`](docs/setup-handoff.md): offline, disposable Arch, and UEFI VM tests.
- [`docs/setup.md`](docs/setup.md): unified setup, prerequisites, and rollback.
- [`docs/setup-handoff.md`](docs/setup-handoff.md): validation evidence and owner/agent tasks.
- [`docs/installation.md`](docs/installation.md): manual installation and rebuild steps.
- [`docs/verification.md`](docs/verification.md): hardware checks, recorded
  evidence, and outstanding validation.

Machine-specific investigation notes and build artifacts live in `local/`,
which is ignored by Git and is not included in a clone.

## Attribution and licensing

The audio driver patches build on
[davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro).
The Thunderbolt fix comes from
[orospakr/linux-apple-alpine-ridge-suspend](https://github.com/orospakr/linux-apple-alpine-ridge-suspend)
by Andrew Clunis and is retained as a pinned submodule.

See [third-party notices](THIRD-PARTY.md) for exact revisions, patch provenance,
and licenses. This repository does not assign a blanket license to all its
contents; the local scripts and documentation currently have no additional
license assigned.
