
from pathlib import Path
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

# Load the same dataset used in the main experiment
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

task_times = dict(zip(df["Task_ID"], df["Task_Time"]))
task_sides = dict(zip(df["Task_ID"], df["Operation_Side"]))


def balance_line(graph, cycle_time, method):
    schedule = {}
    assigned = set()
    position = 1

    weights = {}

    for task in graph.nodes():
        successors = nx.descendants(graph, task)
        weights[task] = task_times[task] + sum(
            task_times[s] for s in successors
        )

    while len(assigned) < graph.number_of_nodes():
        side_finish = {"L": 0, "R": 0}
        tasks_this_position = 0

        while True:
            eligible = [
                task for task in graph.nodes()
                if task not in assigned
                and all(
                    p in assigned
                    for p in graph.predecessors(task)
                )
            ]

            if method == "RPW":
                eligible.sort(
                    key=lambda task: (-weights[task], task)
                )
            else:
                eligible.sort()

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
                f"No task fits at position {position}"
            )

        position += 1

    positions = position - 1
    workload = sum(task_times[t] for t in schedule)
    capacity = positions * 2 * cycle_time

    return {
        "positions": positions,
        "efficiency": workload / capacity * 100,
        "idle": capacity - workload,
        "tasks_assigned": len(schedule),
        "schedule": schedule
    }


def validate_schedule(graph, schedule, cycle_time):
    violations = []

    if set(schedule) != set(graph.nodes()):
        violations.append("Missing or extra tasks")

    for task, info in schedule.items():
        start = info["start"]
        finish = info["finish"]
        position = info["position"]
        side = info["side"]

        # Check operation-side compatibility
        if task_sides[task] not in ("E", side):
            violations.append(
                f"Task {task}: incorrect operation side"
            )

        # Check processing duration and cycle time
        if start < 0 or finish > cycle_time:
            violations.append(
                f"Task {task}: cycle-time violation"
            )

        if finish - start != task_times[task]:
            violations.append(
                f"Task {task}: incorrect duration"
            )

        # Check precedence relationships
        for predecessor in graph.predecessors(task):
            if predecessor not in schedule:
                violations.append(
                    f"Task {task}: missing predecessor {predecessor}"
                )
                continue

            pred = schedule[predecessor]

            if pred["position"] > position:
                violations.append(
                    f"Task {task}: predecessor at later position"
                )

            elif (
                pred["position"] == position
                and pred["finish"] > start
            ):
                violations.append(
                    f"Task {task}: precedence timing violation"
                )

    # Check overlapping tasks on the same workstation
    positions = {
        info["position"] for info in schedule.values()
    }

    for position in positions:
        for side in ["L", "R"]:
            intervals = sorted(
                [
                    (info["start"], info["finish"], task)
                    for task, info in schedule.items()
                    if info["position"] == position
                    and info["side"] == side
                ]
            )

            for previous, current in zip(
                intervals, intervals[1:]
            ):
                if previous[1] > current[0]:
                    violations.append(
                        f"Position {position}, side {side}: "
                        f"tasks overlap"
                    )

    return violations
results = []

for vehicle, task_sets in [
    ("Electric", ["ET", "PT"]),
    ("Fuel", ["FT", "PT"])
]:
    tasks = df[
        df["Task_Set"].isin(task_sets)
    ]["Task_ID"].tolist()

    graph = G.subgraph(tasks).copy()

    for cycle_time in [50, 60, 70]:
        for method in ["RPW", "Baseline"]:
            result = balance_line(
                graph, cycle_time, method
            )
            violations = validate_schedule(
                graph, result["schedule"], cycle_time
            )

            print(
                f"{vehicle} | {cycle_time}s | {method} | "
                f"Validation violations: {len(violations)}"
            )

            for violation in violations:
                print("  -", violation)
            results.append({
                "Vehicle": vehicle,
                "Cycle_Time": cycle_time,
                "Method": method,
                "Positions": result["positions"],
                "Efficiency": round(
                    result["efficiency"], 2
                ),
                "Idle_Time": result["idle"],
                "Tasks_Assigned": result["tasks_assigned"]
            })

results_df = pd.DataFrame(results)

print("\nCYCLE TIME TESTING RESULTS")
print(results_df.to_string(index=False))

output_dir = Path(__file__).parent / "results"
output_dir.mkdir(exist_ok=True)

results_df.to_csv(
    output_dir / "cycle_time_results.csv",
    index=False
)

# Plot efficiency against cycle time
plt.figure(figsize=(9, 5))

for vehicle in ["Electric", "Fuel"]:
    for method in ["RPW", "Baseline"]:
        subset = results_df[
            (results_df["Vehicle"] == vehicle)
            & (results_df["Method"] == method)
        ]

        plt.plot(
            subset["Cycle_Time"],
            subset["Efficiency"],
            marker="o",
            label=f"{vehicle} {method}"
        )

plt.xlabel("Cycle time (seconds)")
plt.ylabel("Line efficiency (%)")
plt.title("Effect of Cycle Time on Line Efficiency")
plt.legend()
plt.grid(True)
plt.tight_layout()

plt.savefig(
    output_dir / "cycle_time_efficiency.png",
    dpi=300
)

plt.show()

print("\nResults and graph saved successfully.")
