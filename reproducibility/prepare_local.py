from pathlib import Path
import argparse
import json
import secrets

ROOT = Path(__file__).resolve().parent


def prepare(root, ground_truth=None):
    if ground_truth is not None:
        data = ground_truth.read_bytes()
        parsed = json.loads(data)
        if (
            not isinstance(parsed, dict)
            or not isinstance(parsed.get('model'), dict)
            or not isinstance(parsed.get('vectors'), list)
        ):
            raise ValueError('Expected a model-server JSON file containing model and vectors')
        target = root / 'phase2/evidence/ground-truth.json'
        if target.exists():
            raise FileExistsError('Preserve existing ground-truth.json; use a fresh rerun copy')
    for relative in ['research/evidence', 'phase2/evidence']:
        (root / relative).mkdir(parents=True, exist_ok=True)
    config = root / 'phase2/protections/extension/config.js'
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        with config.open('x', encoding='utf-8') as output:
            output.write('const provisioningCredential=' + json.dumps(secrets.token_hex(32)) + ';\n')
    if ground_truth is not None:
        with target.open('xb') as output:
            output.write(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare private local inputs without starting experiments.')
    parser.add_argument('--ground-truth', type=Path, help='Explicit fresh model-server JSON to copy for older drivers')
    args = parser.parse_args()
    prepare(ROOT, args.ground_truth)
    print('Local directories and provisioning config are ready. Existing credentials were preserved.')
    if args.ground_truth is not None:
        print('Selected current-run input copied to phase2/evidence/ground-truth.json.')
