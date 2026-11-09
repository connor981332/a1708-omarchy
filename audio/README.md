# CS8409 internal audio

The original fix used davidjo/snd_hda_macbookpro at
`89b22ff90b86468b186706861dd18663562defa7`, plus the adjacent WirePlumber
no-suspend rule. Stock CS8409 support did not initialize this Mac's amplifiers.
The rule avoids a delay when capture starts soon after playback ends.

The recorded current installation adds the system-sleep resume patch from
[upstream PR 228](https://github.com/davidjo/snd_hda_macbookpro/pull/228).
Its saved copy is [audio-system-resume.diff](patches/audio-system-resume.diff).
It replays amplifier setup after system sleep, including s2idle, without
repeating setup on ordinary runtime resumes.

Persistent source: `/usr/local/src/snd_hda_macbookpro-resume`.
DKMS identity: `snd_hda_macbookpro/0.1.resume1`.
See [installation](../docs/installation.md) for rebuild and reinstall steps.

`reload-audio.sh` reloads the driver and restarts the desktop audio services.
It interrupts current audio and needs sudo access; it does not install patches.
`test-audio.sh` performs acoustic loopback tests using Yeti X and Sound Blaster
Play! 3. It changes playback volume/mute settings; see
[verification](../docs/verification.md).

## Historical alternatives and rollback

`historical/audio-resume.diff` is the alternative GPIO-mask-based approach,
associated with PR 220 in the original notes. It was not selected: the measured
GPIO mask after a reported failed wake was 0x0f, whereas that patch checks zero.
Do not apply both patches.

`historical/install-original.sh` deliberately installs the original unpatched
driver. It requires `--restore-original` to avoid accidental rollback. It is
not the current reinstall procedure. Full machine-specific rollback records remain in the excluded local archive.

## Automated packaging

[Unified setup](../docs/setup.md) stages the adjacent Arch recipe with the
selected patch and builds `a1708-audio-dkms/0.1.resume1-1`. Fresh installations
place package-owned source at `/usr/src/snd_hda_macbookpro-0.1.resume1`; existing
matching manual sources are adopted without relocation. DKMS retains the
`snd_hda_macbookpro/0.1.resume1` identity. The system-wide WirePlumber rule is
installed separately with rollback tracking. This package has no dependency on
the historical installer. Kernel-source downloading remains upstream behavior.
