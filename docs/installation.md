# Installation and recovery

For automated installation of all selected fixes, see [unified setup](setup.md).
The commands below remain the manual route and recovery reference. Do not run
them concurrently with the unified installer.

These commands are instructions for deliberate system changes. The directory
reorganization itself did not install drivers or change system configuration.
Commands below assume the project root unless stated otherwise.

## Thunderbolt first

Build using the [Arch packaging instructions](../thunderbolt/README.md), then
install the resulting package with `sudo pacman -U <package-file>`.
Keep `mem_sleep_default=s2idle` in the boot command line. On the recorded Omarchy
installation it lives in `/etc/limine-entry-tool.d/macbook-s2idle.conf`; regenerate
boot images with `sudo limine-mkinitcpio` after boot configuration changes.
See the upstream README for other distributions and uninstall instructions.

## Current audio: rebuild an existing installation

Keep the persistent patched source at
`/usr/local/src/snd_hda_macbookpro-resume`, with DKMS version `0.1.resume1`.
Install headers matching every target kernel. Confirm `dkms status` and rebuild
for each installed kernel with headers, substituting its full version:

```sh
sudo dkms install --force -m snd_hda_macbookpro -v 0.1.resume1 -k <kernel-version>
sudo limine-mkinitcpio
```

Reboot afterward. Do not run the historical installer as routine recovery.

## Current audio: prepare source after a fresh OS installation

Install `git dkms base-devel wget patch` and the headers for each installed
kernel (`linux-headers`, `linux-omarchy-headers`, or the appropriate variants).
Internet is needed for upstream source and matching kernel tarballs.
The following prepares a new source directory; do not overwrite an existing one:

```sh
sudo git clone https://github.com/davidjo/snd_hda_macbookpro.git /usr/local/src/snd_hda_macbookpro-resume
sudo git -C /usr/local/src/snd_hda_macbookpro-resume checkout 89b22ff90b86468b186706861dd18663562defa7
sudo patch -d /usr/local/src/snd_hda_macbookpro-resume -p1 < audio/patches/audio-system-resume.diff
sudo sed -i 's/^PACKAGE_VERSION=.*/PACKAGE_VERSION="0.1.resume1"/' /usr/local/src/snd_hda_macbookpro-resume/dkms.conf
sudo ln -s /usr/local/src/snd_hda_macbookpro-resume /usr/src/snd_hda_macbookpro-0.1.resume1
sudo dkms add -m snd_hda_macbookpro -v 0.1.resume1
```

Then build/install for each kernel as above. These steps reproduce the recorded
source/version arrangement; a fresh reinstall was not performed during cleanup.
Install the WirePlumber rule as the desktop user:

```sh
install -Dm644 audio/51-cs8409-no-suspend.conf ~/.config/wireplumber/wireplumber.conf.d/51-cs8409-no-suspend.conf
systemctl --user restart wireplumber
```

## Keyboard backlight

Follow [the hook installation instructions](../keyboard-backlight/README.md).
Then reboot and complete [verification](verification.md).

Machine-specific installation and rollback history is retained locally and is
excluded from this public repository.
