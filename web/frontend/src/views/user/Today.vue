<script setup>
// <script setup> is Vue 3 shorthand: anything declared at the top level here
// (variables, functions, imports) is automatically available to the <template>
// below, with no separate "export default { data(){...} }" boilerplate needed.
import { ref, computed } from 'vue'
import { HISTORY_SEED, STATUS_LABELS, TODAY_TIMELINE } from '@/lib/placeholderData.js'

// Plain object, not `ref()`. It never changes after the component loads, so it
// doesn't need to be reactive — Vue only needs to track values that can change
// while the page is open (see `notes`/`noteInput` below for the contrast).
// TODO: placeholder — will come from the dose-log API once it exists.
const dose = {
  medName: 'Concerta 36mg',
  takenAt: '8:00 am',
  loggedAt: '8:12 am',
  loggedDelayMin: 12,
  date: 'Sunday, September 7',
}

// Imported straight from placeholderData.js so the same timeline shape can be
// reused by other pages later (History, Curve) without copy-pasting it.
const timeline = TODAY_TIMELINE

// `ref()` wraps a value so Vue can detect changes to it and re-render the
// template automatically. `notes.value` is how you read/write it in the
// <script> block; in the <template> Vue unwraps it for you, so it's just `notes`.
const notes = ref([
  { time: '10:05', text: "couldn't start anything until 10", flagged: false },
  { time: '4:15', text: 'crashed hard at 4', flagged: true },
])
// Bound to the text input below via `v-model="noteInput"` — typing in the
// input updates this ref, and this ref updates the input, automatically.
const noteInput = ref('')

// Called by the form's @submit.prevent handler further down.
function addNote() {
  const text = noteInput.value.trim()
  if (!text) return
  notes.value.push({ time: 'just now', text, flagged: false })
  noteInput.value = ''
}

// `computed()` caches a derived value and only recalculates it when something
// it reads from (HISTORY_SEED, here) changes. Used instead of a plain
// variable so the template can reference `last10Days` reactively.
const last10Days = computed(() => HISTORY_SEED.slice(0, 10))
// Small helper so the template can show "On time" instead of the raw
// "on-time" status string stored in the data.
const statusLabel = (status) => STATUS_LABELS[status] ?? status
</script>

<template>
  <div class="today-page">
    <!-- Left/center column: today's dose header and the release timeline. -->
    <div class="main-col">
      <!-- "Taken at 8:00 am ✎ — Concerta 36mg" plus today's date, top right. -->
      <div class="header-row">
        <div class="header-left">
          <span class="taken-time">Taken at {{ dose.takenAt }}</span>
          <span class="edit-icon" role="button" aria-label="Edit">✎</span>
          <span class="med-name">— {{ dose.medName }}</span>
        </div>
        <span class="today-date">{{ dose.date }}</span>
      </div>

      <div class="logged-flag">
        <span class="flag-dot"></span>
        <span class="flag-text">Logged at {{ dose.loggedAt }} · {{ dose.loggedDelayMin }} min after taking</span>
      </div>

      <!-- Vertical list of milestones ("Taken", "First peak", ...). `v-for` repeats
           this block once per item in `timeline`; `:key` gives Vue a stable id per
           row so it can track/re-order items efficiently instead of re-rendering
           everything. Each row also draws the dot + connecting line beside it. -->
      <div class="timeline-col">
        <div
          v-for="(step, i) in timeline"
          :key="step.time"
          class="timeline-item"
          :class="step.state"
        >
          <div class="timeline-rail">
            <span class="timeline-dot"></span>
            <!-- No connecting line after the very last item. -->
            <span v-if="i < timeline.length - 1" class="timeline-line"></span>
          </div>
          <div class="timeline-body">
            <div class="timeline-time">{{ step.time }}</div>
            <div class="timeline-label">{{ step.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right sidebar: today's notes (with the add-note form) and a quick
         10-day history glance. Separate from the app-wide nav sidebar in
         UserNav.vue — this one is specific to the Today page. -->
    <div class="notes-col">
      <div class="notes-section">
        <div class="section-title">Notes</div>
        <div class="notes-list">
          <!-- `:key="i"` (the array index) is fine here since notes are only ever
               appended, never reordered/removed — if that changes later, give
               each note a real unique id instead. -->
          <div
            v-for="(note, i) in notes"
            :key="i"
            class="note-row"
            :class="{ flagged: note.flagged }"
          >
            <span class="note-time">{{ note.time }}</span>
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
          <div v-for="d in last10Days" :key="d.date" class="history-row">
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
  padding: 32px 40px;
  overflow: hidden;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 22px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.taken-time {
  font: 600 26px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.edit-icon {
  cursor: pointer;
  font-size: 17px;
  color: var(--fg-muted);
}

.med-name {
  font: 400 17px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.today-date {
  font: 500 14px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
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
  max-width: 520px;
  overflow-y: auto;
}

.timeline-item {
  display: flex;
  gap: 14px;
}

.timeline-rail {
  flex: none;
  width: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
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

.timeline-line {
  flex: 1;
  width: 2px;
  background: var(--border);
  margin-top: 2px;
}

.timeline-body {
  padding-bottom: 20px;
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

.note-row.flagged {
  background: var(--flag-soft);
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
