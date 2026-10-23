import { createHash } from "node:crypto";
import { fixtureModel, evaluateModel } from "./workload.mjs";
export const forest = fixtureModel();
export const catalogue = Array.from({ length: 16 }, (_, i) => ({
  id: "P" + String(i + 1).padStart(2, "0"),
  name: ["Sensor", "Cable", "Bracket", "Valve"][i % 4] + " " + (i + 1),
  price: 425 + ((i * 137) % 2200),
  stock: 8 + (i % 5),
}));
export function planRoute(input) {
  const start = input.start,
    end = input.end;
  if (
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    start < 0 ||
    end < 0 ||
    start >= 24 ||
    end >= 24
  )
    throw Error("Node numbers must be 0 through 23");
  const congestion = Number(input.congestion || 0);
  if (!Number.isInteger(congestion) || congestion < 0 || congestion > 20)
    throw Error("Congestion must be 0 through 20");
  const dist = Array(24).fill(Infinity),
    previous = Array(24).fill(-1),
    used = new Set();
  dist[start] = 0;
  for (let step = 0; step < 24; step++) {
    let node = -1;
    for (let j = 0; j < 24; j++) if (!used.has(j) && (node < 0 || dist[j] < dist[node])) node = j;
    if (node < 0 || !Number.isFinite(dist[node])) break;
    used.add(node);
    for (let next = 0; next < 24; next++) {
      if (next === node || !((node + next) % 4 === 0 || Math.abs(next - node) === 1)) continue;
      const weight = 3 + ((node * 17 + next * 11) % 29) + ((node + next) % 3) * congestion;
      if (dist[node] + weight < dist[next]) {
        dist[next] = dist[node] + weight;
        previous[next] = node;
      }
    }
  }
  const route = [];
  for (let at = end; at >= 0; at = previous[at]) {
    route.unshift(at);
    if (at === start) break;
  }
  return { distance: dist[end], route };
}
export function pureOperation(op, input) {
  if (op === "score") return evaluateModel(forest, input);
  if (op === "route") return planRoute(input);
  throw Error("Not a pure operation");
}
export const canonical = (value) =>
  Array.isArray(value)
    ? "[" + value.map(canonical).join(",") + "]"
    : value !== null && typeof value === "object"
      ? "{" +
        Object.keys(value)
          .sort()
          .map((k) => JSON.stringify(k) + ":" + canonical(value[k]))
          .join(",") +
        "}"
      : JSON.stringify(value);
export const hash = (value) =>
  createHash("sha256")
    .update(typeof value === "string" ? value : canonical(value))
    .digest("hex");
