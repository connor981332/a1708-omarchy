# Thunderbolt suspend / USB-C recovery

[The upstream checkout](linux-apple-alpine-ridge-suspend/README.md) contains the
DKMS module, proposed kernel patch, license, and original CI. Its Git history
and origin remote are preserved. The kernel patch is documented as unvalidated
on hardware; the upstream DKMS module has separate recorded hardware testing.

For this Mac, the module and `mem_sleep_default=s2idle` are both needed. The
module addresses lost PCI configuration; s2idle avoids a separate firmware S3
failure. See [installation](../docs/installation.md).

## Local Arch package

The [PKGBUILD](packaging/arch/PKGBUILD) fetches the upstream archive at
`155ffe3a4a963bc8d84df72fa53f14eb16ea9a60`, verified by SHA-256. It is now
self-contained for clean builds and does not depend on adjacent checkout
symlinks. The pinned submodule remains the browsable upstream reference.

```sh
cd packaging/arch
makepkg
```

[Unified setup](../docs/setup.md) stages this recipe and handles installation,
DKMS verification for every installed kernel, the separate s2idle boot setting,
and rollback. A standalone package install alone does not configure s2idle.
The upstream README's anticipated automatic Omarchy integration should not be
assumed to be present; the installer checks actual local state.

When updating upstream, review and update the pinned archive revision and
checksum. Build outputs remain ignored under `local/` or the packaging directory.
