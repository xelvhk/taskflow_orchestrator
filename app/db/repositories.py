from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Task, TaskAttempt, TaskStatus, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_api_key_hash(self, api_key_hash: str) -> User | None:
        return self.session.scalar(select(User).where(User.api_key_hash == api_key_hash))

    def create(self, *, name: str, api_key_hash: str) -> User:
        user = User(name=name, api_key_hash=api_key_hash)
        self.session.add(user)
        self.session.flush()
        return user


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, task: Task) -> Task:
        self.session.add(task)
        self.session.flush()
        return task

    def get_for_user(self, *, task_id: str, user_id: str) -> Task | None:
        return self.session.scalar(
            select(Task)
            .options(selectinload(Task.attempts))
            .where(Task.id == task_id, Task.user_id == user_id)
        )

    def get_by_id(self, task_id: str) -> Task | None:
        return self.session.scalar(
            select(Task).options(selectinload(Task.attempts)).where(Task.id == task_id)
        )

    def get_by_idempotency_key(self, *, user_id: str, idempotency_key: str) -> Task | None:
        return self.session.scalar(
            select(Task)
            .options(selectinload(Task.attempts))
            .where(Task.user_id == user_id, Task.idempotency_key == idempotency_key)
        )

    def list_for_user(
        self,
        *,
        user_id: str,
        status: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> list[Task]:
        query: Select[tuple[Task]] = (
            select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        )
        if status is not None:
            query = query.where(Task.status == status)
        return list(self.session.scalars(query.limit(limit).offset(offset)))

    def count_for_user(self, *, user_id: str, status: TaskStatus | None) -> int:
        query = select(Task).where(Task.user_id == user_id)
        if status is not None:
            query = query.where(Task.status == status)
        return len(list(self.session.scalars(query)))

    def add_attempt(self, attempt: TaskAttempt) -> TaskAttempt:
        self.session.add(attempt)
        self.session.flush()
        return attempt
