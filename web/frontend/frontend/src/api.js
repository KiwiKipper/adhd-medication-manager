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
 
export async function logout() {
  const response = await api.post(
    "/auth/logout/"
  )
  return response.data
}

/* ---- might not need ---- */

export async function fetchMe() {
  const response = await api.get(
    "/auth/me/",
  )
  return response.data
}
