// Deterministic research fixture: eight decision trees, six inputs, known ground truth.
export function fixtureModel(seed = 12648430) {
  let state = seed >>> 0;
  const rand = () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return state >>> 0;
  };
  const tree = (depth) =>
    depth === 0
      ? { value: rand() % 1000 }
      : {
          feature: rand() % 6,
          threshold: 100 + (rand() % 800),
          left: tree(depth - 1),
          right: tree(depth - 1),
        };
  return {
    id: "dispatch-forest",
    version: 1,
    features: 6,
    domain: [0, 1000],
    trees: Array.from({ length: 8 }, () => tree(4)),
  };
}
export function evaluateModel(model, input) {
  if (
    !Array.isArray(input) ||
    input.length !== 6 ||
    input.some((v) => !Number.isInteger(v) || v < 0 || v > 1000)
  )
    throw Error("Six integers from 0 through 1000 required");
  let sum = 0;
  for (const tree of model.trees) {
    let node = tree;
    while (node.value === undefined)
      node = input[node.feature] <= node.threshold ? node.left : node.right;
    sum += node.value;
  }
  const score = Math.floor(sum / model.trees.length);
  return { score, band: score < 350 ? "low" : score < 650 ? "medium" : "high" };
}
export function vector(i) {
  return Array.from({ length: 6 }, (_, j) => ((i + 17) * (j * 173 + 97) + j * j * 29) % 1001);
}
