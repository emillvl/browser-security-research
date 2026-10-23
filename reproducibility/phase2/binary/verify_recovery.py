"""Read Ghidra-exported data, reconstruct the interpreter table, and test held-out behavior."""

import struct, json, ctypes, random, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'binary/recovered-rdata.bin').read_bytes()
candidates = []
for offset in range(0, len(raw) - 248 * 20 + 1, 4):
    rows = [struct.unpack_from('<iiiii', raw, offset + i * 20) for i in range(248)]
    valid = True
    for i, (f, t, left, right, value) in enumerate(rows):
        if f == -1:
            if (t, left, right) != (0, -1, -1) or not 0 <= value < 1000:
                valid = False
                break
        elif not (
            0 <= f < 6 and 100 <= t < 900 and i < left < 248 and i < right < 248 and value == 0
        ):
            valid = False
            break
    if valid:
        candidates.append((offset, rows))
if len(candidates) != 1:
    raise RuntimeError('Unambiguous table recovery failed: ' + str(len(candidates)))
offset, rows = candidates[0]
dll = ctypes.CDLL(str(ROOT / 'binary/forest.dll'))
dll.dispatch_score.argtypes = [ctypes.POINTER(ctypes.c_int)]
dll.dispatch_score.restype = ctypes.c_int


def clone(input):
    total = 0
    for root in range(0, 248, 31):
        at = root
        while rows[at][0] >= 0:
            f, t, l, r, v = rows[at]
            at = l if input[f] <= t else r
        total += rows[at][4]
    return total // 8


rng = random.Random(4901)
results = []
for _ in range(1000):
    vector = [rng.randrange(1001) for _ in range(6)]
    results.append(
        {
            'input': vector,
            'native': dll.dispatch_score((ctypes.c_int * 6)(*vector)),
            'recovered': clone(vector),
        }
    )
report = {
    'format': 'Ghidra decompilation plus exported .rdata; a known five-integer node layout and eight depth-four trees are attacker assumptions',
    'rdataBytes': len(raw),
    'recoveredOffset': offset,
    'nodes': len(rows),
    'heldout': len(results),
    'matches': sum(r['native'] == r['recovered'] for r in results),
    'results': results,
    'table': rows,
}
(ROOT / 'binary/recovery-results.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k not in ['results', 'table']}, indent=2))
