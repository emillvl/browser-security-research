"""Append research events and evidence hashes to the workspace log."""

from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, hashlib, argparse

ROOT = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=4))


def record(kind, experiment, claim, evidence=None, **extra):
    event = {
        "time": datetime.now(TZ).isoformat(),
        "kind": kind,
        "experiment": experiment,
        "claim": claim,
        "evidence": evidence or [],
        **extra,
    }
    with (ROOT / "chronology.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("kind")
    p.add_argument("experiment")
    p.add_argument("claim")
    a = p.parse_args()
    print(json.dumps(record(a.kind, a.experiment, a.claim)))
