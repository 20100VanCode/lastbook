#!/bin/bash
# Records SECS seconds from the bench's null sound card and says whether anything was heard. Never packaged.
#   linux_env.sh run bash linux_sound.sh SECS OUT.wav
SECS="${1:-6}"; OUT="${2:-/tmp/heard.wav}"
timeout "$SECS" parecord --device=lbsink.monitor --file-format=wav "$OUT" 2>/dev/null
python3 - "$OUT" <<'PY'
import sys, wave, array
w = wave.open(sys.argv[1]); a = array.array('h', w.readframes(w.getnframes()))
peak = max((abs(x) for x in a), default=0)
print(f'sound: {len(a)} samples, peak {peak} ->', 'HEARD' if peak > 300 else 'SILENT')
PY
