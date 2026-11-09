# Verification and recorded results

The organization change did not run hardware tests or suspend this machine.

| Check | Earlier evidence | Still needed |
| --- | --- | --- |
| Original audio | Speaker and microphone acoustic tests passed on October 13 | Repeat with current patched driver |
| Audio resume | Patched module built for both kernels and loaded November 8; PipeWire devices present | Acoustic checks before and after several sleep cycles |
| Keyboard backlight | Manual pre/post restored 255 → 0 → 255 | Confirm lid-close blanking and wake restoration |
| Thunderbolt suspend | Local package installed November 7; user later confirmed sleep/wake | Repeated peripheral checks and sleep battery measurement |

For a deliberate hardware check:

1. Check `dkms status`, `cat /sys/power/mem_sleep` (expect `[s2idle] deep`),
   and `lsmod | rg tb_ar_shim`.
2. Attach Yeti X and Sound Blaster Play! 3 and run `bash audio/test-audio.sh`.
   This plays a tone, changes internal speaker volume to 40% and USB playback
   volume to 60%, and unmutes internal playback. Record/restore your preferred
   levels afterward. PASS requires the tone component to exceed 20 times the
   baseline floor. Original recorded tone amplitudes were about 390–500 for speakers and
   640–1080 for the microphone, versus near-zero silent baselines.
3. Perform several lid-close/wake cycles, checking speakers, microphone,
   backlight restoration, Wi-Fi, and USB-C devices after each cycle.
4. Inspect `journalctl -b -k` for Thunderbolt and PM errors, and measure battery
   drain before relying on extended sleep.

Record new results with date, kernel versions, patch/module versions, and the
specific tests performed. Keep historical results distinct from fresh checks.
