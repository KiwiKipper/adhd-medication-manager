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

// Fetch the current user's actively-selected medication, or { medication: null } if none is set
export async function fetchMyMedication() {
  const response = await api.get("/api/my-medication/")
  return response.data
}

// Set the current user's active medication to the given catalogue id (e.g. "concerta")
export async function selectMedication(medicationId) {
  const response = await api.post("/api/my-medication/", { medication: medicationId })
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

// Fetch the current user's notes, newest first
export async function fetchNotes() {
  const response = await api.get("/api/notes/")
  return response.data
}

// Create a new note for the current user
export async function addNote(text) {
  const response = await api.post("/api/notes/", { text })
  return response.data
}

/*
---------------------------------------------------------------------------
Future helpers for Medications.vue and History.vue
---------------------------------------------------------------------------
Both views currently render placeholder data from lib/placeholderData.js.
Once the medication/dose-log backend endpoints exist, replace those
placeholder imports with calls like the ones sketched below (following the
same async/response.data pattern as fetchMe() above).

Fetch the list of medications available to the current user, replacing
MED_DATA from lib/placeholderData.js.
export async function fetchMedications() {
  const response = await api.get("/medications/")
  return response.data
}

Fetch the dose-log history (date, dose time, on-time/late/edited/missed
status, and which medication was taken) for the current user, replacing
HISTORY_SEED from lib/placeholderData.js. Consider accepting a date range
or limit once History.vue needs more than "the last two weeks".
export async function fetchDoseHistory() {
  const response = await api.get("/doses/history/")
  return response.data
}
*/
