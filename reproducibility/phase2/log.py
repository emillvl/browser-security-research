from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, sys

ROOT = Path(__file__).resolve().parent


def event(kind, experiment, claim, files=None, **details):
    entry = {
        'time': datetime.now(timezone(timedelta(hours=4))).isoformat(),
        'kind': kind,
        'experiment': experiment,
        'claim': claim,
        'evidence': files or [],
        **details,
    }
    with (ROOT / 'chronology.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


if __name__ == '__main__':
    print(json.dumps(event(*sys.argv[1:4])))
