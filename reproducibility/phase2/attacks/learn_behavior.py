"""Separate offline learner. It sees queried input/output pairs, not fixture source or constants."""

import json, sys, time, math
from pathlib import Path
import numpy as np

source = Path(sys.argv[1])
data = json.loads(source.read_text())
X = np.array([p['input'] for p in data['training']], dtype=float)
y = np.array([p['output']['score'] for p in data['training']], dtype=float)
test = np.array([p['input'] for p in data['heldout']], dtype=float)
truth = np.array([p['output']['score'] for p in data['heldout']], dtype=float)


def grow(x, target, depth):
    if depth == 0 or len(target) < 16:
        return float(target.mean())
    best = None
    for feature in range(x.shape[1]):
        order = np.argsort(x[:, feature], kind='stable')
        values = x[order, feature]
        t = target[order]
        prefix = np.cumsum(t)
        square = np.cumsum(t * t)
        n = len(t)
        positions = np.arange(8, n - 7)
        valid = values[positions - 1] != values[positions]
        positions = positions[valid]
        if not len(positions):
            continue
        score = (
            square[positions - 1]
            - prefix[positions - 1] ** 2 / positions
            + (square[-1] - square[positions - 1])
            - (prefix[-1] - prefix[positions - 1]) ** 2 / (n - positions)
        )
        i = int(np.argmin(score))
        position = positions[i]
        candidate = (float(score[i]), feature, float((values[position - 1] + values[position]) / 2))
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        return float(target.mean())
    _, feature, threshold = best
    left = x[:, feature] <= threshold
    return [
        feature,
        threshold,
        grow(x[left], target[left], depth - 1),
        grow(x[~left], target[~left], depth - 1),
    ]


def predict(tree, x):
    if not isinstance(tree, list):
        return np.full(len(x), tree)
    feature, threshold, left, right = tree
    mask = x[:, feature] <= threshold
    result = np.empty(len(x))
    result[mask] = predict(left, x[mask])
    result[~mask] = predict(right, x[~mask])
    return result


def fit(x, target):
    mean = float(target.mean())
    prediction = np.full(len(target), mean)
    trees = []
    for _ in range(90):
        tree = grow(x, target - prediction, 3)
        prediction += 0.12 * predict(tree, x)
        trees.append(tree)
    return {'mean': mean, 'rate': 0.12, 'trees': trees}


def run(model, x):
    return np.full(len(x), model['mean']) + sum(
        (model['rate'] * predict(t, x) for t in model['trees']), np.zeros(len(x))
    )


def bands(scores):
    return np.where(scores < 350, 0, np.where(scores < 650, 1, 2))


results = {
    'learner': '90 depth-three squared-error boosting trees; shrinkage 0.12; at least eight samples per leaf; no fixture constants supplied',
    'heldout': len(test),
    'curves': [],
}
sizes = json.loads(sys.argv[2]) if len(sys.argv) > 2 else [32, 128, 512, 2048]
for size in sizes:
    start = time.perf_counter()
    model = fit(X[:size], y[:size])
    score = np.rint(run(model, test))
    band = bands(score)
    labels = bands(truth)
    common = int(np.bincount(bands(y[:size]), minlength=3).argmax())
    entry = {
        'queries': size,
        'exactScore': int(np.sum(score == truth)),
        'scoreMAE': float(np.mean(abs(score - truth))),
        'bandMatches': int(np.sum(band == labels)),
        'majorityBandMatches': int(np.sum(labels == common)),
        'trainingSeconds': time.perf_counter() - start,
    }
    # Train on low/medium/high labels when outputs are minimized.
    category_model = fit(X[:size], bands(y[:size]).astype(float))
    category = np.clip(np.rint(run(category_model, test)), 0, 2)
    entry['bandOnlyMatches'] = int(np.sum(category == labels))
    results['curves'].append(entry)
    if size == max(sizes):
        (source.parent / 'learned-offline-model.json').write_text(json.dumps(model))
results['cachedTrainingRows'] = len({tuple(row) for row in X.tolist()})
results['heldoutCacheHits'] = sum(
    tuple(row) in {tuple(v) for v in X.tolist()} for row in test.tolist()
)
(source.parent / 'learning-results.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
