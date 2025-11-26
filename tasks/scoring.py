from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

DEFAULT_STRATEGY = "smart_balance"
STRATEGY_CHOICES = (
    "fastest_wins",
    "high_impact",
    "deadline_driven",
    "smart_balance",
)
MAX_URGENCY_DAYS = 30


@dataclass(frozen=True)
class TaskData:
    id: int
    title: str
    due_date: Optional[date]
    estimated_hours: float
    importance: int
    dependencies: Tuple[int, ...]


def parse_tasks(payload: Iterable[dict]) -> List[TaskData]:
    tasks: List[TaskData] = []
    for idx, raw in enumerate(payload, start=1):
        due_value = raw.get("due_date")
        due = _coerce_date(due_value)
        task_id = raw.get("id") or idx

        tasks.append(
            TaskData(
                id=task_id,
                title=raw["title"],
                due_date=due,
                estimated_hours=float(raw["estimated_hours"]),
                importance=int(raw["importance"]),
                dependencies=tuple(raw.get("dependencies", [])),
            )
        )
    return tasks


def _coerce_date(value: Optional[object]) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def compute_urgency(due: Optional[date], today: Optional[date] = None) -> Tuple[float, Optional[int]]:
    today = today or date.today()
    if not due:
        return 0.1, None

    days_left = (due - today).days
    if days_left < 0:
        return 1.0, days_left

    urgency = max(0.0, 1 - (min(days_left, MAX_URGENCY_DAYS) / MAX_URGENCY_DAYS))
    return urgency, days_left


def compute_importance(value: int) -> float:
    return min(max(value / 10.0, 0.0), 1.0)


def compute_quick_win(hours: float) -> float:
    capped = min(max(hours, 0.0), 8.0)
    penalty = capped / 8.0
    return 1 - penalty


def build_dependency_graph(tasks: List[TaskData]) -> Tuple[Dict[int, List[int]], Dict[int, int]]:
    adjacency: Dict[int, List[int]] = {task.id: [] for task in tasks}
    dependent_counts: Dict[int, int] = {task.id: 0 for task in tasks}

    for task in tasks:
        for dependency in task.dependencies:
            adjacency.setdefault(dependency, []).append(task.id)
            dependent_counts[dependency] = dependent_counts.get(dependency, 0) + 1

    return adjacency, dependent_counts


def find_cycles(graph: Dict[int, List[int]]) -> Set[int]:
    visited: Set[int] = set()
    stack: Set[int] = set()
    cycle_nodes: Set[int] = set()

    def dfs(node: int):
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in stack:
                cycle_nodes.update(stack)
        stack.remove(node)

    for node in graph.keys():
        if node not in visited:
            dfs(node)

    return cycle_nodes


def score_tasks(tasks_payload: List[dict], strategy: str = DEFAULT_STRATEGY) -> Dict[str, object]:
    if strategy not in STRATEGY_CHOICES:
        raise ValueError(f"Unknown strategy '{strategy}'.")

    parsed_tasks = parse_tasks(tasks_payload)
    graph, dependents = build_dependency_graph(parsed_tasks)
    cycle_nodes = find_cycles(graph)
    max_dep = max(dependents.values()) if dependents else 1

    scored_tasks: List[Dict[str, object]] = []
    today = date.today()

    for task in parsed_tasks:
        urgency, days_left = compute_urgency(task.due_date, today)
        importance_norm = compute_importance(task.importance)
        quick_win = compute_quick_win(task.estimated_hours)
        num_dependents = dependents.get(task.id, 0)
        dep_score = (num_dependents / max_dep) if max_dep else 0.0

        components = {
            "urgency": round(urgency, 4),
            "importance_norm": round(importance_norm, 4),
            "quick_win": round(quick_win, 4),
            "dep_score": round(dep_score, 4),
            "num_dependents": num_dependents,
            "days_left": days_left,
        }

        base_score = STRATEGY_FUNCTIONS[strategy](components)
        cycle_issue = task.id in cycle_nodes
        if cycle_issue:
            base_score *= 0.2

        score = round(base_score * 100, 2)
        explanation = build_explanation(task, components, cycle_issue)

        scored_tasks.append(
            {
                "id": task.id,
                "title": task.title,
                "due_date": task.due_date,
                "estimated_hours": task.estimated_hours,
                "importance": task.importance,
                "dependencies": list(task.dependencies),
                "score": score,
                "explanation": explanation,
                "cycle_issue": cycle_issue,
                "components": components,
            }
        )

    scored_tasks.sort(key=lambda entry: entry["score"], reverse=True)
    for idx, item in enumerate(scored_tasks, start=1):
        item["rank"] = idx

    summary = build_summary(scored_tasks, strategy)
    return {"strategy": strategy, "tasks": scored_tasks, "summary": summary}


def build_summary(tasks: List[Dict[str, object]], strategy: str) -> Dict[str, object]:
    average_score = round(
        sum(task["score"] for task in tasks) / len(tasks), 2
    ) if tasks else 0.0

    return {
        "strategy": strategy,
        "total_tasks": len(tasks),
        "average_score": average_score,
        "top_titles": [task["title"] for task in tasks[:3]],
    }


def build_explanation(task: TaskData, components: Dict[str, float], cycle_issue: bool) -> str:
    parts: List[str] = []

    urgency = components["urgency"]
    days_left = components["days_left"]

    if task.due_date is None:
        parts.append("No deadline (low urgency)")
    else:
        if days_left is not None:
            if days_left < 0:
                due_text = f"overdue by {abs(days_left)} day(s)"
            elif days_left == 0:
                due_text = "due today"
            else:
                due_text = f"due in {days_left} day(s)"
        else:
            due_text = "no due data"

        if urgency >= 0.8:
            urgency_desc = "Very urgent"
        elif urgency >= 0.5:
            urgency_desc = "Moderately urgent"
        else:
            urgency_desc = "Low urgency"
        parts.append(f"{urgency_desc} ({due_text})")

    parts.append(f"Importance {task.importance}/10")

    quick_win = components["quick_win"]
    if quick_win >= 0.7:
        parts.append(f"Quick win ({task.estimated_hours:g}h)")
    elif quick_win <= 0.3:
        parts.append(f"Higher effort ({task.estimated_hours:g}h)")

    num_dependents = components["num_dependents"]
    if num_dependents > 0:
        parts.append(f"Blocks {num_dependents} other task(s)")

    if cycle_issue:
        parts.append("Part of dependency cycle")

    return "; ".join(parts)


def score_fastest(components: Dict[str, float]) -> float:
    return (
        0.6 * components["quick_win"]
        + 0.2 * components["importance_norm"]
        + 0.2 * components["urgency"]
    )


def score_high_impact(components: Dict[str, float]) -> float:
    return (
        0.7 * components["importance_norm"]
        + 0.2 * components["urgency"]
        + 0.1 * components["dep_score"]
    )


def score_deadline(components: Dict[str, float]) -> float:
    return (
        0.7 * components["urgency"]
        + 0.2 * components["importance_norm"]
        + 0.1 * components["quick_win"]
    )


def score_smart(components: Dict[str, float]) -> float:
    return (
        0.35 * components["urgency"]
        + 0.35 * components["importance_norm"]
        + 0.15 * components["quick_win"]
        + 0.15 * components["dep_score"]
    )


STRATEGY_FUNCTIONS = {
    "fastest_wins": score_fastest,
    "high_impact": score_high_impact,
    "deadline_driven": score_deadline,
    "smart_balance": score_smart,
}

