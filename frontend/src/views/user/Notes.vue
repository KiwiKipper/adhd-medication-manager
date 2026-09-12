<script setup>
// The Notes page: every note the user has written, grouped by the day it is
// *about* rather than the day it was typed (the backend's Note.date, which
// is why a note written at 1am can still belong to the previous day's dose).
//
// The Today page's sidebar only ever shows today; this is where earlier days
// are readable, and where a note can be filed against a past day or flagged.
import { ref, computed, onMounted } from 'vue'
import { fetchNotes, addNote as addNoteApi } from '@/api.js'
import { dowLabel, formatDateLabel } from '@/lib/doseHistory.js'
import { formatClockTime } from '@/lib/timeline.js'

// "2026-09-07" for a local Date, matching the backend's `date` field.
function toIsoDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = toIsoDate(new Date())

const loading = ref(true)
const error = ref(null)
const notes = ref([])

// The add-note form. `date` starts on today, which is what almost every note
// is about; changing it files the note against an earlier day instead.
const noteText = ref('')
const noteDate = ref(today)
const noteFlagged = ref(false)
const saving = ref(false)
const saveError = ref('')

const showFlaggedOnly = ref(false)

onMounted(async () => {
  try {
    notes.value = await fetchNotes()
  } catch (err) {
    error.value = "Couldn't load your notes."
  } finally {
    loading.value = false
  }
})

const visibleNotes = computed(
  () => (showFlaggedOnly.value ? notes.value.filter((n) => n.flagged) : notes.value)
)

const flaggedCount = computed(() => notes.value.filter((n) => n.flagged).length)

// [{ date, label, isToday, notes }], newest day first. The API already
// returns notes ordered by date then creation time, so grouping is a single
// pass -- a Map keeps the days in that order.
const days = computed(() => {
  const byDate = new Map()
  for (const note of visibleNotes.value) {
    if (!byDate.has(note.date)) byDate.set(note.date, [])
    byDate.get(note.date).push(note)
  }
  return [...byDate.entries()].map(([date, dayNotes]) => ({
    date,
    label: `${formatDateLabel(date)} · ${dowLabel(date)}`,
    isToday: date === today,
    notes: dayNotes,
  }))
})

async function submitNote() {
  const text = noteText.value.trim()
  if (!text || saving.value) return

  saving.value = true
  saveError.value = ''
  try {
    const note = await addNoteApi(text, { date: noteDate.value, flagged: noteFlagged.value })
    // Slot it in by date so a note filed against an earlier day lands in
    // that day's group rather than at the top of the page.
    notes.value = [...notes.value, note].sort((a, b) =>
      a.date === b.date
        ? new Date(b.created_at) - new Date(a.created_at)
        : b.date.localeCompare(a.date)
    )
    noteText.value = ''
    noteFlagged.value = false
  } catch (err) {
    saveError.value = "Couldn't save that note. Try again."
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="loading" class="notes-status">Loading…</div>
  <div v-else-if="error" class="notes-status">{{ error }}</div>

  <div v-else class="notes-page">
    <div class="page-header">
      <div class="page-title">Notes</div>
      <div class="page-subtitle">
        How the days actually went, in your words — filed against the day they're about.
      </div>
    </div>

    <!-- @submit.prevent runs submitNote() instead of the browser's default
         full-page-reload form submission. -->
    <form class="note-form" @submit.prevent="submitNote">
      <input
        v-model="noteText"
        class="note-input"
        placeholder="Add a note"
        aria-label="Note"
      />
      <input v-model="noteDate" type="date" class="note-date" aria-label="Day this note is about" />
      <label class="note-flag">
        <input v-model="noteFlagged" type="checkbox" />
        <span>Flag</span>
      </label>
      <button type="submit" class="note-submit" :disabled="saving">Add</button>
    </form>
    <p v-if="saveError" class="note-error" role="alert">{{ saveError }}</p>

    <div class="filter-row">
      <label class="filter-toggle">
        <input v-model="showFlaggedOnly" type="checkbox" />
        <span>Flagged only</span>
      </label>
      <span class="filter-count">
        {{ notes.length }} note{{ notes.length === 1 ? '' : 's' }} · {{ flaggedCount }} flagged
      </span>
    </div>

    <p v-if="!days.length" class="notes-empty">
      {{ showFlaggedOnly ? 'No flagged notes yet.' : 'No notes yet.' }}
    </p>

    <div v-else class="day-list">
      <section v-for="day in days" :key="day.date" class="day-group">
        <div class="day-heading">
          <span class="day-label">{{ day.label }}</span>
          <span v-if="day.isToday" class="day-today">Today</span>
        </div>
        <div class="day-notes">
          <!-- `:class="{ flagged: note.flagged }"` colours the row with the
               same red/orange the "late" pills use elsewhere. -->
          <div
            v-for="note in day.notes"
            :key="note.id"
            class="note-row"
            :class="{ flagged: note.flagged }"
          >
            <span class="note-time">{{ formatClockTime(new Date(note.created_at)) }}</span>
            <span class="note-text">{{ note.text }}</span>
            <span v-if="note.flagged" class="note-flag-dot" aria-label="Flagged">●</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.notes-status {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  font: 400 15px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.notes-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 760px;
  padding: 8px 16px 40px;
}

.page-title {
  font: 600 20px 'Inter', sans-serif;
  color: var(--fg);
  margin-bottom: 6px;
}

.page-subtitle {
  font: 400 14px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.note-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.note-input {
  flex: 1;
  min-width: 220px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--fg);
  outline: none;
}

.note-date {
  flex: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 9px 10px;
  font: 500 13px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.note-flag {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  font: 500 13px 'Inter', sans-serif;
  color: var(--fg-muted);
  cursor: pointer;
}

.note-submit {
  flex: none;
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 9px;
  padding: 10px 16px;
  font: 600 13px 'Inter', sans-serif;
  cursor: pointer;
}

.note-submit:disabled {
  opacity: 0.6;
  cursor: default;
}

.note-error {
  margin: 0;
  padding: 10px 14px;
  border-radius: 9px;
  background: var(--flag-soft);
  color: var(--flag);
  font: 500 13px/1.4 'Inter', sans-serif;
}

.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font: 500 13px 'Inter', sans-serif;
  color: var(--fg-muted);
  cursor: pointer;
}

.filter-count {
  font: 400 12.5px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.notes-empty {
  margin: 0;
  font: 400 14px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.day-list {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.day-heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.day-label {
  font: 600 14px 'Inter', sans-serif;
  color: var(--fg);
}

.day-today {
  font: 600 11px 'Inter', sans-serif;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 20px;
  padding: 3px 9px;
}

.day-notes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.note-row {
  display: flex;
  gap: 12px;
  align-items: baseline;
  background: var(--accent-soft);
  border-radius: 10px;
  padding: 10px 12px;
  /* Lets a long unbroken word wrap instead of widening the row past the
     page (flex items default to min-width: auto). */
  min-width: 0;
}

.note-row.flagged {
  background: var(--flag-soft);
}

.note-time {
  flex: none;
  width: 62px;
  font: 600 12px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.note-text {
  flex: 1;
  min-width: 0;
  font: 400 13px/1.5 'Inter', sans-serif;
  color: var(--fg);
  overflow-wrap: anywhere;
}

.note-flag-dot {
  flex: none;
  font-size: 10px;
  color: var(--flag);
}
</style>
