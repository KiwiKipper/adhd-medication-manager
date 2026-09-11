<script setup>
// Thin container: loads the state both Today sub-views need, then decides
// which one to show. No route change between them — "today" is one URL with
// two states (no dose logged yet vs. dose logged), matching the design mock.
import { ref, computed, onMounted } from 'vue'
import { fetchDoses, fetchMyMedication, logDose, deleteTodayDose } from '@/api.js'
import { buildHistoryRows } from '@/lib/doseHistory.js'
import TodayTakeDose from './TodayTakeDose.vue'
import TodayTimeline from './TodayTimeline.vue'

const loading = ref(true)
const medication = ref(null) // { id, name } or null if none selected yet
const todayDose = ref(null) // today's Dose row, or null if not logged yet
const historyDoses = ref([]) // raw last-14-days Dose[] from the API
const takingDose = ref(false)

const historyRows = computed(() => buildHistoryRows(historyDoses.value))

onMounted(async () => {
  const [todayDoses, myMedication, doses] = await Promise.all([
    fetchDoses('today'),
    fetchMyMedication(),
    fetchDoses(),
  ])
  todayDose.value = todayDoses[0] ?? null
  medication.value = myMedication.medication
  historyDoses.value = doses
  loading.value = false
})

// Keeps historyDoses in sync so the last-10-days list reflects a just-logged
// or just-edited dose without needing to refetch.
function upsertHistoryDose(dose) {
  const i = historyDoses.value.findIndex((d) => d.date === dose.date)
  if (i >= 0) historyDoses.value[i] = dose
  else historyDoses.value = [dose, ...historyDoses.value]
}

async function takeDoseNow() {
  takingDose.value = true
  try {
    const dose = await logDose(new Date().toISOString())
    todayDose.value = dose
    upsertHistoryDose(dose)
  } finally {
    takingDose.value = false
  }
}

function onDoseUpdated(dose) {
  todayDose.value = dose
  upsertHistoryDose(dose)
}

async function onDoseReset() {
  await deleteTodayDose()
  historyDoses.value = historyDoses.value.filter((d) => d.date !== todayDose.value.date)
  todayDose.value = null
}
</script>

<template>
  <div v-if="loading" class="today-status">Loading…</div>

  <div v-else-if="!medication" class="today-status">
    <p>No medication selected yet.</p>
    <router-link to="/medications">Choose a medication</router-link>
  </div>

  <TodayTimeline
    v-else-if="todayDose"
    :dose="todayDose"
    :history-rows="historyRows"
    @dose-updated="onDoseUpdated"
    @dose-reset="onDoseReset"
  />

  <TodayTakeDose
    v-else
    :medication="medication"
    :pending="takingDose"
    @take-dose="takeDoseNow"
  />
</template>

<style scoped>
.today-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 100vh;
  font: 400 15px 'Inter', sans-serif;
  color: var(--fg-muted);
}
</style>
