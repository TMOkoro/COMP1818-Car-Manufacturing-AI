# COMP1818 – Automotive Assembly-Line Balancing

## Project Description
This project implements the Ranked Positional Weight (RPW) algorithm for two-sided automotive assembly-line balancing.

It compares RPW against an ascending-task-ID baseline for electric and fuel-powered vehicles.

## Dataset
The dataset is located at `data/chassis_assembly_times.csv` and contains 58 assembly tasks.

## Experiments
Both algorithms are evaluated using cycle times of 50, 60 and 70 seconds.

## Python Files
- `full_rpw_balancing.py` – Main RPW implementation and baseline comparison.
- `cycle_time_testing.py` – Runs the cycle-time experiments.

## How to Run
Install the required Python libraries, then run:

```bash
python full_rpw_balancing.py
python cycle_time_testing.py
```

## Results
The experiments compare assembly positions, line efficiency and idle capacity. All 12 generated schedules passed the implemented validation checks.