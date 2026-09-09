<script setup>
// <script setup> is Vue 3 shorthand: anything declared at the top level here
// (variables, functions, imports) is automatically available to the <template>
// below, with no separate "export default { data(){...} }" boilerplate needed.
import { ref, computed } from 'vue'
import { catmullRom } from '@/lib/curve.js'
import { MED_DATA } from '@/lib/placeholderData.js'

// The design mock shows a static "methylphenidate-class stimulant" subtitle
// under every medication, which is only correct for 3 of the 5 — Dexamfetamine
// and Vyvanse are amfetamine-class stimulants. MED_DATA (lib/placeholderData.js)
// has no drug-class field, so this fills the gap locally by medication id
// rather than showing medically wrong text or inventing new placeholder fields.
const DRUG_CLASS_LABELS = {
  concerta: 'methylphenidate-class stimulant',
  'ritalin-ir': 'methylphenidate-class stimulant',
  'ritalin-la': 'methylphenidate-class stimulant',
  dexamf: 'amfetamine-class stimulant',
  vyvanse: 'amfetamine-class stimulant (prodrug)',
}

// `ref()` wraps a value so Vue can detect changes to it and re-render the
// template automatically. Starts on the first medication, same as the design mock.
const selectedId = ref(MED_DATA[0].id)

// Looked up whenever `selectedId` changes; `computed()` caches the result and
// only recalculates when something it reads (selectedId, MED_DATA) changes.
const selectedMed = computed(
  () => MED_DATA.find((m) => m.id === selectedId.value) ?? MED_DATA[0]
)

const selectedDrugClass = computed(
  () => DRUG_CLASS_LABELS[selectedMed.value.id] ?? 'stimulant'
)

// Converts a medication's normalized release-shape (x/y as 0-100% points) into
// an SVG path sized to a `w`-by-`h` viewBox, with `pad` px of vertical margin
// so the curve doesn't touch the top/bottom edge. Mirrors the design mock's
// `sparkFromShape`. Kept local here (rather than added to lib/curve.js) since
// this task is scoped to editing Medications.vue and History.vue only.
function sparkPath(shape, w, h, pad) {
  const points = shape.map(([x, y]) => ({
    x: (x / 100) * w,
    y: h - pad - (y / 100) * (h - pad * 2),
  }))
  return catmullRom(points)
}

// Recomputed whenever the selected medication changes.
const selectedSparkPath = computed(() => sparkPath(selectedMed.value.shape, 120, 44, 3))
</script>

<template>
  <div class="medications-page">
    <!-- Left column: scrollable list of known medications. A <button> per row
         (rather than a clickable <div>) so the list is keyboard- and
         screen-reader-accessible for free. -->
    <aside class="med-list">
      <div class="list-title">Medications</div>
      <button
        v-for="m in MED_DATA"
        :key="m.id"
        type="button"
        class="med-row"
        :class="{ active: m.id === selectedId }"
        :aria-pressed="m.id === selectedId"
        @click="selectedId = m.id"
      >
        <div class="med-row-name">{{ m.name }}</div>
        <div class="med-row-blurb">{{ m.blurb }}</div>
      </button>
    </aside>

    <!-- Right column: details for whichever medication is selected. -->
    <section class="med-detail">
      <div>
        <div class="med-name">{{ selectedMed.name }}</div>
        <div class="med-class">{{ selectedDrugClass }}</div>
      </div>

      <p class="med-desc">{{ selectedMed.longDesc }}</p>

      <div class="spark-block">
        <div class="spark-label">Release shape</div>
        <svg viewBox="0 0 120 44" width="220" height="80" class="spark-svg">
          <path :d="selectedSparkPath" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" />
        </svg>
      </div>

      <div class="source-block">
        <span class="source-icon">§</span>
        <p class="source-text">{{ selectedMed.source }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
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

.med-row.active {
  background: var(--accent-soft);
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

.med-name {
  font: 700 26px 'Inter', sans-serif;
  color: var(--fg);
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

.spark-block {
  margin-top: 22px;
}

.spark-label {
  font: 500 13px/1 'Inter', sans-serif;
  color: var(--fg-muted);
  margin-bottom: 10px;
}

.spark-svg {
  overflow: visible;
  display: block;
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
