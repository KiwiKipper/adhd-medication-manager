<script setup>
// Shown on the Today page once a dose has been logged for the day. Renders
// the release timeline, the notes list, and the last-10-days glance — all
// from real data passed in / fetched here, replacing the old
// lib/placeholderData.js-backed version.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchNotes, addNote as addNoteApi, logDose } from '@/api.js'
import { buildTimelineSteps, elapsedMinutes, TIMELINE_SPAN_MIN, formatClockTime, formatLongDate } from '@/lib/timeline.js'
import { statusLabel } from '@/lib/doseHistory.js'

const props = defineProps({
  dose: { type: Object, required: true }, // today's Dose row from the API
  historyRows: { type: Array, required: true },
})
const emit = defineEmits(['dose-updated', 'dose-reset'])

const takenAt = computed(() => new Date(props.dose.taken_at))
const loggedAt = computed(() => new Date(props.dose.updated_at))
// How long after taking it the dose was actually logged/edited — only
// interesting (and only shown) when it's more than a minute or so; hitting
// "Take dose" logs both at once, so this is normally 0.
const loggedDelayMin = computed(() => Math.round((loggedAt.value - takenAt.value) / 60_000))

const todayLabel = formatLongDate()

// Ticks once a minute so the NOW marker and past/future states stay live
// without the user having to refresh. The first tick is delayed to the next
// whole minute, so the badge's clock time flips exactly on the minute rather
// than drifting by however long ago the page happened to load.
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

const timeline = computed(() => buildTimelineSteps(props.dose.taken_at, now.value))

// The timeline is a linear time axis: every row sits at its true distance
// from the dose, scaled by this many pixels per minute, and the NOW marker
// creeps down at the same rate. Change this one number to rescale the whole
// thing (the axis ends up TIMELINE_SPAN_MIN * PX_PER_MIN tall).
//
// At 0.5 the full ~12h span is about 365px. Don't raise it much further
// without checking the tightest gap — "Taken" to "Should start to feel it"
// is only 72 minutes, and each row needs ~32px for its two lines of text.
const PX_PER_MIN = 0.5

// How far down the axis "now" is, in px.
const nowPx = computed(() => elapsedMinutes(props.dose.taken_at, now.value) * PX_PER_MIN)
const nowLabel = computed(() => `NOW · ${formatClockTime(now.value)}`)

// --- Editing today's taken time -------------------------------------------
const editing = ref(false)
const editTime = ref('')
const savingEdit = ref(false)

