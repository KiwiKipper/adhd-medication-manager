// Placeholder data mirroring the Dose design mock, until the real
// medication/dose-log/curve APIs (including the "pk" release-curve service) exist.

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

export const HISTORY_SEED = [
  { date: 'Sep 7', dow: 'Sun', doseTime: '8:00 am', status: 'edited' },
  { date: 'Sep 6', dow: 'Sat', doseTime: '8:05 am', status: 'on-time' },
  { date: 'Sep 5', dow: 'Fri', doseTime: '8:35 am', status: 'late' },
  { date: 'Sep 4', dow: 'Thu', doseTime: '7:58 am', status: 'on-time' },
  { date: 'Sep 3', dow: 'Wed', doseTime: '—', status: 'missed' },
  { date: 'Sep 2', dow: 'Tue', doseTime: '8:02 am', status: 'on-time' },
  { date: 'Sep 1', dow: 'Mon', doseTime: '8:10 am', status: 'on-time' },
  { date: 'Aug 31', dow: 'Sun', doseTime: '9:20 am', status: 'late' },
  { date: 'Aug 30', dow: 'Sat', doseTime: '8:04 am', status: 'on-time' },
  { date: 'Aug 29', dow: 'Fri', doseTime: '7:55 am', status: 'on-time' },
  { date: 'Aug 28', dow: 'Thu', doseTime: '8:12 am', status: 'on-time' },
  { date: 'Aug 27', dow: 'Wed', doseTime: '—', status: 'missed' },
  { date: 'Aug 26', dow: 'Tue', doseTime: '8:01 am', status: 'on-time' },
  { date: 'Aug 25', dow: 'Mon', doseTime: '8:08 am', status: 'on-time' },
]

export const STATUS_LABELS = {
  'on-time': 'On time',
  edited: 'Edited',
  late: 'Late',
  missed: 'Missed',
}

export const TODAY_TIMELINE = [
  { time: '8:00 am', label: 'Taken', state: 'past' },
  { time: '9:12 am', label: 'Should start to feel it', state: 'past' },
  { time: '10:30 am', label: 'First peak', state: 'past' },
  { time: '1:45 pm', label: 'Second release', state: 'past' },
  { time: '5:20 pm', label: 'Starting to fade', state: 'future' },
  { time: '8:10 pm', label: 'Largely worn off', state: 'future' },
]
