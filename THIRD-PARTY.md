# Third-party notices

## CS8409 audio patches

The saved patches modify [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro)
at base commit `89b22ff90b86468b186706861dd18663562defa7`.
The project ships the GNU GPL version 2; its license text is reproduced in
[audio/patches/COPYING](audio/patches/COPYING). Original upstream copyright
notices remain with the upstream source and are not replaced by this collection.

- `audio/patches/audio-system-resume.diff`: system-sleep notifier approach,
  recorded as applied from [PR 228](https://github.com/davidjo/snd_hda_macbookpro/pull/228).
- `audio/historical/audio-resume.diff`: alternate GPIO-mask approach,
  associated in the investigation notes with [PR 220](https://github.com/davidjo/snd_hda_macbookpro/pull/220).
  Preserved for reference; not part of the selected installation.

## Thunderbolt

The pinned submodule is [orospakr/linux-apple-alpine-ridge-suspend](https://github.com/orospakr/linux-apple-alpine-ridge-suspend),
commit `155ffe3a4a963bc8d84df72fa53f14eb16ea9a60`, authored by Andrew Clunis.
Its GPL-2.0-only license and attribution are retained in the submodule.

This collection does not claim authorship of third-party work or apply a new
blanket license to it. No additional license is assigned to the local scripts
and documentation in this initial publication.
