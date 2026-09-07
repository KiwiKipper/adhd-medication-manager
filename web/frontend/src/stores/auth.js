import { reactive } from 'vue'
import { fetchMe } from '@/api.js'
 
// Who is signed in. Shared so the navbar and the router guard read the same thing.
export const auth = reactive({
  user: null,     // { email, first_name, last_name }
  loaded: false,  // has a session check finished at least once?
})
 
export async function loadUser() {
  try {
    auth.user = await fetchMe()
  } catch {
    auth.user = null
  }
  auth.loaded = true
  return auth.user
}
 
export function clearUser() {
  auth.user = null
}
