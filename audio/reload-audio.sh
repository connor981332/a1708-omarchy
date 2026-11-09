#!/bin/bash
set -euo pipefail
# Run as the desktop user; keep sockets stopped while unloading the codec.
systemctl --user stop wireplumber pipewire-pulse.service pipewire.service pipewire-pulse.socket pipewire.socket
restore_audio() {
  systemctl --user start pipewire.socket pipewire-pulse.socket pipewire.service pipewire-pulse.service wireplumber
}
trap restore_audio EXIT
sudo -n modprobe -r snd_hda_intel
sudo -n modprobe -r snd_hda_codec_cs8409
sudo -n modprobe snd_hda_intel
