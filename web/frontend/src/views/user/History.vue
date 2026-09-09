<script setup>
// <script setup> is Vue 3 shorthand: anything declared at the top level here
// (variables, functions, imports) is automatically available to the <template>
// below, with no separate "export default { data(){...} }" boilerplate needed.
import { computed } from 'vue'
import { HISTORY_SEED, STATUS_LABELS } from '@/lib/placeholderData.js'

// Small helper so the template can show "On time" instead of the raw
// "on-time" status string stored in the data.
const statusLabel = (status) => STATUS_LABELS[status] ?? status

// Stats panel figures, all derived from HISTORY_SEED rather than hardcoded,
// so they stay correct if the placeholder data changes.
// HISTORY_SEED is newest-first (see lib/placeholderData.js).
const totalDays = computed(() => HISTORY_SEED.length)
const missedDays = computed(() => HISTORY_SEED.filter((d) => d.status === 'missed').length)
const adherencePercent = computed(() =>
  Math.round(((totalDays.value - missedDays.value) / totalDays.value) * 100)
)
// Consecutive not-missed days counting back from today; stops at the first
// missed day. "Edited"/"late" still count as taken, so they extend the streak.
const currentStreak = computed(() => {
  let streak = 0
  for (const d of HISTORY_SEED) {
    if (d.status === 'missed') break
    streak++
  }
  return streak
})
</script>

<template>
  <div class="history-page">
    <!-- Left/center column: page header and the day-by-day dose list. -->
    <div class="main-col">
      <div class="page-header">
        <div class="page-title">History — last two weeks</div>
        <div class="page-subtitle">Dose time and status for each day.</div>
      </div>

      <div class="day-list">
        <div v-for="d in HISTORY_SEED" :key="d.date" class="day-row">
          <div class="day-row-date">
            <div class="day-row-date-main">{{ d.date }}</div>
            <div class="day-row-dow">{{ d.dow }}</div>
          </div>
          <div class="day-row-time">{{ d.doseTime }}</div>
          <div class="day-row-status" :class="d.status">{{ statusLabel(d.status) }}</div>
        </div>
      </div>
    </div>

    <!-- Right sidebar: adherence stats over the same two-week window. Sized
         to match the Today page's notes sidebar (see Today.vue's .notes-col). -->
    <div class="stats-col">
      <div class="section-title">Stats</div>
      <div class="stats-list">
        <!-- Adherence and streak are "good news" metrics, so they use the
             app's blue accent colour (same one the "on-time" pill uses in
             the list below). A slim progress track echoes the percentage. -->
        <div class="stat-card accent">
          <div class="stat-label"><span class="stat-dot"></span>Adherence</div>
          <div class="stat-value">{{ adherencePercent }}%</div>
          <div class="stat-bar">
            <div class="stat-bar-fill" :style="{ width: adherencePercent + '%' }"></div>
          </div>
        </div>
        <div class="stat-card accent">
          <div class="stat-label"><span class="stat-dot"></span>Current streak</div>
          <div class="stat-value">{{ currentStreak }} days</div>
        </div>
        <!-- Missed doses use the app's red/orange "flag" colour instead — the
             same one the "late"/"edited" pills use — to call it out as the
             one number here worth a second look. -->
        <div class="stat-card flag">
          <div class="stat-label"><span class="stat-dot"></span>Missed</div>
          <div class="stat-value">{{ missedDays }} of {{ totalDays }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-page {
  display: flex;
  min-height: 100vh;
}

.main-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 36px 48px;
  gap: 28px;
  overflow-y: auto;
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

.day-list {
  display: flex;
  flex-direction: column;
  max-width: 760px;
}

.day-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 4px;
  border-bottom: 1px solid var(--border);
}

.day-row-date {
  flex: none;
  width: 80px;
}

.day-row-date-main {
  font: 600 14px 'Inter', sans-serif;
  color: var(--fg);
}

.day-row-dow {
  font: 400 12px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.day-row-time {
  flex: 1;
  font: 400 14px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.day-row-status {
  flex: none;
  padding: 4px 10px;
  border-radius: 20px;
  font: 600 12px 'Inter', sans-serif;
  background: var(--surface);
  color: var(--fg-muted);
}

.day-row-status.on-time {
  background: var(--accent-soft);
  color: var(--accent);
}

.day-row-status.edited,
.day-row-status.late {
  background: var(--flag-soft);
  color: var(--flag);
}

/* Same footprint as Today.vue's .notes-col, so the two pages line up. */
.stats-col {
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

.stats-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-card {
  position: relative;
  /* Left border-radius shrunk so the colour stripe below (::before) sits
     flush against a square inner corner instead of poking past a round one. */
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px 12px 12px 4px;
  padding: 14px 16px;
  /* Keeps the colour stripe from spilling past the card's rounded corners. */
  overflow: hidden;
}

/* Colour stripe down the left edge, echoing the coloured dot in the label. */
.stat-card::before {
  content: '';
  position: absolute;
  inset-block: 0;
  left: 0;
  width: 3px;
}

.stat-card.accent::before {
  background: var(--accent);
}

.stat-card.flag::before {
  background: var(--flag);
}

.stat-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font: 500 12px 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-bottom: 6px;
}

.stat-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.stat-card.accent .stat-dot {
  background: var(--accent);
}

.stat-card.flag .stat-dot {
  background: var(--flag);
}

.stat-value {
  font: 700 22px ui-monospace, Menlo, monospace;
  color: var(--fg);
}

.stat-card.accent .stat-value {
  color: var(--accent);
}

.stat-card.flag .stat-value {
  color: var(--flag);
}

.stat-bar {
  margin-top: 10px;
  height: 5px;
  border-radius: 3px;
  background: var(--border);
  overflow: hidden;
}

.stat-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
}
</style>
