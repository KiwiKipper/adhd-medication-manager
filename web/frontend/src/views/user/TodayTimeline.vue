<script setup>
// Shown on the Today page once a dose has been logged for the day. Renders
// the release timeline, the notes list, and the last-10-days glance — all
// from real data passed in / fetched here, replacing the old
// lib/placeholderData.js-backed version.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchNotes, addNote as addNoteApi, logDose } from '@/api.js'
import { buildTimelineSteps, formatClockTime, formatLongDate } from '@/lib/timeline.js'
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

// Ticks every 30s so the "NOW" marker and past/future states stay live
// without the user having to refresh the page.
const now = ref(new Date())
let nowTimer
onMounted(() => {
  nowTimer = setInterval(() => { now.value = new Date() }, 30_000)
})
onUnmounted(() => clearInterval(nowTimer))

const timeline = computed(() => buildTimelineSteps(props.dose.taken_at, now.value))

// Splices a `{ now: true }` marker into the timeline at the boundary between
// "past" and "future" steps, so the template can render it as a single rail
// with one `v-for` instead of two separate lists stitched together by hand.
const timelineWithNow = computed(() => {
  const items = []
  let inserted = false
  for (const step of timeline.value) {
    if (!inserted && step.state === 'future') {
      items.push({ now: true, time: `NOW · ${formatClockTime(now.value)}` })
      inserted = true
    }
    items.push(step)
  }
  if (!inserted) items.push({ now: true, time: `NOW · ${formatClockTime(now.value)}` })
  return items
})

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

        <!-- Vertical list of milestones ("Taken", "First peak", ...), with a
             "now" marker spliced in at the past/future boundary (see
             `timelineWithNow`). `v-for` repeats this block once per item;
             `:key` gives Vue a stable id per row so it can track/re-order
             items efficiently instead of re-rendering everything. -->
        <div class="timeline-col">
          <div
            v-for="(step, i) in timelineWithNow"
            :key="step.time"
            class="timeline-item"
            :class="step.now ? 'now' : step.state"
          >
            <div class="timeline-rail">
              <span class="timeline-dot"></span>
              <!-- No connecting line after the very last item. -->
              <span v-if="i < timelineWithNow.length - 1" class="timeline-line"></span>
            </div>
            <!-- The "now" marker gets a horizontal line + badge instead of a
                 time/label pair, matching the design's "NOW · 2:47 pm" cue. -->
            <div v-if="step.now" class="now-row">
              <span class="now-line"></span>
              <span class="now-badge">{{ step.time }}</span>
            </div>
            <div v-else class="timeline-body">
              <div class="timeline-time">{{ step.time }}</div>
              <div class="timeline-label">{{ step.label }}</div>
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
}

.timeline-item {
  display: flex;
  gap: 14px;
}

.timeline-rail {
  flex: none;
  /* Wide enough for the biggest dot (the "now" marker's 14px ring) so it
     never gets clipped against the rail's edge. */
  width: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: visible;
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

/* The "now" marker's dot is bigger and hollow, echoing the design's ring. */
.timeline-item.now .timeline-dot {
  background: var(--bg);
  border: 2px solid var(--fg);
  width: 14px;
  height: 14px;
}

.timeline-line {
  flex: 1;
  width: 2px;
  background: var(--border);
  margin-top: 2px;
}

.timeline-body {
  padding-bottom: 24px;
}

.now-row {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 24px;
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
