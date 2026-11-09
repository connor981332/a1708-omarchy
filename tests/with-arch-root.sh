#!/bin/bash
# Execute in a disposable extracted Arch bootstrap root, using user namespaces.
# No host sudo, device passthrough, sysfs, boot mounts, or host package writes.
set -euo pipefail
if (( $# < 2 )); then
  echo "Usage: $0 /absolute/path/to/root.x86_64 command [args...]" >&2
  exit 2
fi
root=$(realpath "$1")
shift
[[ $root != / && -f $root/etc/arch-release && -d $root/usr/bin ]] || exit 2
# shellcheck disable=SC2016 # The single-quoted program executes inside the namespace.
exec unshare --user --map-auto --map-root-user --mount --pid --fork \
  bash -eu -c '
    root=$1
    shift
    mount --make-rprivate /
    mount --bind "$root" "$root"
    mount -t proc proc "$root/proc"
    for device in null zero random urandom; do
      touch "$root/dev/$device"
      mount --bind "/dev/$device" "$root/dev/$device"
    done
    ln -sfn /proc/self/fd "$root/dev/fd"
    ln -sfn /proc/self/fd/0 "$root/dev/stdin"
    ln -sfn /proc/self/fd/1 "$root/dev/stdout"
    ln -sfn /proc/self/fd/2 "$root/dev/stderr"
    cp -L /etc/resolv.conf "$root/etc/resolv.conf"
    exec chroot "$root" "$@"
  ' bash "$root" "$@"
