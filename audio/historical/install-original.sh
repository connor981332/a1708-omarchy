#!/bin/bash
# Installs the Apple CS8409 audio driver (davidjo/snd_hda_macbookpro) via DKMS
# for every kernel installed on this Omarchy/Arch machine (MacBook Pro A1708).
# Historical rollback installer: omits the system-sleep resume patch.
#
# Usage: ./install-original.sh --restore-original (uses sudo itself)
set -euo pipefail
if [[ ${1:-} != --restore-original ]]; then
  echo 'Historical installer: replaces the audio fix with the original driver.' >&2
  echo 'For deliberate rollback only: ./install-original.sh --restore-original' >&2
  exit 2
fi

REPO=https://github.com/davidjo/snd_hda_macbookpro.git
COMMIT=89b22ff90b86468b186706861dd18663562defa7   # known-good (2026-09-06)
SRC_DIR=/usr/local/src/snd_hda_macbookpro          # must persist: DKMS symlinks to it
DKMS_ID=snd_hda_macbookpro/0.1

[[ $EUID -eq 0 ]] || exec sudo -E "$0" "$@"

echo "==> Installing build dependencies"
pkgs=(git dkms base-devel wget patch)
for k in linux linux-omarchy linux-lts linux-zen; do
  pacman -Q "$k" &>/dev/null && pkgs+=("$k-headers")
done
pacman -S --needed --noconfirm "${pkgs[@]}"

echo "==> Fetching driver source ($COMMIT)"
if [[ ! -d $SRC_DIR/.git ]]; then
  git clone "$REPO" "$SRC_DIR"
fi
git -C "$SRC_DIR" fetch --quiet origin || true
git -C "$SRC_DIR" checkout --quiet "$COMMIT"

# The upstream pre-build script downloads the matching kernel.org source
# tarball, so this needs internet access. Our dkms.sh-style symlink:
ln -sfn "$SRC_DIR" /usr/src/snd_hda_macbookpro-0.1

echo "==> Building/installing for each installed kernel"
cd "$SRC_DIR"
for dir in /usr/lib/modules/*/; do
  k=$(basename "$dir")
  if [[ ! -e $dir/build ]]; then
    echo "   skip $k (no headers)"
    continue
  fi
  echo "   -> $k"
  dkms install -c dkms.conf --force -m "$DKMS_ID" -k "$k"
done
dkms status

# Reload the driver now if the running kernel was just built, so no reboot is needed
echo "==> Reloading sound modules"
U=${SUDO_USER:-$(logname)}
usrctl() { sudo -u "$U" XDG_RUNTIME_DIR=/run/user/$(id -u "$U") systemctl --user "$@" 2>/dev/null || true; }
usrctl stop wireplumber pipewire-pulse pipewire pipewire.socket pipewire-pulse.socket
modprobe -r snd_hda_intel snd_hda_codec_cs8409 2>/dev/null || echo "   (could not unload; reboot to apply)"
modprobe snd_hda_intel || true
sleep 2
usrctl start pipewire.socket pipewire-pulse.socket pipewire wireplumber

echo "==> Installing WirePlumber no-suspend rule for the internal card"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WP=$(getent passwd "$U" | cut -d: -f6)/.config/wireplumber/wireplumber.conf.d
sudo -u "$U" mkdir -p "$WP"
sudo -u "$U" cp "$HERE/../51-cs8409-no-suspend.conf" "$WP/"
usrctl restart wireplumber

echo "Done. Run ./test-audio.sh to verify (needs the Yeti X + Sound Blaster Play! 3 attached)."
