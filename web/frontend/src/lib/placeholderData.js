// Placeholder data mirroring the Dose design mock, until Medications.vue's
// descriptive blurb/longDesc/shape fields move to the real backend catalogue
// (fetchMedications() in api.js already returns id/name for real; the
// richer per-medication copy below is still hand-written). History.vue and
// TodayTimeline.vue no longer use this file -- see fetchAdherence() and
// fetchTimeline() in api.js, both computed by the pk service.

export const MED_DATA = [
  {
    id: 'concerta',
    name: 'Concerta 36mg',
    blurb: 'Two waves — a morning rise, a dip, then a broader afternoon peak.',
    longDesc: 'An outer layer releases through the morning; an inner core releases later, giving a second, broader peak in the afternoon before tapering off by evening.',
    shape: [[0, 0], [15, 10], [30, 80], [45, 55], [55, 40], [70, 75], [85, 45], [100, 10]],
    source: 'Source: Medsafe consumer medicine information · retrieved 6 Sep 2026',
  },
  {
    id: 'ritalin-ir',
    name: 'Ritalin IR 10mg',
    blurb: 'Comes on quickly and wears off within a few hours — a single peak.',
    longDesc: 'Releases all at once. Effects are typically felt within half an hour, peak within one to two hours, and taper off within about four hours.',
    shape: [[0, 0], [20, 85], [40, 90], [60, 50], [80, 15], [100, 2]],
    source: 'Source: Medsafe consumer medicine information · retrieved 6 Sep 2026',
  },
  {
    id: 'ritalin-la',
    name: 'Ritalin LA 20mg',
    blurb: 'An immediate dose, then a second delayed pulse about four hours later.',
    longDesc: 'A capsule combining an immediate-release portion with a second, delayed-release portion, producing two separate release peaks across the day.',
    shape: [[0, 0], [15, 70], [30, 55], [45, 40], [60, 85], [80, 45], [100, 10]],
    source: 'Source: Medsafe consumer medicine information · retrieved 6 Sep 2026',
  },
  {
    id: 'dexamf',
    name: 'Dexamfetamine 5mg',
    blurb: 'Fast onset, single peak, shorter tail than the extended-release options.',
    longDesc: 'An immediate-release tablet. Onset is typically fast, with a single peak and a shorter overall duration than extended-release formulations.',
    shape: [[0, 0], [15, 90], [35, 95], [55, 55], [75, 20], [100, 3]],
    source: 'Source: Medsafe consumer medicine information · retrieved 6 Sep 2026',
  },
  {
    id: 'vyvanse',
    name: 'Vyvanse 30mg',
    blurb: 'Builds gradually to one broad peak and tapers slowly over the day.',
    longDesc: 'A prodrug that is converted gradually in the body, producing a slow onset, one broad peak, and a longer, gentler taper than immediate-release options.',
    shape: [[0, 0], [25, 60], [45, 88], [65, 88], [85, 55], [100, 15]],
    source: 'Source: Medsafe consumer medicine information · retrieved 6 Sep 2026',
  },
]
