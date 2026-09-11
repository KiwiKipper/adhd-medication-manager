<script setup>
// The day-curve page (step 8 of web/steps.md): today's dose drawn as the
// release curve pk computed for it, on a real clock-time axis.
//
// Everything shaped here comes from the pk service via fetchTimeline() --
// the sampled curve, and the labelled events marked along it. This page only
// scales those numbers into the chart box (see lib/curve.js) and says, in
// words, what they are: a model of an average response, not a measurement.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchDoses, fetchMyMedication, fetchTimeline } from '@/api.js'
import {
  curveAxis, curveToPoints, hourTicks, levelAt, levelToY, pathFromPoints, timeToX,
} from '@/lib/curve.js'
import { formatClockTime, formatLongDate } from '@/lib/timeline.js'

// The chart's own coordinate space, matching the design mock's proportions.
// The SVG scales to fit whatever room the page gives it, so these are
// aspect-ratio units rather than pixels.
const VIEW_W = 1500
const VIEW_H = 560
const BOX = { x0: 50, x1: 1470, y0: 30, y1: 480 }

// pk's event labels are sentences ("Should start to feel it"); above a
// marker line there's only room for a couple of words. Anything not in this
// map falls back to pk's own wording rather than being dropped.
const SHORT_LABELS = {
  'Taken': 'Taken',
  'Should start to feel it': 'Feel it',
  'First peak': 'Peak 1',
  'Second release': '2nd release',
  'Starting to fade': 'Fading',
  'Largely worn off': 'Worn off',
}

const loading = ref(true)
const error = ref(null)
const medication = ref(null) // the catalogue row, or null if none is selected
const takenAt = ref(null) // today's dose time, or null if none is logged
const curve = ref([])
const events = ref([])

const todayLabel = formatLongDate()

// Ticks once a minute so the NOW marker keeps up with the clock, first tick
// aligned to the next whole minute. Same approach as TodayTimeline.vue.
const now = ref(new Date())
let firstTickTimeout
let nowTimer
onMounted(() => {
  firstTickTimeout = setTimeout(() => {
    now.value = new Date()
    nowTimer = setInterval(() => { now.value = new Date() }, 60_000)
  }, 60_000 - (Date.now() % 60_000))
})
onUnmounted(() => {
  clearTimeout(firstTickTimeout)
  clearInterval(nowTimer)
})

onMounted(async () => {
  try {
    const [{ medication: selected }, todayDoses] = await Promise.all([
      fetchMyMedication(),
      fetchDoses('today'),
    ])
    medication.value = selected
    takenAt.value = todayDoses[0]?.taken_at ?? null

    // Both of those missing are ordinary states with their own message
    // below, not errors -- and neither leaves pk anything to compute.
    if (!selected || !takenAt.value) return

    const timeline = await fetchTimeline(takenAt.value)
    curve.value = timeline.curve
    events.value = timeline.events
  } catch (err) {
    error.value = "Couldn't load today's curve."
  } finally {
    loading.value = false
  }
})

const hasCurve = computed(() => curve.value.length > 0)

const axis = computed(() => curveAxis(takenAt.value, curve.value))
const curvePath = computed(
  () => pathFromPoints(curveToPoints(curve.value, takenAt.value, axis.value, BOX))
)
const ticks = computed(
  () => hourTicks(axis.value).map((tick) => ({ ...tick, x: timeToX(tick.ms, axis.value, BOX) }))
)

const eventMarks = computed(() =>
  events.value.map((event) => ({
    x: timeToX(new Date(event.at).getTime(), axis.value, BOX),
    label: SHORT_LABELS[event.label] ?? event.label,
    title: `${event.label} — ${formatClockTime(new Date(event.at))}`,
  }))
)

const nowX = computed(() => timeToX(now.value.getTime(), axis.value, BOX))
// Null before the dose and after the curve's last sample, where there is no
// curve for the marker's dot to sit on -- the line is still drawn, the dot
// isn't.
const nowLevel = computed(() => levelAt(curve.value, takenAt.value, now.value.getTime()))
const nowY = computed(() => (nowLevel.value === null ? null : levelToY(nowLevel.value, BOX)))
const nowLabel = computed(() => `now ${formatClockTime(now.value)}`)

const takenLabel = computed(
  () => (takenAt.value ? `taken ${formatClockTime(new Date(takenAt.value))}` : '')
)
</script>

