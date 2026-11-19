
from pathlib import Path
import pandas as pd
import networkx as nx

df = pd.read_csv(
    Path(__file__).parent / "data" / "chassis_assembly_times.csv",
    dtype={"Immediate_Predecessors": "string"}
)

G = nx.DiGraph()
G.add_nodes_from(df["Task_ID"])

for _, row in df.iterrows():
    if pd.notna(row["Immediate_Predecessors"]):
        for predecessor in row["Immediate_Predecessors"].split(","):
            G.add_edge(
                int(predecessor.strip()),
                int(row["Task_ID"])
            )

electric_tasks = df[
    df["Task_Set"].isin(["ET", "PT"])
]["Task_ID"].tolist()

graph = G.subgraph(electric_tasks).copy()

task_times = dict(zip(df["Task_ID"], df["Task_Time"]))
task_sides = dict(zip(df["Task_ID"], df["Operation_Side"]))

weights = {}

for task in graph.nodes():
    successors = nx.descendants(graph, task)
    weights[task] = task_times[task] + sum(
        task_times[s] for s in successors
    )

cycle_time = 60
schedule = {}
assigned = set()
position = 1

while len(assigned) < graph.number_of_nodes():
    side_finish = {"L": 0, "R": 0}
    tasks_this_position = 0

    while True:
        eligible = [
            task for task in graph.nodes()
            if task not in assigned
            and all(p in assigned for p in graph.predecessors(task))
        ]

        eligible.sort(key=lambda task: (-weights[task], task))

        selected = None

        for task in eligible:
            possible = []

            for side in ["L", "R"]:
                if task_sides[task] not in ("E", side):
                    continue

                predecessor_finish = max(
                    (
                        schedule[p]["finish"]
                        for p in graph.predecessors(task)
                        if schedule[p]["position"] == position
                    ),
                    default=0
                )

                start = max(side_finish[side], predecessor_finish)
                finish = start + task_times[task]

                if finish <= cycle_time:
                    possible.append((finish, side, start))

            if possible:
                finish, side, start = min(possible)
                selected = (task, side, start, finish)
                break

        if selected is None:
            break

        task, side, start, finish = selected

        schedule[task] = {
            "position": position,
            "side": side,
            "start": start,
            "finish": finish
        }

        assigned.add(task)
        side_finish[side] = finish
        tasks_this_position += 1

    if tasks_this_position == 0:
        raise RuntimeError(
            f"No tasks could be assigned at position {position}"
        )

    position += 1

print("\nELECTRIC VEHICLE RPW BALANCING RESULTS")

for pos in range(1, position):
    print(f"\nAssembly position {pos}")

    for side in ["L", "R"]:
        tasks = [
            task for task, info in schedule.items()
            if info["position"] == pos
            and info["side"] == side
        ]

        tasks.sort(key=lambda t: schedule[t]["start"])

        workload = sum(task_times[t] for t in tasks)

        print(
            f"  {side}: Tasks {tasks}, "
            f"Workload {workload}/{cycle_time}s"
        )

print("\nTotal assembly positions:", position - 1)
print("Total assigned tasks:", len(assigned))
print(
    "All tasks assigned:",
    len(assigned) == graph.number_of_nodes()
)

print("\nSCHEDULE VALIDATION")

violations = []

if set(schedule) != set(graph.nodes()):
    violations.append("Not all required tasks were scheduled")

for task, info in schedule.items():
    pos = info["position"]
    side = info["side"]
    start = info["start"]
    finish = info["finish"]

    if task_sides[task] not in ("E", side):
        violations.append(
            f"Task {task}: invalid operation side"
        )

    if start < 0 or finish > cycle_time:
        violations.append(
            f"Task {task}: cycle-time violation"
        )

    if finish - start != task_times[task]:
        violations.append(
            f"Task {task}: incorrect processing duration"
        )

    for predecessor in graph.predecessors(task):
        if predecessor not in schedule:
            violations.append(
                f"Task {task}: predecessor "
                f"{predecessor} is missing"
            )
            continue

        pred = schedule[predecessor]

        if pred["position"] > pos:
            violations.append(
                f"Task {task}: predecessor {predecessor} "
                f"is at a later position"
            )

        elif (
            pred["position"] == pos
            and pred["finish"] > start
        ):
            violations.append(
                f"Task {task}: starts before predecessor "
                f"{predecessor} finishes"
            )

for pos in range(1, position):
    for side in ["L", "R"]:
        intervals = sorted(
            [
                (info["start"], info["finish"], task)
                for task, info in schedule.items()
                if info["position"] == pos
                and info["side"] == side
            ]
        )

        for previous, current in zip(
            intervals, intervals[1:]
        ):
            if previous[1] > current[0]:
                violations.append(
                    f"Position {pos}, side {side}: "
                    f"tasks {previous[2]} and "
                    f"{current[2]} overlap"
                )

print("Total violations:", len(violations))

if violations:
    for violation in violations:
        print(violation)
else:
    print("Schedule passed all validation checks")

