// Builds the "release timeline" shown on the Today page, anchored to the
// real time a dose was taken.
//
// NOTE: the offsets below are generic placeholders, not per-medication
// pharmacokinetics — there's no dose-duration data in the backend yet (see
// the "pk service" TODO in curve.js). Once that exists, swap this out for a
// per-medication calculation instead of these fixed offsets.
const MILESTONE_OFFSETS_MIN = [
  { label: 'Should start to feel it', offsetMin: 72 },
  { label: 'First peak', offsetMin: 150 },
  { label: 'Second release', offsetMin: 345 },
  { label: 'Starting to fade', offsetMin: 560 },
  { label: 'Largely worn off', offsetMin: 730 },
]

// Total minutes the timeline covers, from "Taken" to the last milestone. The
// Today page uses this to size its linear time axis.
export const TIMELINE_SPAN_MIN = MILESTONE_OFFSETS_MIN[MILESTONE_OFFSETS_MIN.length - 1].offsetMin

// Formats a Date as the design's "8:12 am" style clock time.
export function formatClockTime(date) {
  let hours = date.getHours()
  const minutes = date.getMinutes()
  const suffix = hours >= 12 ? 'pm' : 'am'
  hours = hours % 12 || 12
  return `${hours}:${String(minutes).padStart(2, '0')} ${suffix}`
}

// Formats a Date as "Sunday, September 7", used by both Today sub-views.
export function formatLongDate(date = new Date()) {
  return date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
}

// Returns the [{ time, label, state, offsetMin }] list TodayTimeline.vue
// renders: "Taken" at takenAt, then each milestone above, each marked 'past'
// or 'future' by comparing its clock time against `now`. `offsetMin` is how
// many minutes after the dose the step happens — the Today page multiplies it
// by a px-per-minute scale to place the row on its linear time axis.
export function buildTimelineSteps(takenAt, now) {
  const taken = new Date(takenAt)
  const steps = [{ time: formatClockTime(taken), label: 'Taken', state: 'past', offsetMin: 0 }]

  for (const { label, offsetMin } of MILESTONE_OFFSETS_MIN) {
    const at = new Date(taken.getTime() + offsetMin * 60_000)
    steps.push({
      time: formatClockTime(at),
      label,
      state: at <= now ? 'past' : 'future',
      offsetMin,
    })
  }

  return steps
}

// Minutes since the dose was taken, clamped to the timeline's span. The
// clamp keeps the NOW marker on the axis: pinned to the top if the taken
// time is in the future, and to the bottom once the dose has worn off.
export function elapsedMinutes(takenAt, now) {
  const elapsed = (now - new Date(takenAt)) / 60_000
  return Math.min(TIMELINE_SPAN_MIN, Math.max(0, elapsed))
}
