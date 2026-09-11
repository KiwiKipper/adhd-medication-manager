// Chart helpers for the release-curve pages.
//
// The curve itself is computed by the pk module: fetchTimeline() in api.js
// returns `curve: [{ t_h, level }]`, sampled every few minutes from the
// moment the dose was taken, with `level` as a proportion of that curve's
// own peak (so 1 is the peak, not a blood concentration). Nothing in this
// file models anything -- these functions only map pk's samples onto chart
// coordinates. The hand-drawn DAY_CURVE_BASE_POINTS that used to live here,
// and the design mock's fixed 6am-midnight axis with it, are gone: the axis
// now follows the dose the user actually logged.

const HOUR_MS = 3_600_000

// A polyline through pk's samples. Deliberately not a smoothed spline: the
// samples are dense (one every few minutes), so straight segments between
// them draw the curve pk computed rather than inventing shape between points.
export function pathFromPoints(points) {
  if (!points.length) return ''
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ')
}

// The chart's time axis, in real clock time: from the whole hour at or
// before the dose to the whole hour at or after the last sample. Hour
// boundaries make the tick labels land on round times, and anchoring to the
// dose (rather than the mock's fixed 6am-midnight window) means a dose taken
// at 6am and one taken at 2pm are both fully on screen.
export function curveAxis(takenAt, curve) {
  const taken = new Date(takenAt)
  const start = new Date(taken)
  start.setMinutes(0, 0, 0)

  // Rounded *up* to the next whole hour, never down: a dose at 08:20 samples
  // out to 08:20 the next day, and flooring that to 08:00 would push the
  // last twenty minutes of curve off the end of the axis, where timeToX
  // clamps it into a false flat line against the right edge.
  const lastHours = curve?.length ? curve[curve.length - 1].t_h : 1
  const end = new Date(taken.getTime() + lastHours * HOUR_MS)
  if (end.getMinutes() || end.getSeconds() || end.getMilliseconds()) {
    end.setMinutes(0, 0, 0)
    end.setTime(end.getTime() + HOUR_MS)
  }

  return { startMs: start.getTime(), endMs: Math.max(end.getTime(), start.getTime() + HOUR_MS) }
}

// Where a moment in time sits horizontally, in the chart box's own units.
// Times outside the axis clamp to its edges, which is what keeps the NOW
// marker on the chart late in the evening instead of off the right of it.
export function timeToX(ms, axis, box) {
  const fraction = (ms - axis.startMs) / (axis.endMs - axis.startMs)
  return box.x0 + Math.min(1, Math.max(0, fraction)) * (box.x1 - box.x0)
}

// Where a level (0 at the baseline, 1 at this curve's peak) sits vertically.
// y0 is the top of the box, y1 the baseline, since SVG y grows downwards.
export function levelToY(level, box) {
  return box.y1 - Math.min(1, Math.max(0, level)) * (box.y1 - box.y0)
}

// pk's samples as chart points.
export function curveToPoints(curve, takenAt, axis, box) {
  const takenMs = new Date(takenAt).getTime()
  return (curve ?? []).map((sample) => ({
    x: timeToX(takenMs + sample.t_h * HOUR_MS, axis, box),
    y: levelToY(sample.level, box),
  }))
}

// The level at a given moment, interpolated between the two samples either
// side of it -- used to sit the NOW dot on the curve. Returns null before
// the dose or after the last sample, where there is no curve to sit on.
export function levelAt(curve, takenAt, ms) {
  if (!curve?.length) return null
  const hours = (ms - new Date(takenAt).getTime()) / HOUR_MS
  if (hours < curve[0].t_h || hours > curve[curve.length - 1].t_h) return null

  for (let i = 1; i < curve.length; i++) {
    if (curve[i].t_h < hours) continue
    const prev = curve[i - 1]
    const next = curve[i]
    const span = next.t_h - prev.t_h
    if (span <= 0) return next.level
    return prev.level + ((hours - prev.t_h) / span) * (next.level - prev.level)
  }
  return curve[curve.length - 1].level
}

// "6am", "12pm", "9pm" -- the design's axis-label style.
export function formatHourLabel(date) {
  const hours = date.getHours()
  const suffix = hours >= 12 ? 'pm' : 'am'
  return `${hours % 12 || 12}${suffix}`
}

// Tick marks every `stepH` hours across the axis, starting from a whole
// multiple of stepH so the labels stay on familiar times (9am, 12pm, 3pm)
// rather than whatever hour the dose happened to fall on.
export function hourTicks(axis, stepH = 3) {
  const first = new Date(axis.startMs)
  first.setHours(Math.ceil(first.getHours() / stepH) * stepH, 0, 0, 0)

  const ticks = []
  for (let ms = first.getTime(); ms <= axis.endMs; ms += stepH * HOUR_MS) {
    ticks.push({ ms, label: formatHourLabel(new Date(ms)) })
  }
  return ticks
}

// A miniature of the same curve for the Medications list, drawn in its own
// `w` by `h` box with `pad` of vertical margin so the peak doesn't touch the
// top edge. Same pk samples as the full chart -- just smaller.
export function sparkPathFromCurve(curve, w, h, pad) {
  if (!curve?.length) return ''
  const lastHours = curve[curve.length - 1].t_h || 1
  const points = curve.map((sample) => ({
    x: (sample.t_h / lastHours) * w,
    y: h - pad - Math.min(1, Math.max(0, sample.level)) * (h - pad * 2),
  }))
  return pathFromPoints(points)
}