print("\nASSEMBLY LINE PERFORMANCE")

total_workload = sum(task_times[t] for t in schedule)

total_positions = position - 1
total_workstations = total_positions * 2

available_capacity = total_workstations * cycle_time

total_idle_time = available_capacity - total_workload

line_efficiency = (
    total_workload / available_capacity
) * 100

balance_delay = 100 - line_efficiency

print("Total workload:", total_workload, "seconds")
print("Assembly positions:", total_positions)
print("Workstation slots:", total_workstations)
print("Available capacity:", available_capacity, "seconds")
print("Total idle time:", total_idle_time, "seconds")
print(f"Line efficiency: {line_efficiency:.2f}%")
print(f"Balance delay: {balance_delay:.2f}%")



def run_fifo(graph, task_times, task_sides, cycle_time):
    fifo_schedule = {}
    fifo_assigned = set()
    fifo_position = 1

    while len(fifo_assigned) < graph.number_of_nodes():
        side_finish = {"L": 0, "R": 0}
        tasks_this_position = 0

        while True:
            eligible = [
                task for task in graph.nodes()
                if task not in fifo_assigned
                and all(
                    predecessor in fifo_assigned
                    for predecessor in graph.predecessors(task)
                )
            ]

            # FIFO baseline:
            # chooses the lowest task ID first.
            eligible.sort()

            selected = None

            for task in eligible:
                possible = []

                for side in ["L", "R"]:
                    if task_sides[task] not in ("E", side):
                        continue

                    predecessor_finish = max(
                        (
                            fifo_schedule[p]["finish"]
                            for p in graph.predecessors(task)
                            if fifo_schedule[p]["position"]
                            == fifo_position
                        ),
                        default=0
                    )

                    start = max(
                        side_finish[side],
                        predecessor_finish
                    )

                    finish = start + task_times[task]

                    if finish <= cycle_time:
                        possible.append(
                            (finish, side, start)
                        )

                if possible:
                    finish, side, start = min(possible)
                    selected = (
                        task, side, start, finish
                    )
                    break

            if selected is None:
                break

            task, side, start, finish = selected

            fifo_schedule[task] = {
                "position": fifo_position,
                "side": side,
                "start": start,
                "finish": finish
            }

            fifo_assigned.add(task)
            side_finish[side] = finish
            tasks_this_position += 1

        if tasks_this_position == 0:
            raise RuntimeError(
                "FIFO could not assign any tasks at "
                f"position {fifo_position}"
            )

        fifo_position += 1

    return fifo_schedule, fifo_position - 1


fifo_schedule, fifo_positions = run_fifo(
    graph, task_times, task_sides, cycle_time
)

fifo_workload = sum(
    task_times[task] for task in fifo_schedule
)

fifo_capacity = fifo_positions * 2 * cycle_time

fifo_idle = fifo_capacity - fifo_workload

fifo_efficiency = (
    fifo_workload / fifo_capacity
) * 100

print("\nRPW VS FIFO COMPARISON")

print(f"RPW assembly positions: {total_positions}")
print(f"FIFO assembly positions: {fifo_positions}")

print(f"RPW efficiency: {line_efficiency:.2f}%")
print(f"FIFO efficiency: {fifo_efficiency:.2f}%")

print(f"RPW idle capacity: {total_idle_time}s")
print(f"FIFO idle capacity: {fifo_idle}s")

print(
    "FIFO tasks assigned:",
    len(fifo_schedule),
    "/", graph.number_of_nodes()
)

import matplotlib.pyplot as plt
import numpy as np

labels = ["Electric RPW", "Electric FIFO",
          "Fuel RPW", "Fuel FIFO"]

positions = [8, 8, 8, 9]
efficiencies = [70.42, 70.42, 76.25, 67.78]
idle_times = [284, 284, 228, 348]

output_dir = Path(__file__).parent / "results"
output_dir.mkdir(exist_ok=True)

# Graph 1: Assembly positions
plt.figure(figsize=(9, 5))
plt.bar(labels, positions)
plt.ylabel("Number of assembly positions")
plt.title("Assembly Positions: RPW vs Baseline")
plt.ylim(0, 11)
plt.tight_layout()
plt.savefig(output_dir / "assembly_positions.png", dpi=300)
plt.show()

# Graph 2: Line efficiency
plt.figure(figsize=(9, 5))
plt.bar(labels, efficiencies)
plt.ylabel("Line efficiency (%)")
plt.title("Line Efficiency: RPW vs Baseline")
plt.ylim(0, 100)
plt.tight_layout()
plt.savefig(output_dir / "line_efficiency.png", dpi=300)
plt.show()

# Graph 3: Idle capacity
plt.figure(figsize=(9, 5))
plt.bar(labels, idle_times)
plt.ylabel("Idle capacity (seconds per cycle)")
plt.title("Idle Capacity: RPW vs Baseline")
plt.tight_layout()
plt.savefig(output_dir / "idle_capacity.png", dpi=300)
plt.show()

print("\nAll three graphs saved in the results folder.")