<template>
  <div v-if="loading" class="curve-status">Loading…</div>
  <div v-else-if="error" class="curve-status">{{ error }}</div>

  <div v-else-if="!medication" class="curve-status">
    <p>No medication selected yet.</p>
    <router-link to="/medications">Choose a medication</router-link>
  </div>

  <div v-else-if="!takenAt" class="curve-status">
    <p>No dose logged today, so there's no curve to draw yet.</p>
    <router-link to="/today">Log today's dose</router-link>
  </div>

  <div v-else class="curve-page">
    <div class="header-row">
      <div>
        <div class="med-name">{{ medication.name }}</div>
        <div class="taken-time">{{ takenLabel }}</div>
      </div>
      <span class="date-label">{{ todayLabel }}</span>
    </div>

    <div class="chart-area">
      <!-- One SVG scaled to the page rather than a chart library: the shape
           is a path pk already computed, and everything else on it is two
           axes, some tick text and a marker line. -->
      <svg :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`" width="100%" height="100%" class="chart-svg">
        <!-- Axes, with the 50% guide the design mock puts behind the curve. -->
        <line :x1="BOX.x0" :y1="BOX.y0" :x2="BOX.x0" :y2="BOX.y1" class="axis-line" />
        <line :x1="BOX.x0" :y1="BOX.y1" :x2="BOX.x1" :y2="BOX.y1" class="axis-line" />
        <line
          :x1="BOX.x0" :y1="(BOX.y0 + BOX.y1) / 2"
          :x2="BOX.x1" :y2="(BOX.y0 + BOX.y1) / 2"
          class="guide-line"
        />

        <!-- Percentages are of this curve's own peak, which is what pk's
             `level` is -- hence "of peak" on the axis, not a concentration. -->
        <text x="8" :y="BOX.y1 + 4" class="axis-text">0%</text>
        <text x="8" :y="(BOX.y0 + BOX.y1) / 2 + 4" class="axis-text">50%</text>
        <text x="8" :y="BOX.y0 + 6" class="axis-text">100%</text>
        <text x="8" :y="BOX.y0 - 14" class="axis-caption">of peak</text>

        <text
          v-for="tick in ticks"
          :key="tick.ms"
          :x="tick.x"
          :y="BOX.y1 + 28"
          text-anchor="middle"
          class="tick-text"
        >{{ tick.label }}</text>

        <path :d="curvePath" class="curve-path" />

        <!-- pk's milestones, marked where they fall on the same axis. -->
        <g v-for="mark in eventMarks" :key="mark.title">
          <title>{{ mark.title }}</title>
          <line :x1="mark.x" :y1="BOX.y0" :x2="mark.x" :y2="BOX.y1" class="event-line" />
          <text :x="mark.x" :y="BOX.y0 - 12" text-anchor="middle" class="event-text">
            {{ mark.label }}
          </text>
        </g>

        <!-- NOW: a full-height line, a dot on the curve where one exists,
             and the clock time in a badge under the axis. -->
        <line :x1="nowX" :y1="BOX.y0" :x2="nowX" :y2="BOX.y1" class="now-line" />
        <circle v-if="nowY !== null" :cx="nowX" :cy="nowY" r="6.5" class="now-dot" />
        <rect :x="nowX - 60" :y="BOX.y1 + 40" width="120" height="26" rx="7" class="now-badge" />
        <text :x="nowX" :y="BOX.y1 + 57.5" text-anchor="middle" class="now-badge-text">
          {{ nowLabel }}
        </text>
      </svg>

      <p v-if="!hasCurve" class="chart-empty">pk returned no samples for this dose.</p>
    </div>

    <!-- The honesty line. This is a modelled curve for an average response to
         a published dose, positioned against the time the user logged -- it
         is not a measurement of them, and the milestones above are model
         output, not observations. -->
    <p class="chart-caption">
      Modelled release curve for {{ medication.name }}, drawn from published pharmacokinetic
      parameters and anchored to the time you logged. It predicts an average response, not
      yours — and the milestones above it are predictions too, not measurements.
    </p>
    <p v-if="!medication.source" class="chart-provenance">
      This medication's curve parameters haven't been checked against a published source yet.
    </p>
    <p v-else class="chart-provenance">{{ medication.source }}</p>
  </div>
</template>

<style scoped>
.curve-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 100vh;
  font: 400 15px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.curve-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 8px 16px 24px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.med-name {
  font: 600 22px 'Inter', sans-serif;
  color: var(--fg);
}

.taken-time {
  font: 400 14px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
  margin-top: 2px;
}

.date-label {
  font: 500 14px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

/* The chart takes whatever vertical room is left over; min-height: 0 lets it
   shrink on a short window instead of pushing the caption off the page. */
.chart-area {
  flex: 1;
  min-height: 0;
  margin-top: 14px;
  position: relative;
}

.chart-svg {
  display: block;
  /* The event labels sit just above the plot box, so they'd be clipped by a
     tight viewBox without this. */
  overflow: visible;
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  font: 400 14px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.axis-line {
  stroke: var(--border);
  stroke-width: 1;
}

.guide-line {
  stroke: var(--border);
  stroke-width: 1;
  stroke-dasharray: 2 5;
}

.axis-text,
.tick-text {
  font: 400 13px ui-monospace, Menlo, monospace;
  fill: var(--fg-muted);
}

.axis-caption {
  font: 400 12px 'Inter', sans-serif;
  fill: var(--fg-muted);
}

.curve-path {
  fill: none;
  stroke: var(--accent);
  stroke-width: 3.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.event-line {
  stroke: var(--fg-muted);
  stroke-width: 1;
  stroke-dasharray: 2 5;
  opacity: 0.5;
}

.event-text {
  font: 400 12.5px ui-monospace, Menlo, monospace;
  fill: var(--fg-muted);
}

.now-line {
  stroke: var(--fg);
  stroke-width: 2;
}

.now-dot {
  fill: var(--fg);
}

.now-badge {
  fill: var(--fg);
}

.now-badge-text {
  font: 600 13px ui-monospace, Menlo, monospace;
  fill: var(--bg);
}

/* Nudges the whole marker as the minute ticks over, rather than snapping. */
.now-line,
.now-dot,
.now-badge,
.now-badge-text {
  transition: x 0.4s ease, cx 0.4s ease, x1 0.4s ease, x2 0.4s ease;
}

.chart-caption {
  margin: 18px 0 0;
  max-width: 900px;
  font: 400 14px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
}

.chart-provenance {
  margin: 6px 0 0;
  max-width: 900px;
  font: 400 13px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
}
</style>
