# -*- coding: utf-8 -*-
"""이벤트 기반 시뮬레이션을 위한 최소 스케줄러."""
from __future__ import annotations

import heapq
import itertools
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

EventCallback = Callable[[], None]


@dataclass(order=True)
class _ScheduledEvent:
    sort_index: Tuple[int, int] = field(init=False, repr=False)
    timestamp: int
    order: int
    callback: EventCallback = field(compare=False)

    def __post_init__(self) -> None:
        self.sort_index = (self.timestamp, self.order)


class EventScheduler:
    """단순 힙 기반 이벤트 스케줄러."""

    def __init__(self, *, logger: Optional[logging.Logger] = None) -> None:
        self._queue: List[_ScheduledEvent] = []
        self._now: int = 0
        self._counter = itertools.count()
        self.logger = logger or logging.getLogger(__name__)

    @property
    def now(self) -> int:
        """현재 시뮬레이터 시간이자 마지막으로 실행된 이벤트 타임스탬프."""

        return self._now

    def schedule(self, *, timestamp: int, callback: EventCallback) -> int:
        """주어진 시각에 콜백을 실행하도록 예약한다."""

        if timestamp < self._now:
            raise ValueError("timestamp는 현재 시각보다 작을 수 없습니다.")

        order = next(self._counter)
        event = _ScheduledEvent(timestamp=timestamp, order=order, callback=callback)
        heapq.heappush(self._queue, event)
        self.logger.debug(
            "event.schedule",
            extra={
                "timestamp": timestamp,
                "callback": getattr(callback, "__qualname__", str(callback)),
                "order": order,
            },
        )
        return order

    def schedule_after(self, *, delay: int, callback: EventCallback) -> int:
        """현재 시각으로부터 delay 만큼 이후에 콜백을 예약한다."""

        if delay < 0:
            raise ValueError("delay는 음수가 될 수 없습니다.")
        return self.schedule(timestamp=self._now + delay, callback=callback)

    def run(self, *, until: Optional[int] = None) -> None:
        """예약된 이벤트를 실행하며 시간 축을 진행한다."""

        if until is not None and until < self._now:
            raise ValueError("until은 현재 시각보다 작을 수 없습니다.")

        while self._queue:
            next_event = self._queue[0]
            if until is not None and next_event.timestamp > until:
                self._now = until
                return

            event = heapq.heappop(self._queue)
            self._now = event.timestamp
            self.logger.debug(
                "event.run",
                extra={
                    "timestamp": self._now,
                    "callback": getattr(
                        event.callback, "__qualname__", str(event.callback)
                    ),
                    "order": event.order,
                },
            )
            event.callback()

        if until is not None:
            self._now = until


__all__ = ["EventScheduler"]
