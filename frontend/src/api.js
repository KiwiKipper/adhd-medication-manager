import axios from "axios"
export const MAX_ATTEMPTS = 3
export const TIMEOUT_ERROR = "ETIMEDOUT"
 
const api = axios.create({
  baseURL: "http://localhost:8000",
  withCredentials: true,
  withXSRFToken: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
  timeout: 5000,
  transitional: {
        clarifyTimeoutError: true,
    }
});
 
// Helper function to pause execution for 'ms' milliseconds
function sleep(ms) {
  return new Promise(function (resolve) {
    setTimeout(resolve, ms);
  });
}

// Wrapper function to retry an axios request up to 'maxRetries' times
// Follows exponential backoff principle
// NOTE: Retrying GET requests is recommended, but be careful when retrying 
// POST requests 
export async function withRetry(maxRetries, axiosFunction, ...args) {
  // Set default value manually if not provided
  if (maxRetries === undefined || maxRetries === null)
    maxRetries = MAX_ATTEMPTS
 
  for (let x = 1; x <= maxRetries; x++) {
    try {
      return await axiosFunction(...args);
    } catch (error) {
      var isTimeout = error.code === TIMEOUT_ERROR
 
      if (isTimeout && x < maxRetries) {
        // jitter of upto 500ms to prevent multiple clients sending requests at same time
        const jitter = Math.random() * 500
        const dropOffTime = 100 * Math.pow(2, x - 1) + jitter
        await sleep(dropOffTime)
        console.log("Response Timeout. Retrying")
        continue
      }
      // different error
      throw error
    }
  }
}
 
// fetch Crsf token and store it as a cookie
// for future requests
export async function fetchCsrfCookie() {
  await api.get("/auth/csrf/")
}
 
// Authenticate with the given credentials and start a session
export async function login(username, password) {
  const response = await api.post(
    "/auth/login/",
    {
      username,
      password,
    }
  )
  return response.data;
 
}
 
// End the current session
export async function logout() {
  const response = await api.post(
    "/auth/logout/"
  )
  return response.data
}

// Fetch the signed-in user's profile
export async function fetchMe() {
  const response = await api.get(
    "/auth/me/",
  )
  return response.data
}

// Fetch the read-only medication catalogue (seeded by the backend)
export async function fetchMedications() {
  const response = await api.get("/api/medications/")
  return response.data
}

// Fetch the current user's actively-selected medication and the daily time
// it's scheduled for: { medication, scheduled_time } -- both null if nothing
// has been selected yet. scheduled_time is "HH:MM" and is what pk classifies
// each dose against as on-time or late.
export async function fetchMyMedication() {
  const response = await api.get("/api/my-medication/")
  return response.data
}

// Set the current user's active medication to the given catalogue id (e.g. "concerta")
export async function selectMedication(medicationId) {
  const response = await api.post("/api/my-medication/", { medication: medicationId })
  return response.data
}

// Change the daily time the current selection is scheduled for, without
// touching which medication it is. "HH:MM", 24-hour.
export async function setScheduledTime(scheduledTime) {
  const response = await api.post("/api/my-medication/", { scheduled_time: scheduledTime })
  return response.data
}

// Log a dose taken at the given ISO timestamp; logging again the same day edits that day's dose
export async function logDose(takenAt) {
  const response = await api.post("/api/doses/", { taken_at: takenAt })
  return response.data
}

// Fetch the current user's dose log. Pass "today" for just today's dose, or omit for the last 14 days
export async function fetchDoses(date) {
  const response = await api.get("/api/doses/", { params: date ? { date } : undefined })
  return response.data
}

// Delete today's logged dose, resetting the day back to "not taken yet"
export async function deleteTodayDose() {
  await api.delete("/api/doses/")
}

// Fetch the current user's notes, newest day first. Pass "today", or a
// "YYYY-MM-DD" date, for just that day's notes; omit it for all of them.
export async function fetchNotes(date) {
  const response = await api.get("/api/notes/", { params: date ? { date } : undefined })
  return response.data
}

// Create a note for the current user. `date` is the day the note is *about*
// (defaults to today server-side, which is what the Today page wants), and
// `flagged` marks it as something to stand out -- a bad reaction, a skipped
// dose, something to raise with a prescriber.
export async function addNote(text, { date, flagged } = {}) {
  const payload = { text }
  if (date) payload.date = date
  if (flagged !== undefined) payload.flagged = flagged
  const response = await api.post("/api/notes/", payload)
  return response.data
}

// Fetch today's release-curve timeline for the current user's active
// medication -- computed by the pk module, not here. Requires a dose to
// already be logged for today (pass an ISO-8601 timestamp with a UTC offset
// as `takenAt` to ask about a different moment instead), and optionally a
// catalogue id as `medicationId` to preview a medication the user hasn't
// selected, which is how the Medications page draws its release shape.
// Returns { taken_at, events: [{ at, label }], curve: [{ t_h, level }], ... }
export async function fetchTimeline(takenAt, medicationId) {
  const params = {}
  if (takenAt) params.taken_at = takenAt
  if (medicationId) params.medication = medicationId
  const response = await api.get("/api/timeline/", { params })
  return response.data
}

// Fetch adherence stats over the last `days` days (default 14) for the
// current user's active medication -- on-time/late/missed classification,
// streak and adherence percentage are computed by the pk module, not here.
// Returns { days: [{ date, status, minutes_late? }], adherence, streak_days, missed, of, ... }
export async function fetchAdherence(days) {
  const response = await api.get("/api/adherence/", { params: days ? { days } : undefined })
  return response.data
}
