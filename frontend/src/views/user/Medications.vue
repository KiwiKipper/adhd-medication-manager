<script setup>
// <script setup> is Vue 3 shorthand: anything declared at the top level here
// (variables, functions, imports) is automatically available to the <template>
// below, with no separate "export default { data(){...} }" boilerplate needed.
//
// The catalogue, its copy and each medication's drug class now all come from
// GET /api/medications/, and the release shape beside a medication is the
// curve pk computes for it (GET /api/timeline/?medication=...), not a
// hand-drawn set of points. lib/placeholderData.js is gone with them.
import { ref, computed, onMounted, watch } from 'vue'
import { sparkPathFromCurve } from '@/lib/curve.js'
import {
  fetchMedications, fetchMyMedication, fetchTimeline, selectMedication, setScheduledTime,
} from '@/api.js'

const loading = ref(true)
const loadError = ref('')
const medications = ref([])

// Two separate ideas, deliberately. `viewingId` is whichever medication's
// details are on screen; `activeId` is the one that's actually yours. They
// used to be a single ref, which meant clicking a row to read about it also
// switched your medication -- so you couldn't compare two without changing
// what every other page classifies your doses against.
const viewingId = ref(null)
const activeId = ref(null)
const saving = ref(false)
const saveError = ref('')

// The daily time doses are compared against. Until this picker existed
// everyone sat on the 8am default, so on-time/late was wrong for anyone who
// doesn't take their dose at 8am.
const scheduledTime = ref('08:00')
const savedScheduledTime = ref('08:00')
const savingTime = ref(false)
const timeError = ref('')
const timeSaved = ref(false)

// The preview curve for whichever medication is selected, from pk.
const curve = ref([])
const curveLoading = ref(false)
const curveError = ref('')

onMounted(async () => {
  try {
    const [catalogue, mine] = await Promise.all([fetchMedications(), fetchMyMedication()])
    medications.value = catalogue
    activeId.value = mine.medication?.id ?? null
    // Someone who hasn't picked a medication yet still opens on something
    // readable, rather than an empty detail panel.
    viewingId.value = activeId.value ?? catalogue[0]?.id ?? null
    if (mine.scheduled_time) {
      scheduledTime.value = mine.scheduled_time
      savedScheduledTime.value = mine.scheduled_time
    }
  } catch (err) {
    loadError.value = "Couldn't load the medication list."
  } finally {
    loading.value = false
  }
})

// Looked up whenever `viewingId` changes; `computed()` caches the result and
// only recalculates when something it reads changes.
const viewedMed = computed(
  () => medications.value.find((m) => m.id === viewingId.value) ?? null
)

// Is the medication on screen the one that's actually yours?
const viewingIsActive = computed(
  () => viewingId.value !== null && viewingId.value === activeId.value
)

// Reading only. No API call, so browsing the catalogue costs nothing and
// changes nothing.
function viewMed(id) {
  viewingId.value = id
  saveError.value = ''
}

// The explicit commit: makes the medication you're reading the one that's
// yours. Rolls back on failure so the page can't claim a selection the server
// didn't accept.
async function confirmSelection() {
  if (viewingId.value === null || saving.value) return
  const previous = activeId.value
  saveError.value = ''
  saving.value = true
  try {
    await selectMedication(viewingId.value)
    activeId.value = viewingId.value
  } catch {
    activeId.value = previous
    saveError.value = 'Could not save your selection. Try again.'
  } finally {
    saving.value = false
  }
}

async function saveScheduledTime() {
  if (!scheduledTime.value || savingTime.value) return
  timeError.value = ''
  timeSaved.value = false
  savingTime.value = true
  try {
    const result = await setScheduledTime(scheduledTime.value)
    savedScheduledTime.value = result.scheduled_time
    scheduledTime.value = result.scheduled_time
    timeSaved.value = true
  } catch {
    scheduledTime.value = savedScheduledTime.value
    timeError.value = 'Could not save that time. Try again.'
  } finally {
    savingTime.value = false
  }
}

// The release shape: pk's curve for this medication, asked for at the user's
// own scheduled time so the preview matches the day they actually have. web
// never computes a curve itself, so a medication the user hasn't selected is
// previewed through /api/timeline/?medication=<id> rather than drawn here.
async function loadCurve(medicationId, scheduled) {
  if (!medicationId) return
  curveLoading.value = true
  curveError.value = ''
  curve.value = []
  try {
    const [hours, minutes] = scheduled.split(':').map(Number)
    const at = new Date()
    at.setHours(hours, minutes, 0, 0)
    const timeline = await fetchTimeline(at.toISOString(), medicationId)
    curve.value = timeline.curve
  } catch (err) {
    curveError.value = "Couldn't load this medication's release curve."
  } finally {
    curveLoading.value = false
  }
}

