// Builds the "release timeline" shown on the Today page, anchored to the real
// time a dose was taken. The milestones themselves ("First peak", "Second
// release", ...) come from the pk module via fetchTimeline() in api.js. This
// file only turns that response into what the page renders: clock strings,
// past/future state, and pixel positions.

// The axis is linear in time: this many pixels per minute since the dose.
// A ~12h span comes out around 365px at 0.5.
export const PX_PER_MIN = 0.5

// Each row is two lines of text, so two rows closer together than this
// overlap and become unreadable. See MIN_ROW_GAP_PX below.
const ROW_HEIGHT_PX = 32

// Minimum vertical distance between two label blocks.
//
// This matters because pk's real events cluster hard at the start of the
// curve. Every seeded medication puts "Taken" and "Should start to feel it"
// 10-50 minutes apart, which at 0.5px/min is 5-25px -- well under the 32px a
// row needs, so the text used to render on top of itself. (The placeholder
// offsets this page shipped with before it was wired to pk were spaced 72
// minutes apart at the tightest, which is why the problem only appeared once
// the numbers became real.)
//
// So label blocks get pushed apart to at least this gap while the dots stay
// on their true minute -- see buildTimelineSteps.
const MIN_ROW_GAP_PX = 36

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

// Turns pk's `events` ([{ at, label }], chronological, "Taken" first) into the
// list TodayTimeline.vue renders.
//
// Each step carries three positions, and the difference between them is the
// point: `offsetMin` is the true minutes after the dose, `topPx` is where the
// label block actually goes after rows have been pushed apart, and
// `dotOffsetPx` is how far back up the marker has to sit to land on its true
// minute again. So the dots stay honest to the clock even where the labels
// beside them have been spread out to stay legible.
export function buildTimelineSteps(takenAt, now, events) {
  const taken = new Date(takenAt)
  let previousTopPx = null

  return (events ?? []).map((event) => {
    const at = new Date(event.at)
    const offsetMin = (at - taken) / 60_000
    const truePx = offsetMin * PX_PER_MIN
    // Walking in order, each row lands at its true position or is pushed down
    // to clear the one above, whichever is lower.
    const topPx = previousTopPx === null
      ? truePx
      : Math.max(truePx, previousTopPx + MIN_ROW_GAP_PX)
    previousTopPx = topPx

    return {
      time: formatClockTime(at),
      label: event.label,
      state: at <= now ? 'past' : 'future',
      offsetMin,
      topPx,
      dotOffsetPx: truePx - topPx, // <= 0: the dot sits at or above its label
    }
  })
}

// How tall the canvas has to be. Normally the span from "Taken" to the last
// event, but a run of pushed-apart rows can reach further down than that, and
// the last row must not end up outside the box.
export function timelineCanvasHeight(steps, spanMin) {
  const lastTopPx = steps.length ? steps[steps.length - 1].topPx : 0
  return Math.max(spanMin * PX_PER_MIN, lastTopPx)
}

// Total minutes the timeline covers, from "Taken" to its last event. Falls
// back to an hour so the axis still renders while events are loading, and for
// the rare curve that never reaches "Should start to feel it" inside the
// sampled window (where pk returns only the "Taken" event).
const MIN_SPAN_MIN = 60

export function timelineSpanMinutes(events) {
  if (!events || events.length < 2) return MIN_SPAN_MIN
  const takenAt = new Date(events[0].at)
  const lastAt = new Date(events[events.length - 1].at)
  return Math.max(MIN_SPAN_MIN, (lastAt - takenAt) / 60_000)
}

// Minutes since the dose was taken, clamped to the timeline's span. The clamp
// keeps the NOW marker on the axis: pinned to the top if the taken time is in
// the future, and to the bottom once the dose has worn off.
export function elapsedMinutes(takenAt, now, spanMin) {
  const elapsed = (now - new Date(takenAt)) / 60_000
  return Math.min(spanMin, Math.max(0, elapsed))
}
