# Thunderbolt suspend / USB-C recovery

[The upstream checkout](linux-apple-alpine-ridge-suspend/README.md) contains the
DKMS module, proposed kernel patch, license, and original CI. Its Git history
and origin remote are preserved. The kernel patch is documented as unvalidated
on hardware; the upstream DKMS module has separate recorded hardware testing.

For this Mac, the module and `mem_sleep_default=s2idle` are both needed. The
module addresses lost PCI configuration; s2idle avoids a separate firmware S3
failure. See [installation](../docs/installation.md).

## Local Arch package

The [PKGBUILD](packaging/arch/PKGBUILD) reads module files from the adjacent
checkout, pinned to commit `155ffe3a4a963bc8d84df72fa53f14eb16ea9a60` and verified
by SHA-256. Three relative symlinks expose the canonical sources to makepkg. It stages
files during `makepkg`; no second maintained source copy
is needed. To build without installing:

```sh
cd packaging/arch
makepkg
```

Install dependencies separately if makepkg reports any. When updating upstream,
review and update both the pinned commit and checksums. Existing package and
staging artifacts are preserved under `local/builds/thunderbolt/` at the project
root. Staging symlinks now use relative paths to the canonical module source.
