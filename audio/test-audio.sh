#!/bin/bash
# Loopback test of the internal CS8409 speaker and mic using known-good USB devices:
#   speaker: play tone on internal speaker, record on Yeti X
#   mic:     play tone on Sound Blaster Play! 3, record on internal mic
# Passes if the 1 kHz component of the recording is well above a silent baseline.
set -euo pipefail

INT_SINK=alsa_output.pci-0000_00_1f.3.analog-stereo
INT_SRC=alsa_input.pci-0000_00_1f.3.analog-stereo
YETI_SRC=$(pactl list short sources | cut -f2 | grep -m1 'Yeti_X.*analog-stereo$')
SB_SINK=$(pactl list short sinks | cut -f2 | grep -m1 'Sound_Blaster_Play__3')
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

python3 - "$T/tone.wav" <<'E'
import wave, struct, math, sys
w = wave.open(sys.argv[1], 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
w.writeframes(b''.join(struct.pack('<hh', *(int(12000*math.sin(2*math.pi*1000*i/48000)),)*2) for i in range(48000*4)))
E

cat > "$T/an.py" <<'E'
import wave, struct, math, sys
w = wave.open(sys.argv[1]); sr = w.getframerate(); ch = w.getnchannels()
d = w.readframes(w.getnframes()); s = struct.unpack('<%dh' % (len(d)//2), d)[::ch]
k = 2*math.pi*1000/sr
re = sum(x*math.cos(k*i) for i, x in enumerate(s)); im = sum(x*math.sin(k*i) for i, x in enumerate(s))
print(round(2*math.hypot(re, im)/len(s), 1))
E

rec() { # rec <source> <out.wav> [sink-to-play-tone-on]
  pw-record --target "$1" "$2" & local p=$!
  sleep 5   # idle capture nodes can take several seconds to wake up
  [[ -n ${3:-} ]] && pw-play --target "$3" "$T/tone.wav" || sleep 4
  sleep 1; kill $p; wait $p 2>/dev/null || true
}
amp() { python3 "$T/an.py" "$1"; }

pactl set-sink-mute "$INT_SINK" 0; pactl set-sink-volume "$INT_SINK" 40%
pactl set-sink-volume "$SB_SINK" 60%

rec "$YETI_SRC" "$T/spk_base.wav";            rec "$YETI_SRC" "$T/spk.wav" "$INT_SINK"
rec "$INT_SRC"  "$T/mic_base.wav";            rec "$INT_SRC"  "$T/mic.wav" "$SB_SINK"

ok=0
for t in spk mic; do
  b=$(amp "$T/${t}_base.wav"); s=$(amp "$T/$t.wav")
  if python3 -c "import sys; sys.exit(0 if $s > 20*max($b,1) else 1)"; then r=PASS; else r=FAIL; ok=1; fi
  echo "$t: baseline=$b tone=$s  $r"
done
exit $ok
