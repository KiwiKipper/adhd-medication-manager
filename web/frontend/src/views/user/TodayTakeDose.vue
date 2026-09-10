<script setup>
// Shown on the Today page before any dose has been logged for the day
// (mirrors "Today — before taken", page 07 of Dose Desktop.html). Purely
// presentational — Today.vue owns the data fetching and the actual
// logDose() API call, this component just asks for one via @take-dose.
import { formatLongDate } from '@/lib/timeline.js'

defineProps({
  medication: { type: Object, required: true },
  pending: { type: Boolean, default: false },
})
defineEmits(['take-dose'])

const todayLabel = formatLongDate()
</script>

<template>
  <div class="today-page">
    <!-- No "Last 10 days" sidebar here — that only appears once there's a
         dose to show for today, on TodayTimeline. -->
    <div class="main-col">
      <div class="pre-dose-header">
        <div class="pre-dose-date">{{ todayLabel }}</div>
        <div class="pre-dose-title">Not taken yet today</div>
        <div class="pre-dose-med">{{ medication.name }}</div>
      </div>

      <div class="button-anchor">
        <button
          type="button"
          class="take-dose-button"
          :disabled="pending"
          @click="$emit('take-dose')"
        >
          <span>Take</span>
          <span>dose</span>
        </button>
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
  /* Button size/gap as variables so the header's anchor offset below always
     matches, instead of duplicating the same numbers in two places. */
  --btn-radius: 125px;
  --header-gap: 60px;
  flex: 1;
  min-width: 0;
  position: relative;
}

/* Positioned by its own bottom edge (not stacked in flow above the button),
   so its height never affects where the button's center lands - only the
   button's own top/left below determines that. */
.pre-dose-header {
  position: absolute;
  left: 50%;
  bottom: calc(50% + var(--btn-radius) + var(--header-gap));
  /* Two corrections on top of the plain 50%/50%: shift left by half the nav
     sidebar's width (this column only spans the space right of it, so
     centering within it alone lands right of true screen-center), and shift
     up by the page padding App.vue wraps every page in (that padding pushes
     .today-page down without shrinking its own 100vh box, so "50%" of it
     lands page-padding below true screen-center). */
  transform:
    translateX(-50%)
    translateX(calc(var(--sidebar-width) / -2))
    translateY(calc(var(--page-padding) * -1));
  text-align: center;
}

.pre-dose-date {
  font: 500 15px ui-monospace, Menlo, monospace;
  color: var(--fg-muted);
}

.pre-dose-title {
  font: 600 26px 'Inter', sans-serif;
  color: var(--fg);
  margin-top: 8px;
}

.pre-dose-med {
  font: 400 16px 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-top: 6px;
}

/* Positions the button at true screen-center (top/left: 50% of .main-col,
   which spans full viewport height/width right of the nav), independently of
   the header above it, so the header's height never pushes the button's own
   center off-screen-center. Kept as a separate, otherwise-invisible wrapper
   (rather than putting the transform on .take-dose-button itself) because a
   transform directly on the colored button promotes it to its own composited
   layer, which visibly washes out its oklch background in some browsers. */
.button-anchor {
  position: absolute;
  top: 50%;
  left: 50%;
  /* See .pre-dose-header above for why both the sidebar-width and
     page-padding corrections are needed. */
  transform:
    translate(-50%, -50%)
    translateX(calc(var(--sidebar-width) / -2))
    translateY(calc(var(--page-padding) * -1));
}

/* Concentric rings around the button, matching the design mock. */
.take-dose-button {
  position: relative;
  width: calc(var(--btn-radius) * 2);
  height: calc(var(--btn-radius) * 2);
  border-radius: 50%;
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  cursor: pointer;
  box-shadow: 0 16px 40px -10px var(--accent);
  font: 600 24px 'Inter', sans-serif;
}

.take-dose-button::before,
.take-dose-button::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.take-dose-button::before {
  inset: -50px;
  background: var(--accent-soft);
  z-index: -2;
}

.take-dose-button::after {
  inset: -28px;
  border: 3px dashed var(--accent);
  opacity: 0.5;
  z-index: -1;
}

.take-dose-button:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