// Reloads on either input: a different medication, or a new scheduled time
// (the curve is drawn against the time of day the dose is taken). Watching
// the pair rather than each separately means changing both only refetches
// once, and the first fetch waits until the catalogue has settled on an id.
watch(
  () => [viewingId.value, savedScheduledTime.value],
  ([id, scheduled]) => loadCurve(id, scheduled),
)

const sparkPath = computed(() => sparkPathFromCurve(curve.value, 120, 44, 3))
</script>

<template>
  <div v-if="loading" class="med-status">Loading…</div>
  <div v-else-if="loadError" class="med-status">{{ loadError }}</div>

  <div v-else class="medications-page">
    <!-- Left column: scrollable list of known medications. A <button> per row
         (rather than a clickable <div>) so the list is keyboard- and
         screen-reader-accessible for free.
         Two states worth telling apart: `viewing` is the one being read,
         `active` is the one that's yours. The "Current" badge carries that
         second meaning in text, so it doesn't rest on colour alone. -->
    <aside class="med-list">
      <div class="list-title">Medications</div>
      <button
        v-for="m in medications"
        :key="m.id"
        type="button"
        class="med-row"
        :class="{ viewing: m.id === viewingId, active: m.id === activeId }"
        :aria-pressed="m.id === viewingId"
        @click="viewMed(m.id)"
      >
        <div class="med-row-head">
          <div class="med-row-name">{{ m.name }}</div>
          <span v-if="m.id === activeId" class="med-row-badge">Current</span>
        </div>
        <div class="med-row-blurb">{{ m.blurb }}</div>
      </button>
    </aside>

    <!-- Right column: details for whichever medication is selected. -->
    <section v-if="viewedMed" class="med-detail">
      <div class="med-head">
        <div>
          <div class="med-name">{{ viewedMed.name }}</div>
          <div class="med-class">{{ viewedMed.drug_class || 'stimulant' }}</div>
        </div>

        <!-- Selecting is an explicit act, so you can read about anything here
             without it becoming yours. -->
        <span v-if="viewingIsActive" class="med-current">Your current medication</span>
        <button
          v-else
          type="button"
          class="med-select-btn"
          :disabled="saving"
          @click="confirmSelection"
        >{{ saving ? 'Saving…' : 'Select this medication' }}</button>
      </div>

      <p v-if="saveError" class="med-error" role="alert">{{ saveError }}</p>

      <p class="med-desc">{{ viewedMed.description }}</p>

      <!-- The dose time pk classifies each day against. Only shown on the
           active medication, because it saves to whichever one is yours --
           offering it while you're reading about another would edit something
           you aren't looking at. -->
      <form v-if="viewingIsActive" class="schedule-block" @submit.prevent="saveScheduledTime">
        <div class="schedule-label">Scheduled dose time</div>
        <div class="schedule-row">
          <input
            v-model="scheduledTime"
            type="time"
            class="schedule-input"
            aria-label="Scheduled dose time"
          />
          <button
            type="submit"
            class="schedule-save"
            :disabled="savingTime || scheduledTime === savedScheduledTime"
          >Save</button>
          <span v-if="timeSaved" class="schedule-saved">Saved</span>
        </div>
        <p class="schedule-hint">
          Doses are called on time or late against this time — set it to when you actually
          take yours.
        </p>
        <p v-if="timeError" class="med-error" role="alert">{{ timeError }}</p>
      </form>

      <div class="spark-block">
        <div class="spark-label">Release shape</div>
        <p v-if="curveLoading" class="spark-status">Loading…</p>
        <p v-else-if="curveError" class="spark-status">{{ curveError }}</p>
        <svg v-else viewBox="0 0 120 44" width="220" height="80" class="spark-svg">
          <path :d="sparkPath" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" />
        </svg>
        <p class="spark-caption">
          Modelled from published parameters for a {{ savedScheduledTime }} dose — a prediction
          of an average response, not a measurement.
        </p>
      </div>

      <!-- Provenance, or the honest absence of it. The old placeholder data
           carried a fabricated "Medsafe · retrieved 6 Sep 2026" line on every
           medication; the catalogue's source fields are genuinely empty, so
           the page says that instead of implying a citation exists. -->
      <div class="source-block">
        <span class="source-icon">§</span>
        <p v-if="viewedMed.source" class="source-text">
          {{ viewedMed.source }}
          <a v-if="viewedMed.source_url" :href="viewedMed.source_url" target="_blank" rel="noopener">
            source
          </a>
          <span v-if="viewedMed.retrieved"> · retrieved {{ viewedMed.retrieved }}</span>
        </p>
        <p v-else class="source-text">
          No published source recorded for this medication yet — its curve parameters and
          description haven't been checked against Medsafe or the NZ Formulary.
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.med-status {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  font: 400 15px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.medications-page {
  display: flex;
  min-height: 100vh;
}

.med-list {
  flex: none;
  width: 400px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 32px 8px;
  overflow-y: auto;
}

.list-title {
  font: 600 18px 'Inter', sans-serif;
  color: var(--fg);
  padding: 0 20px 16px;
}

/* Reset default <button> styling so these rows look like the plain,
   borderless list items in the design mock. */
.med-row {
  display: block;
  width: 100%;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 12px;
  padding: 14px 20px;
  margin: 0 12px 2px;
  font: inherit;
  color: inherit;
}

/* The one that's yours. */
.med-row.active {
  background: var(--accent-soft);
}

/* The one being read. An outline rather than a fill, so a row that is both
   still shows the active background underneath. */
.med-row.viewing {
  box-shadow: inset 0 0 0 1.5px var(--accent);
}

.med-row-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.med-row-badge {
  flex: none;
  background: var(--accent);
  color: var(--accent-contrast);
  border-radius: 20px;
  padding: 2px 8px;
  font: 600 10.5px 'Inter', sans-serif;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.med-row-name {
  font: 600 15px 'Inter', sans-serif;
  color: var(--fg);
}

.med-row-blurb {
  font: 400 12.5px/1.4 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-top: 3px;
}

.med-detail {
  flex: 1;
  min-width: 0;
  padding: 44px 56px;
  overflow-y: auto;
}

.med-detail > * {
  max-width: 640px;
}

/* Title on the left, the select action on the right. Wraps rather than
   squashing the button on a narrow window. */
.med-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.med-name {
  font: 700 26px 'Inter', sans-serif;
  color: var(--fg);
}

.med-select-btn {
  flex: none;
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 10px;
  padding: 11px 18px;
  font: 600 14px 'Inter', sans-serif;
  cursor: pointer;
}

.med-select-btn:disabled {
  opacity: 0.7;
  cursor: default;
}

.med-current {
  flex: none;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 20px;
  padding: 7px 14px;
  font: 600 12.5px 'Inter', sans-serif;
}

.med-class {
  font: 400 14px 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-top: 4px;
}

.med-desc {
  margin: 22px 0 0;
  font: 400 16px/1.65 'Inter', sans-serif;
  color: var(--fg);
}

.med-error {
  margin: 10px 0 0;
  padding: 10px 14px;
  border-radius: 9px;
  background: var(--flag-soft);
  color: var(--flag);
  font: 500 13px/1.4 'Inter', sans-serif;
}

.schedule-block {
  margin-top: 22px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
}

.schedule-label {
  font: 600 13px 'Inter', sans-serif;
  color: var(--fg);
  margin-bottom: 10px;
}

.schedule-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.schedule-input {
  font: 500 14px ui-monospace, Menlo, monospace;
  color: var(--fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px 10px;
}

.schedule-save {
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font: 600 13px 'Inter', sans-serif;
  cursor: pointer;
}

.schedule-save:disabled {
  opacity: 0.5;
  cursor: default;
}

.schedule-saved {
  font: 500 12.5px 'Inter', sans-serif;
  color: var(--accent);
}

.schedule-hint {
  margin: 10px 0 0;
  font: 400 12.5px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
}

.spark-block {
  margin-top: 22px;
}

.spark-label {
  font: 500 13px/1 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-bottom: 10px;
}

.spark-status {
  margin: 0;
  height: 80px;
  display: flex;
  align-items: center;
  font: 400 13px 'Inter', sans-serif;
  color: var(--fg-muted);
}

.spark-svg {
  overflow: visible;
  display: block;
}

.spark-caption {
  margin: 10px 0 0;
  font: 400 12.5px/1.5 'Inter', sans-serif;
  color: var(--fg-muted);
}

.source-block {
  margin-top: 22px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
}

.source-icon {
  flex: none;
  font-size: 15px;
  color: var(--fg-muted);
}

.source-text {
  margin: 0;
  font: 400 14px/1.5 'Inter', sans-serif;
  color: var(--fg);
}
</style>