function startEdit() {
  const t = takenAt.value
  editTime.value = `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
  editing.value = true
}

async function saveEdit() {
  if (!editTime.value) return
  savingEdit.value = true
  try {
    const isoTakenAt = new Date(`${props.dose.date}T${editTime.value}:00`).toISOString()
    const updated = await logDose(isoTakenAt)
    emit('dose-updated', updated)
    editing.value = false
  } finally {
    savingEdit.value = false
  }
}

// --- Notes -----------------------------------------------------------------
const notes = ref([])
onMounted(async () => {
  notes.value = await fetchNotes()
})
const noteInput = ref('')

async function addNote() {
  const text = noteInput.value.trim()
  if (!text) return
  noteInput.value = ''
  const note = await addNoteApi(text)
  notes.value = [note, ...notes.value]
}

// --- Reset today's log ------------------------------------------------------
function resetLog() {
  if (!window.confirm("Delete today's logged dose and start over?")) return
  emit('dose-reset')
}
</script>

<template>
  <div class="today-page">
    <!-- Left/center column: today's dose header and the release timeline. -->
    <div class="main-col">
      <div class="content-inner">
        <div class="header-row">
          <div class="header-left">
            <span class="taken-time">Taken at {{ formatClockTime(takenAt) }}</span>
            <template v-if="!editing">
              <span class="edit-icon" role="button" aria-label="Edit" @click="startEdit">✎</span>
            </template>
            <template v-else>
              <input v-model="editTime" type="time" class="edit-time-input" />
              <button type="button" class="edit-save-btn" :disabled="savingEdit" @click="saveEdit">Save</button>
              <button type="button" class="edit-cancel-btn" @click="editing = false">Cancel</button>
            </template>
          </div>
        </div>

        <div v-if="loggedDelayMin > 0" class="logged-flag">
          <span class="flag-dot"></span>
          <span class="flag-text">Logged at {{ formatClockTime(loggedAt) }} · {{ loggedDelayMin }} min after taking</span>
        </div>

        <!-- The milestones ("Taken", "First peak", ...) on a linear time
             axis: the canvas is one pixel tall per minute of the dose, and
             every row is absolutely positioned at its own offset, so the
             gaps between rows match the real gaps in time. The NOW marker
             is placed the same way and creeps down a pixel a minute.
             `v-for` repeats the row block once per step; `:key` gives Vue a
             stable id per row so it can track items efficiently. -->
        <div class="timeline-col">
          <div class="timeline-canvas" :style="{ height: TIMELINE_SPAN_MIN * PX_PER_MIN + 'px' }">
            <!-- One continuous rail behind the dots, with the elapsed part
                 of it filled in on top, down to the NOW position. -->
            <span class="rail-track"></span>
            <span class="rail-elapsed" :style="{ height: nowPx + 'px' }"></span>

            <div
              v-for="step in timeline"
              :key="step.time"
              class="timeline-item"
              :class="step.state"
              :style="{ top: step.offsetMin * PX_PER_MIN + 'px' }"
            >
              <span class="timeline-marker"><span class="timeline-dot"></span></span>
              <div class="timeline-body">
                <div class="timeline-time">{{ step.time }}</div>
                <div class="timeline-label">{{ step.label }}</div>
              </div>
            </div>

            <!-- NOW marker: just a line and a badge, living in the empty
                 space to the right of the labels so it never crosses any
                 text, however close to a row it happens to sit. -->
            <div class="now-overlay" :style="{ top: nowPx + 'px' }">
              <span class="now-line"></span>
              <span class="now-badge">{{ nowLabel }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right sidebar: today's notes (with the add-note form) and a quick
         10-day history glance. Separate from the app-wide nav sidebar in
         UserNav.vue — this one is specific to the Today page. -->
    <div class="notes-col">
      <div class="info-section">
        <div class="section-title">Information</div>
        <div class="info-med">{{ dose.medication_name }}</div>
        <div class="info-date">{{ todayLabel }}</div>
        <button type="button" class="reset-btn" @click="resetLog">Reset today's log</button>
      </div>

      <div class="notes-section">
        <div class="section-title">Notes</div>
        <div class="notes-list">
          <div v-for="note in notes" :key="note.id" class="note-row">
            <span class="note-time">{{ formatClockTime(new Date(note.created_at)) }}</span>
            <span class="note-text">"{{ note.text }}"</span>
          </div>
        </div>
        <!-- @submit.prevent calls addNote() and stops the browser's default
             full-page-reload form submission. -->
        <form class="note-add-row" @submit.prevent="addNote">
          <input v-model="noteInput" placeholder="Add a note" />
          <button type="submit">Add</button>
        </form>
      </div>

      <div class="history-section">
        <div class="section-title">Last 10 days</div>
        <div class="history-list">
          <div v-for="(d, i) in historyRows" :key="i" class="history-row">
            <div class="history-date">{{ d.date }}</div>
            <div class="history-time">{{ d.doseTime }}</div>
            <!-- `:class="d.status"` adds a class named e.g. "on-time" or "missed",
                 which the <style> block below uses to color the pill. -->
            <div class="history-status" :class="d.status">{{ statusLabel(d.status) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.today-page {
  display: flex;
  min-height: 100vh;
}

.main-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 40px;
  overflow: hidden;
}

.content-inner {
  width: 75%;
  max-width: 980px;
  display: flex;
  flex-direction: column;
  /* flex: 1 + min-height: 0 give this a real height to divide up, which is
     what lets .timeline-col below scroll its own overflow instead of the
     axis being clipped by .main-col on a short window. */
  flex: 1;
  min-height: 0;
}

.header-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 22px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.taken-time {
  flex: none;
  white-space: nowrap;
  font: 600 26px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.edit-icon {
  flex: none;
  cursor: pointer;
  font-size: 17px;
  color: var(--fg-muted);
}

.edit-time-input {
  flex: none;
  font: 500 14px ui-monospace, Menlo, monospace;
  color: var(--fg);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 2px 6px;
}

.edit-save-btn,
.edit-cancel-btn {
  flex: none;
  font: 600 12px 'Inter', sans-serif;
  border: none;
  border-radius: 6px;
  padding: 5px 10px;
  cursor: pointer;
}

.edit-save-btn {
  background: var(--accent);
  color: var(--accent-contrast);
}

.edit-cancel-btn {
  background: var(--surface);
  color: var(--fg-muted);
  border: 1px solid var(--border);
}

.logged-flag {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 22px;
}

.flag-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--flag);
  flex: none;
}

.flag-text {
  font: 500 12.5px/1 'Inter', sans-serif;
  color: var(--flag);
}

.timeline-col {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  /* Headroom for the half of the NOW badge (and of the first dot) that sits
     above the top of the axis when no time has elapsed yet. */
  padding-top: 18px;
}

/* The time axis everything inside is positioned against. Its height comes
   from an inline style (span in minutes x px-per-minute), so a row's `top`
   in px is simply its offset in minutes. */
.timeline-canvas {
  position: relative;
  /* Never let the scroll container squash the axis — its height is the
     scale, so it has to stay exactly as tall as the inline style says. A
     margin (not padding) keeps the last row's two lines of text clear of
     the bottom without eating into that height. */
  flex: none;
  margin-bottom: 40px;

  --rail-width: 14px; /* wide enough for the biggest dot */
  --rail-gap: 14px; /* space between the rail and the label text */
  --label-left: calc(var(--rail-width) + var(--rail-gap));
  --label-col-width: 200px; /* wider than the longest label; the NOW line starts after it */
}

.rail-track,
.rail-elapsed {
  position: absolute;
  /* Centred in the rail column, so the dots sit on top of it. */
  left: calc(var(--rail-width) / 2 - 1px);
  top: 0;
  width: 2px;
}

.rail-track {
  bottom: 0;
  background: var(--border);
}

/* The elapsed part of the rail, drawn over the grey track. Its height is
   set inline from the NOW position, so it grows as the day goes on. */
.rail-elapsed {
  background: var(--accent);
}

/* Each milestone, placed by inline `top` at its own minute offset. */
.timeline-item {
  position: absolute;
  left: 0;
  right: 0;
  display: flex;
  align-items: flex-start;
  gap: var(--rail-gap);
}

/* A fixed-width, zero-height slot for the row's dot. Centring inside a box
   with no height puts the dot's middle exactly on the row's time, whatever
   size the dot is, and the fixed width keeps every label starting at the
   same x. */
.timeline-marker {
  position: relative; /* with z-index, draws over the rail */
  z-index: 1;
  flex: none;
  width: var(--rail-width);
  height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
}

.timeline-item.future .timeline-dot {
  background: var(--bg);
  border: 1.5px solid var(--border);
  width: 7px;
  height: 7px;
}

/* Lifts the time text so it reads as level with the dot beside it. */
.timeline-body {
  margin-top: -8px;
}

/* The NOW line and badge. Sits to the right of the label column so it can
   never overlap a row's text, and is centred on its exact minute. */
.now-overlay {
  position: absolute;
  left: calc(var(--label-left) + var(--label-col-width));
  right: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  /* No gap: the line runs right up to the badge so the two read as one
     marker. */
  transform: translateY(-50%);
}

/* Small easing so the once-a-minute step, and bigger jumps when the taken
   time is edited, glide instead of snapping. */
.now-overlay,
.rail-elapsed {
  transition: top 0.4s ease, height 0.4s ease;
}

.now-line {
  flex: 1;
  height: 2px;
  background: var(--fg);
}

.now-badge {
  flex: none;
  background: var(--fg);
  color: var(--bg);
  border-radius: 6px;
  padding: 5px 12px;
  font: 600 11.5px ui-monospace, Menlo, monospace;
  white-space: nowrap;
}

.timeline-time {
  font: 600 13.5px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.timeline-item.future .timeline-time {
  color: var(--fg-muted);
}

.timeline-label {
  font: 400 12.5px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.notes-col {
  flex: none;
  width: 340px;
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 32px 26px;
  gap: 26px;
  overflow-y: auto;
  overflow-x: hidden;
}

.section-title {
  font: 600 14px 'Inter', sans-serif;
  color: var(--fg);
  margin-bottom: 12px;
}

.info-med {
  font: 500 13px 'Inter', sans-serif;
  color: var(--fg);
}

.info-date {
  font: 500 12px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
  margin-top: 4px;
}

.reset-btn {
  margin-top: 14px;
  background: var(--flag-soft);
  color: var(--flag);
  border: 1px solid var(--flag);
  border-radius: 9px;
  padding: 8px 14px;
  font: 600 13px 'Inter', sans-serif;
  cursor: pointer;
}

.notes-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.note-row {
  display: flex;
  gap: 12px;
  background: var(--accent-soft);
  border-radius: 10px;
  padding: 10px 12px;
  /* Flex items default to min-width: auto, which lets an unbroken long word
     (a URL, a run-together word) force the row wider than the sidebar and
     overflow the page. min-width: 0 lets it shrink and wrap instead. */
  min-width: 0;
}

.note-time {
  flex: none;
  width: 44px;
  font: 600 12px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.note-text {
  flex: 1;
  min-width: 0;
  font: 400 13px/1.4 'Inter', sans-serif;
  color: var(--fg);
  overflow-wrap: anywhere;
}

.note-add-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.note-add-row input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--fg);
  outline: none;
}

.note-add-row button {
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 9px;
  padding: 0 14px;
  font: 600 13px 'Inter', sans-serif;
  cursor: pointer;
}

.history-list {
  display: flex;
  flex-direction: column;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.history-date {
  flex: none;
  width: 52px;
  font: 500 12px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.history-time {
  flex: 1;
  font: 400 12.5px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.history-status {
  flex: none;
  padding: 4px 10px;
  border-radius: 20px;
  font: 600 12px 'Inter', sans-serif;
  background: var(--surface);
  color: var(--fg-muted);
}

.history-status.on-time {
  background: var(--accent-soft);
  color: var(--accent);
}

.history-status.edited,
.history-status.late {
  background: var(--flag-soft);
  color: var(--flag);
}
</style>
