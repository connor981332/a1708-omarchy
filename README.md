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

Clone with submodules to include the pinned Thunderbolt source:

```sh
git clone --recurse-submodules https://github.com/connor981332/a1708-omarchy.git
cd a1708-omarchy
```

If you already cloned the repository:

```sh
git submodule update --init --recursive
```

Use [unified setup](docs/setup.md) for the experimental automated route, or
follow [manual installation and recovery](docs/installation.md), starting with
Thunderbolt, then audio and the keyboard backlight hook. The component READMEs
provide the details and rollback notes. The instructions cover both preparing
the current audio source on a fresh installation and rebuilding an existing
DKMS installation.

The documented installation uses Arch tooling, DKMS, matching kernel headers,
and Omarchy's Limine boot-image tooling. Build the drivers for every kernel you
intend to boot. The Thunderbolt module and the `s2idle` boot setting address
separate problems; the module alone is not the complete fix.

After installation and reboot, follow the
[verification procedure](docs/verification.md) to check audio, sleep/wake,
backlight restoration, and connected devices.

## Automation status

The experimental [`a1708-setup`](docs/setup.md) CLI now builds pinned audio and
Thunderbolt DKMS packages, checks compatibility, installs all three selected
fixes plus the s2idle boot setting, and records a rollback transaction. It
supports read-only status/planning/verification and adopts matching existing
manual audio sources. It does not reboot or suspend automatically.

Start with [unified setup](docs/setup.md), including prerequisites and recovery.
[Validation and handoff](docs/setup-handoff.md) separates automated results from
pending fresh-Omarchy and physical hardware tests. This is not yet a validated
fresh-machine installer; only MacBookPro14,1 is supported.

The audio reload/acoustic test scripts remain separate deliberate tools.
`audio/historical/install-original.sh` restores the original audio driver; it
is not the unified installer's rollback command or the current installer.
The alternate historical audio patch must not be combined with the selected
resume patch. The bundled Thunderbolt installer targets other distributions;
use unified setup or the local Arch package recipe on Omarchy.

## Repository layout

- [`audio/`](audio/README.md): current audio patch, WirePlumber configuration,
  recovery/test scripts, and historical alternatives.
- [`thunderbolt/`](thunderbolt/README.md): pinned upstream submodule and local
  Arch package recipe for the suspend/resume module.
- [`keyboard-backlight/`](keyboard-backlight/README.md): systemd sleep hook and
  installation/removal instructions.
- [`setup/`](docs/setup.md): unified installer, transaction handling, and build staging.
- [`tests/`](docs/setup-handoff.md): offline, disposable Arch, and UEFI VM tests.
- [`docs/installation.md`](docs/installation.md): installation and rebuild steps.
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
