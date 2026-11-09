# Keyboard backlight across sleep

`macbook-keyboard-backlight` is a systemd sleep hook restricted to MacBookPro14,1.
It saves brightness in `/run`, blanks the SPI backlight before sleep, and restores
brightness afterward. Install with:

```sh
sudo install -m755 macbook-keyboard-backlight /usr/lib/systemd/system-sleep/macbook-keyboard-backlight
```

Run that command from this directory. The earlier manual pre/post test passed
(255 → 0 → 255); actual lid-close verification remains pending. See
[verification](../docs/verification.md). To remove:

```sh
sudo rm /usr/lib/systemd/system-sleep/macbook-keyboard-backlight
```
