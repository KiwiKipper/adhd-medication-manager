import { formatClockTime } from './timeline.js'

export const STATUS_LABELS = {
  'on-time': 'On time',
  edited: 'Edited',
  late: 'Late',
  missed: 'Missed',
}

export const statusLabel = (status) => STATUS_LABELS[status] ?? status

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

// "2026-09-07" -> "Sep 7". Built from the date string's own parts (rather
// than `new Date("2026-09-07")`, which parses as UTC and can land on the
// wrong day in some timezones) so it always matches the date the backend meant.
function formatDateLabel(isoDate) {
  const [, month, day] = isoDate.split('-').map(Number)
  return `${MONTH_NAMES[month - 1]} ${day}`
}

// "2026-09-07" for a given local Date, matching the backend's `date` field.
function toIsoDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Turns the Dose[] from fetchDoses() into the last `days` calendar days,
// newest first, filling in any day with no logged dose as 'missed' — the
// backend only returns rows that exist, so gaps have to be synthesized here.
export function buildHistoryRows(doses, days = 10) {
  const byDate = new Map(doses.map((d) => [d.date, d]))
  const rows = []

  for (let i = 0; i < days; i++) {
    const day = new Date()
    day.setDate(day.getDate() - i)
    const isoDate = toIsoDate(day)
    const dose = byDate.get(isoDate)

    rows.push({
      date: formatDateLabel(isoDate),
      doseTime: dose?.taken_at ? formatClockTime(new Date(dose.taken_at)) : '—',
      status: dose?.status ?? 'missed',
    })
  }

  return rows
}
