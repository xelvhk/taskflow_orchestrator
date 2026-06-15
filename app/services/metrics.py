from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.repositories import TaskRepository


class MetricsService:
    def __init__(self, session: Session) -> None:
        self.tasks = TaskRepository(session)

    def render_prometheus(self) -> str:
        lines = [
            "# HELP taskflow_tasks_total Current tasks by type and status.",
            "# TYPE taskflow_tasks_total gauge",
        ]
        for task_type, status, count in self.tasks.count_by_type_and_status():
            lines.append(
                f'taskflow_tasks_total{{type="{task_type}",status="{status}"}} {count}'
            )

        lines.extend(
            [
                "# HELP taskflow_task_attempts_total Task attempts by type and status.",
                "# TYPE taskflow_task_attempts_total counter",
            ]
        )
        for task_type, status, count in self.tasks.attempt_count_by_type_and_status():
            lines.append(
                f'taskflow_task_attempts_total{{type="{task_type}",status="{status}"}} {count}'
            )

        lines.extend(
            [
                "# HELP taskflow_task_attempt_duration_ms_avg Average finished attempt duration.",
                "# TYPE taskflow_task_attempt_duration_ms_avg gauge",
            ]
        )
        for task_type, average in self.tasks.average_attempt_duration_ms_by_type():
            lines.append(
                f'taskflow_task_attempt_duration_ms_avg{{type="{task_type}"}} {average:.2f}'
            )

        lines.extend(
            [
                "# HELP taskflow_task_queue_latency_ms_avg "
                "Average time from task creation to first attempt.",
                "# TYPE taskflow_task_queue_latency_ms_avg gauge",
            ]
        )
        for task_type, average in average_by_type(
            self.tasks.first_attempt_queue_latencies_ms_by_type()
        ).items():
            lines.append(f'taskflow_task_queue_latency_ms_avg{{type="{task_type}"}} {average:.2f}')

        return "\n".join(lines) + "\n"


def average_by_type(values: list[tuple[str, int]]) -> dict[str, float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for task_type, value in values:
        grouped[task_type].append(value)
    return {
        task_type: sum(type_values) / len(type_values)
        for task_type, type_values in grouped.items()
    }
