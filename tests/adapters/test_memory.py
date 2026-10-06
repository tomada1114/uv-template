"""Behavior only the in-memory repository has to prove: its lock."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from my_app.adapters.memory import InMemoryTodoRepository
from my_app.core.models import TodoDraft

CONCURRENT_ADDS = 200
WORKERS = 8


def test_in_memory_repository_concurrent_adds_assign_unique_ids(fixed_now):
    repository = InMemoryTodoRepository()
    drafts = [TodoDraft(f"todo {n}", fixed_now) for n in range(CONCURRENT_ADDS)]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        added = list(pool.map(repository.add, drafts))

    ids = sorted(todo.id for todo in added)
    assert ids == list(range(1, CONCURRENT_ADDS + 1))
    assert len(repository.list_all()) == CONCURRENT_ADDS
