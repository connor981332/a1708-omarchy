# A1708 Linux fixes

Local fixes and recovery notes for the 2017 A1708 MacBook Pro, MacBookPro14,1,
running Omarchy / Arch Linux. Other A1708 revisions have not been verified here.

Start with [installation](docs/installation.md) and [verification](docs/verification.md).

| Component | Source and instructions | Recorded status |
| --- | --- | --- |
| Internal CS8409 audio | [Audio](audio/README.md) | Original speakers/microphone tested; resume patch built and loaded, post-sleep acoustic checks pending |
| Thunderbolt / USB-C suspend | [Thunderbolt](thunderbolt/README.md) | Installed for both kernels; successful sleep/wake reported by user |
| Keyboard backlight | [Backlight](keyboard-backlight/README.md) | Manual pre/post test passed; actual sleep check pending |

Status summarizes earlier records, not a fresh hardware test. Upstream's own
28-cycle Thunderbolt validation is separate from this machine's installation.

`local/` holds machine-specific notes, original investigation records, and build
artifacts. It is excluded from future commits by `.gitignore`. The Thunderbolt
checkout is a pinned submodule retaining its upstream history and license.

## Clone

```sh
git clone --recurse-submodules git@github.com:connor981332/a1708-omarchy.git
cd a1708-omarchy
```

For an existing clone, run `git submodule update --init --recursive`.
See [third-party notices](THIRD-PARTY.md) for patch provenance and licensing.
