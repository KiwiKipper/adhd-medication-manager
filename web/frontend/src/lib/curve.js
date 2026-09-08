// Smooth curve helpers for medication release-curve charts.
// TODO: the actual release-curve data will come from the "pk" backend service;
// DAY_CURVE_BASE_POINTS below is placeholder shape data matching the design mock.

export function catmullRom(points) {
  if (points.length < 2) return ''
  let d = `M${points[0].x},${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2] || p2
    const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6
    const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2.x},${p2.y}`
  }
  return d
}

// Reference points in a 720 (x, 6am-12am) by 280 (y, 0%-100% inverted) space.
export const DAY_CURVE_BASE_POINTS = [
  { x: 0, y: 280 }, { x: 80, y: 280 }, { x: 128, y: 241 }, { x: 160, y: 98 }, { x: 180, y: 33 }, { x: 210, y: 85 },
  { x: 240, y: 163 }, { x: 280, y: 176 }, { x: 310, y: 137 }, { x: 340, y: 51.2 }, { x: 380, y: 72 },
  { x: 453, y: 163 }, { x: 500, y: 215 }, { x: 567, y: 254 }, { x: 640, y: 269.6 }, { x: 720, y: 280 },
]

// Scales DAY_CURVE_BASE_POINTS into the given chart-axis bounds and returns an SVG path.
export function dayCurvePath(x0, x1, y0, y1) {
  const sx = (x1 - x0) / 720
  const sy = (y1 - y0) / 280
  const scaled = DAY_CURVE_BASE_POINTS.map((p) => ({ x: p.x * sx + x0, y: p.y * sy + y0 }))
  return catmullRom(scaled)
}
