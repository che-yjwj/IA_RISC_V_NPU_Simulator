from __future__ import annotations

import pytest

from src.simulator.events import EventScheduler


def test_events_execute_in_timestamp_order() -> None:
    scheduler = EventScheduler()
    executed: list[int] = []

    scheduler.schedule(timestamp=10, callback=lambda: executed.append(2))
    scheduler.schedule(timestamp=5, callback=lambda: executed.append(1))
    scheduler.schedule(timestamp=15, callback=lambda: executed.append(3))

    scheduler.run()

    assert executed == [1, 2, 3]


def test_same_timestamp_respects_insertion_order() -> None:
    scheduler = EventScheduler()
    executed: list[int] = []

    scheduler.schedule(timestamp=10, callback=lambda: executed.append(1))
    scheduler.schedule(timestamp=10, callback=lambda: executed.append(2))
    scheduler.schedule(timestamp=10, callback=lambda: executed.append(3))

    scheduler.run()

    assert executed == [1, 2, 3]


def test_schedule_after_relies_on_current_time() -> None:
    scheduler = EventScheduler()
    trace: list[int] = []

    def first() -> None:
        trace.append(0)
        scheduler.schedule_after(delay=5, callback=lambda: trace.append(2))

    scheduler.schedule(callback=lambda: trace.append(1), timestamp=3)
    scheduler.schedule(callback=first, timestamp=1)

    scheduler.run()

    assert trace == [0, 1, 2]


def test_run_until_advances_time_without_executing_future_events() -> None:
    scheduler = EventScheduler()
    scheduler.schedule(timestamp=10, callback=lambda: None)

    scheduler.run(until=5)

    assert scheduler.now == 5

    # 이벤트는 남아 있고 나중에 실행 가능해야 한다.
    scheduler.run()
    assert scheduler.now == 10


def test_schedule_after_rejects_negative_delay() -> None:
    scheduler = EventScheduler()

    with pytest.raises(ValueError):
        scheduler.schedule_after(delay=-1, callback=lambda: None)

