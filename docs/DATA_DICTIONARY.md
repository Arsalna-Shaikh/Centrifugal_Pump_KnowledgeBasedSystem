# Data Dictionary

## operational_sensor_log.csv
- `timestamp`: synthetic five-minute time stamp.
- `vibration_mm_s_rms`: synthetic overall vibration value.
- `bearing_temp_c`: bearing temperature.
- `motor_temp_c`: motor temperature.
- `flow_percent_of_baseline`: flow as percentage of a healthy reference condition.
- `discharge_pressure_bar`: discharge pressure.
- `suction_pressure_bar_abs`: absolute suction pressure.
- `motor_current_a`: motor current.
- `seal_temp_c`: seal-area temperature.
- `pressure_fluctuation_percent`: synthetic pressure instability indicator.
- `abnormal_noise`: 1 if abnormal mechanical noise is present.
- `air_bubbles`: 1 if frothy discharge / air bubbles are observed.
- `prime_ok`: 1 when the pump is primed.
- `episode_label`: synthetic generating condition (`NORMAL`, `F01`, `F02`, etc.).

## diagnostic_cases.csv
Each row is a synthetic diagnosis case. Symptom columns use 1 = observed and 0 = not observed. `true_fault_id` is the fault used to generate the synthetic pattern. `simulated_missing_rate` records the intended incompleteness level used during generation.

## Important
These datasets are created for educational prototyping. They are not field measurements and should not be described as real industrial logs.
