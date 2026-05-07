"""Operation timing utilities for pipeline benchmarking.

Captures start time (HH:MM), end time (HH:MM) and precise duration (seconds)
for named operations. Results can be dumped to JSON and aggregated across a
batch of runs.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger("Timing")


@contextmanager
def timed(timer: "Optional[OperationTimer]", label: str) -> Iterator[None]:
    """None-safe timing context. Use to wrap call sites without verbose branching."""
    if timer is None:
        yield
        return
    with timer.measure(label):
        yield


@dataclass
class OperationRecord:
    label: str
    started_at: str
    ended_at: str
    duration_sec: float

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": round(self.duration_sec, 3),
        }


class OperationTimer:
    """Per-URL timer. Accumulates named operations via a context manager."""

    def __init__(self, url: str = "", blog_id: str = "", row_index: Optional[int] = None):
        self.url = url
        self.blog_id = blog_id
        self.row_index = row_index
        self._records: Dict[str, OperationRecord] = {}
        self._process_started_perf: Optional[float] = None
        self._process_ended_perf: Optional[float] = None
        self.process_started_at: Optional[str] = None
        self.process_ended_at: Optional[str] = None
        self.errors: List[str] = []
        self.success: bool = True
        self.output_html: Optional[str] = None

    def start(self) -> None:
        self._process_started_perf = time.perf_counter()
        self.process_started_at = datetime.now().strftime("%H:%M")

    def stop(self) -> None:
        self._process_ended_perf = time.perf_counter()
        self.process_ended_at = datetime.now().strftime("%H:%M")

    @contextmanager
    def measure(self, label: str) -> Iterator[None]:
        """Measure duration of the wrapped block and store it under `label`.

        Subsequent calls with the same label accumulate durations but keep the
        earliest start and latest end (useful for sheets_write called multiple
        times per URL).
        """
        started = time.perf_counter()
        started_hhmm = datetime.now().strftime("%H:%M")
        try:
            yield
        finally:
            duration = time.perf_counter() - started
            ended_hhmm = datetime.now().strftime("%H:%M")
            existing = self._records.get(label)
            if existing is None:
                self._records[label] = OperationRecord(
                    label=label,
                    started_at=started_hhmm,
                    ended_at=ended_hhmm,
                    duration_sec=duration,
                )
            else:
                existing.ended_at = ended_hhmm
                existing.duration_sec += duration
            logger.info(
                "[TIMING] %s: %s → %s (%.2fs)",
                label, started_hhmm, ended_hhmm, duration,
            )

    @property
    def total_duration_sec(self) -> float:
        if self._process_started_perf is None or self._process_ended_perf is None:
            return 0.0
        return self._process_ended_perf - self._process_started_perf

    @property
    def measured_sec(self) -> float:
        return sum(r.duration_sec for r in self._records.values())

    @property
    def other_sec(self) -> float:
        return max(0.0, self.total_duration_sec - self.measured_sec)

    def to_dict(self) -> dict:
        return {
            "blog_id": self.blog_id,
            "url": self.url,
            "row_index": self.row_index,
            "process_started_at": self.process_started_at,
            "process_ended_at": self.process_ended_at,
            "total_duration_sec": round(self.total_duration_sec, 3),
            "operations": {k: v.to_dict() for k, v in self._records.items()},
            "other_sec": round(self.other_sec, 3),
            "output_html": self.output_html,
            "success": self.success,
            "errors": self.errors,
        }


class TimingReport:
    """Thin helper to dump a single OperationTimer to a JSON file."""

    @staticmethod
    def dump(timer: OperationTimer, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(timer.to_dict(), ensure_ascii=False, indent=2))


@dataclass
class BatchTimingReport:
    """Aggregates timers from a batch run."""

    blog_id: str
    source_sheet: str
    row_range: str
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    timers: List[OperationTimer] = field(default_factory=list)
    batch_started_at: Optional[str] = None
    batch_ended_at: Optional[str] = None
    _batch_started_perf: Optional[float] = None
    _batch_ended_perf: Optional[float] = None

    def start(self) -> None:
        self._batch_started_perf = time.perf_counter()
        self.batch_started_at = datetime.now().strftime("%H:%M")

    def stop(self) -> None:
        self._batch_ended_perf = time.perf_counter()
        self.batch_ended_at = datetime.now().strftime("%H:%M")

    def add(self, timer: OperationTimer) -> None:
        self.timers.append(timer)

    @property
    def batch_duration_sec(self) -> float:
        if self._batch_started_perf is None or self._batch_ended_perf is None:
            return 0.0
        return self._batch_ended_perf - self._batch_started_perf

    def aggregate(self) -> Dict[str, dict]:
        labels: Dict[str, List[float]] = {}
        for t in self.timers:
            for label, rec in t._records.items():
                labels.setdefault(label, []).append(rec.duration_sec)
        batch = self.batch_duration_sec or 1.0
        agg = {}
        for label, values in labels.items():
            total = sum(values)
            agg[label] = {
                "total_sec": round(total, 3),
                "avg_sec": round(total / len(values), 3) if values else 0.0,
                "pct_of_batch": round(100.0 * total / batch, 2),
            }
        other_total = sum(t.other_sec for t in self.timers)
        agg["other"] = {
            "total_sec": round(other_total, 3),
            "avg_sec": round(other_total / len(self.timers), 3) if self.timers else 0.0,
            "pct_of_batch": round(100.0 * other_total / batch, 2),
        }
        return agg

    def to_dict(self) -> dict:
        successes = sum(1 for t in self.timers if t.success)
        return {
            "run_id": self.run_id,
            "blog_id": self.blog_id,
            "source": {"sheet": self.source_sheet, "rows": self.row_range},
            "batch_started_at": self.batch_started_at,
            "batch_ended_at": self.batch_ended_at,
            "batch_duration_sec": round(self.batch_duration_sec, 3),
            "urls_count": len(self.timers),
            "urls_success": successes,
            "urls_failed": len(self.timers) - successes,
            "aggregate": self.aggregate(),
            "per_url": [
                {
                    "url": t.url,
                    "row_index": t.row_index,
                    "started_at": t.process_started_at,
                    "ended_at": t.process_ended_at,
                    "duration_sec": round(t.total_duration_sec, 3),
                    "success": t.success,
                }
                for t in self.timers
            ],
        }

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    def render_console_summary(self) -> str:
        agg = self.aggregate()
        lines = []
        lines.append(f"═══ Benchmark Summary — {self.blog_id} ═══")
        lines.append(
            f"Batch: {self.batch_started_at} → {self.batch_ended_at} "
            f"({_fmt_duration(self.batch_duration_sec)})"
        )
        successes = sum(1 for t in self.timers if t.success)
        failed = len(self.timers) - successes
        lines.append(f"URLs: {len(self.timers)} processed, {successes} success, {failed} failed")
        lines.append("")
        lines.append(f"{'Operation':<15} | {'Total':>10} | {'Avg/URL':>9} | {'% of batch':>10}")
        for label in list(agg.keys()):
            d = agg[label]
            lines.append(
                f"{label:<15} | {_fmt_duration(d['total_sec']):>10} | "
                f"{_fmt_duration(d['avg_sec']):>9} | {d['pct_of_batch']:>9.1f}%"
            )
        return "\n".join(lines)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs:02d}s"
