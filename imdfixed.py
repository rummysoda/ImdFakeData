import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

#  Simulation settings
total_duration_s = 120           # simulate 2 minutes total runtime
sample_rate_hz = 1000            # 1 ms sampling interval
V_high, V_low = 5.0, 0.0         # logic-level voltages for high/low outputs

#  Possible IMD output frequencies (per datasheet)
frequencies = [10, 20, 30, 40, 50]
#  Relative likelihood of each mode; mostly 10 Hz (normal)
weights = [0.9, 0.03, 0.05, 0.01, 0.01]

rows = []                        # list to hold every simulated sample
t = datetime.now()               # start timestamp
elapsed_total = 0.0              # total elapsed simulated time tracker


def simulate_segment(f, duty, okhs, duration_s, t_start):
    
    ##Generate one time segment of IMD PWM and OKHS voltages.

    ##f        - PWM frequency (Hz)
    ##duty     - PWM duty cycle (%)
    ##okhs     - OKHS voltage (High=5 V / Low=0 V)
    ##duration_s - how long this segment lasts (s)
    ##t_start  - timestamp when this segment begins
    
    n_samples = int(duration_s * sample_rate_hz)      # number of 1 ms samples
    t_vals = [t_start + timedelta(milliseconds=i) for i in range(n_samples)]
    period_s = 1.0 / f                                # one full PWM cycle time

    pwm_signal = []
    elapsed = 0.0
    for _ in range(n_samples):
        # phase progresses 0→1 across each PWM cycle
        phase = (elapsed % period_s) / period_s
        # output high for the duty fraction, low otherwise
        v = V_high if phase < duty / 100 else V_low
        pwm_signal.append(v)
        elapsed += 1.0 / sample_rate_hz

    # build sample records for this segment
    segment_rows = [
        {
            "timestamp": int(ts.timestamp() * 1000),  # ms since epoch
            "MHS_voltage_V": round(v, 3),
            "OKHS_voltage_V": okhs,
        }
        for ts, v in zip(t_vals, pwm_signal)
    ]
    # return rows and timestamp for the next segment start
    return segment_rows, t_vals[-1] + timedelta(milliseconds=1)


#  First segment: IMD startup SST phase (always 30 Hz for ~2 s)
f = 30
if random.random() < 0.85:
    duty = random.uniform(5, 10)    # SST good condition
    okhs = V_high
else:
    duty = random.uniform(90, 95)   # SST bad condition
    okhs = V_low
segment_duration = 2.0              # fixed 2-second startup self-test
segment_rows, t = simulate_segment(f, duty, okhs, segment_duration, t)
rows.extend(segment_rows)
elapsed_total += segment_duration


#  Continue generating random segments until reaching 120 s total
while elapsed_total < total_duration_s:
    #  Pick a random IMD mode based on probabilities
    f = np.random.choice(frequencies, p=weights)
    period_s = 1.0 / f

    #  Choose duty-cycle and OKHS level per IMD operating state
    if f == 10:                     # Normal operation
        duty = random.uniform(5, 95)
        okhs = V_high
    elif f == 20:                   # Undervoltage condition
        duty = random.uniform(5, 95)
        okhs = V_low
    elif f == 30:                   # SST (should rarely occur after startup)
        if random.random() < 0.85:
            duty = random.uniform(5, 10)   # Good
            okhs = V_high
        else:
            duty = random.uniform(90, 95)  # Bad
            okhs = V_low
    elif f == 40:                   # Device error
        duty = random.uniform(47.5, 52.5)
        okhs = V_low
    else:                           # 50 Hz → Earth-connection fault
        duty = random.uniform(47.5, 52.5)
        okhs = V_low

    #  Each mode persists 3–10s 
    segment_duration = random.uniform(3, 10)
    #  make it sure it sticks to 2minutes total
    if elapsed_total + segment_duration > total_duration_s:
        segment_duration = total_duration_s - elapsed_total

    #  Simulate this segment and append its samples
    segment_rows, t = simulate_segment(f, duty, okhs, segment_duration, t)
    rows.extend(segment_rows)
    elapsed_total += segment_duration


#  Assemble everything into a DataFrame and export to JSON
df = pd.DataFrame(rows)
out_path = "IMD_output_2min_startup_30Hz.json"
df.to_json(out_path, orient="records", indent=2)



#SST = 30 Hz for the first ~2 s.

#There are ~60 PWM cycles (period ≈ 33.3 ms each).

#Now two possibilities:

#If SST is GOOD

#MHS (PWM): duty 5–10 % → mostly 0 V, with brief highs at ~5 V for 1.7–3.3 ms each cycle.

#OKHS (status): High (~5 V) the whole 2 s.

#If SST is BAD

#MHS (PWM): duty 90–95 % → mostly ~5 V, with brief lows at 0 V for 1.7–3.3 ms each cycle.

#OKHS (status): Low (0 V) the whole 2 s.