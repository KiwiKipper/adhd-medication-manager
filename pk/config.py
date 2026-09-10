"""Every tunable constant for the pk service lives here.

Nothing anywhere else in this codebase may hardcode a threshold: changing a
value in this file (and redeploying) is the demonstrated source-code change.
"""

# --- Event thresholds, as a proportion of the normalised peak (peak == 1.0) ---
ONSET_THRESHOLD    = 0.20   # proportion of peak that counts as "feeling it"
FADE_THRESHOLD     = 0.50   # after peak, below this = starting to fade
WORN_THRESHOLD     = 0.10   # after peak, below this = largely worn off

# --- Adherence classification ---
LATE_AFTER_MINUTES = 30     # a dose later than this is "late"

# --- Sampling of the curve ---
SAMPLE_MINUTES     = 5      # spacing between samples of the curve, in minutes
WINDOW_HOURS       = 24     # how far past taken_at the curve is sampled

# --- Model identity, echoed in every response ---
MODEL_VERSION      = "1.0"

# --- Shape detection ---
LOCAL_MAX_MIN_DIP  = 0.02   # a later bump only counts as a separate maximum if
                            # the curve first dips this far below both peaks
KA_KE_EPSILON      = 1e-9   # |ka - ke| below this uses the limiting case, since
                            # the closed form for t_max divides by (ka - ke)

# --- Rounding of emitted numbers (presentation only) ---
CURVE_TIME_DECIMALS  = 4    # decimal places on curve t_h values
CURVE_LEVEL_DECIMALS = 4    # decimal places on curve level values
ADHERENCE_DECIMALS   = 2    # decimal places on the adherence proportion
