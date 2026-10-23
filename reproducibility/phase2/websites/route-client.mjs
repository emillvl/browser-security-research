export function planRoute(input) {
  const { start, end } = input,
    congestion = Number(input.congestion || 0);
  if (
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    start < 0 ||
    end < 0 ||
    start > 23 ||
    end > 23 ||
    !Number.isInteger(congestion) ||
    congestion < 0 ||
    congestion > 20
  )
    throw Error("Invalid routing input");
  const dist = Array(24).fill(Infinity),
    previous = Array(24).fill(-1),
    used = new Set();
  dist[start] = 0;
  for (let step = 0; step < 24; step++) {
    let node = -1;
    for (let j = 0; j < 24; j++) if (!used.has(j) && (node < 0 || dist[j] < dist[node])) node = j;
    if (node < 0 || !Number.isFinite(dist[node])) break;
    used.add(node);
    for (let next = 0; next < 24; next++)
      if (next !== node && ((node + next) % 4 === 0 || Math.abs(next - node) === 1)) {
        const value =
          dist[node] + 3 + ((node * 17 + next * 11) % 29) + ((node + next) % 3) * congestion;
        if (value < dist[next]) {
          dist[next] = value;
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
