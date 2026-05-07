"""Tests for the OperationTimer / BatchTimingReport utilities."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from _shared.core.utils.timing import (
    BatchTimingReport,
    OperationTimer,
    TimingReport,
    timed,
)


def test_measure_accumulates_duration():
    timer = OperationTimer(url="https://example.com", blog_id="x")
    timer.start()
    with timer.measure("gsc_fetch"):
        time.sleep(0.05)
    timer.stop()

    d = timer.to_dict()
    assert "gsc_fetch" in d["operations"]
    rec = d["operations"]["gsc_fetch"]
    assert rec["duration_sec"] >= 0.04  # lower bound tolerant to jitter
    assert len(rec["started_at"]) == 5 and rec["started_at"][2] == ":"
    assert len(rec["ended_at"]) == 5
    assert d["total_duration_sec"] >= rec["duration_sec"]


def test_same_label_accumulates():
    timer = OperationTimer()
    timer.start()
    with timer.measure("sheets_write"):
        time.sleep(0.02)
    with timer.measure("sheets_write"):
        time.sleep(0.02)
    timer.stop()

    rec = timer.to_dict()["operations"]["sheets_write"]
    assert rec["duration_sec"] >= 0.03  # two ~20ms windows, allowing jitter


def test_timed_context_none_safe():
    # timer=None must not error
    with timed(None, "gsc_fetch"):
        pass

    timer = OperationTimer()
    timer.start()
    with timed(timer, "gsc_fetch"):
        time.sleep(0.01)
    timer.stop()
    assert "gsc_fetch" in timer.to_dict()["operations"]


def test_timing_report_dump(tmp_path: Path):
    timer = OperationTimer(url="https://a", blog_id="b", row_index=3)
    timer.start()
    with timer.measure("x"):
        pass
    timer.stop()

    path = tmp_path / "out.json"
    TimingReport.dump(timer, path)
    data = json.loads(path.read_text())
    assert data["url"] == "https://a"
    assert data["row_index"] == 3
    assert "x" in data["operations"]


def test_batch_aggregate_and_summary(tmp_path: Path):
    report = BatchTimingReport(blog_id="b", source_sheet="GSC_Perfs", row_range="2:3")
    report.start()
    for url in ("https://a", "https://b"):
        t = OperationTimer(url=url, blog_id="b")
        t.start()
        with t.measure("gsc_fetch"):
            time.sleep(0.02)
        with t.measure("sheets_write"):
            time.sleep(0.01)
        t.stop()
        report.add(t)
    report.stop()

    agg = report.aggregate()
    assert "gsc_fetch" in agg
    assert "sheets_write" in agg
    assert "other" in agg
    assert agg["gsc_fetch"]["total_sec"] >= 0.03

    out = tmp_path / "batch.json"
    report.dump(out)
    data = json.loads(out.read_text())
    assert data["urls_count"] == 2
    assert data["source"]["sheet"] == "GSC_Perfs"
    assert "aggregate" in data and "per_url" in data

    summary = report.render_console_summary()
    assert "Benchmark Summary" in summary
    assert "gsc_fetch" in summary
