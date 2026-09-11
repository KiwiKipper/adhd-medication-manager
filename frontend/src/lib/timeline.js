// Builds the "release timeline" shown on the Today page, anchored to the
// real time a dose was taken. The milestones themselves ("First peak",
// "Second release", ...) come from the pk module via fetchTimeline() in
// api.js -- this file only turns that response into what the page renders
// (clock strings, past/future state, pixel offsets), matching whatever
// events pk actually returned rather than a fixed medication-agnostic list.

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

// Turns pk's `events` ([{ at, label }], chronological, "Taken" first) into
// the [{ time, label, state, offsetMin }] list TodayTimeline.vue renders.
// `state` is 'past' or 'future', by comparing each event's real timestamp
// against `now`. `offsetMin` is how many minutes after the dose the step
// happens -- the Today page multiplies it by a px-per-minute scale to place
// the row on its linear time axis.
export function buildTimelineSteps(takenAt, now, events) {
  const taken = new Date(takenAt)
  return (events ?? []).map((event) => {
    const at = new Date(event.at)
    return {
      time: formatClockTime(at),
      label: event.label,
      state: at <= now ? 'past' : 'future',
      offsetMin: (at - taken) / 60_000,
    }
  })
}

// Total minutes the timeline covers, from "Taken" to its last event -- the
// Today page uses this to size its linear time axis. Falls back to an hour
// so the axis still renders something while events haven't loaded yet, or
// for the rare curve that never even reaches "Should start to feel it"
// within the sampled window (so pk returns only the "Taken" event).
const MIN_SPAN_MIN = 60

export function timelineSpanMinutes(events) {
  if (!events || events.length < 2) return MIN_SPAN_MIN
  const takenAt = new Date(events[0].at)
  const lastAt = new Date(events[events.length - 1].at)
  return Math.max(MIN_SPAN_MIN, (lastAt - takenAt) / 60_000)
}

// Minutes since the dose was taken, clamped to the timeline's span. The
// clamp keeps the NOW marker on the axis: pinned to the top if the taken
// time is in the future, and to the bottom once the dose has worn off.
export function elapsedMinutes(takenAt, now, spanMin) {
  const elapsed = (now - new Date(takenAt)) / 60_000
  return Math.min(spanMin, Math.max(0, elapsed))
}
