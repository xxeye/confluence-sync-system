# tests/test_dirty_watcher.py
"""
測試 ProjectInstance._on_file_change
A 方案：dirty + 合併觸發（Timer window）

測試目標：
1) 多次連續檔案事件 → 合併為一次 sync
2) sync_lock 被占用時 → 不丟事件，會排 retry（但不會在測試中無限重試）
3) sync 進行中再有事件 → sync 結束後補跑「一輪」
"""

import threading
import pytest

from multi_project_manager import ProjectInstance


# ----------------------------------------------------------------------
# 測試用假物件
# ----------------------------------------------------------------------

class DummyLogger:
    def __init__(self):
        self.records = []

    def info(self, icon, msg, **kwargs):
        self.records.append(("info", icon, msg))

    def warning(self, icon, msg, **kwargs):
        self.records.append(("warning", icon, msg))

    def error(self, icon, msg, **kwargs):
        self.records.append(("error", icon, msg))


class DummyEngine:
    def __init__(self, on_run=None):
        self.calls = []
        self.on_run = on_run

    def run_sync(self, is_startup=False, log_reason="Sync", dry_run=False, notes_dirty=False):
        self.calls.append((is_startup, log_reason, dry_run))
        if self.on_run:
            self.on_run()

    def run_notes_only_sync(self, log_reason="Notes Update"):
        pass


class FakeTimer:
    """
    可控 Timer：
    - start() 不等時間，只排入 queue
    - 測試端自己決定 fire() 何時執行
    """
    timers = []

    def __init__(self, delay, func):
        self.delay = delay
        self.func = func
        self.cancelled = False
        self.daemon = False

    def cancel(self):
        self.cancelled = True

    def start(self):
        FakeTimer.timers.append(self)

    def fire(self):
        if not self.cancelled:
            self.func()


def fire_next_timer():
    """只 fire 下一個 timer（避免 lock busy 情境下無限追 timer）"""
    assert FakeTimer.timers, "No timers to fire"
    t = FakeTimer.timers.pop(0)
    t.fire()


def fire_all_current_timers():
    """
    fire「當下已排入 queue」的 timers（不包含 fire 過程中新排的）。
    用來模擬：合併窗口到期後、或某個階段的 timer 全部跑完。
    """
    current = FakeTimer.timers[:]
    FakeTimer.timers.clear()
    for t in current:
        t.fire()


def assert_timer_count_at_least(n: int):
    assert len(FakeTimer.timers) >= n, f"Expected at least {n} timers, got {len(FakeTimer.timers)}"


# ----------------------------------------------------------------------
# pytest fixtures
# ----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_threading_timer(monkeypatch):
    FakeTimer.timers.clear()
    monkeypatch.setattr(threading, "Timer", FakeTimer)
    yield
    FakeTimer.timers.clear()


@pytest.fixture
def dummy_project():
    """
    建立一個「繞過 __init__」的 ProjectInstance：
    - 不讀 config
    - 不連 Confluence
    - 只留下 _on_file_change 需要的欄位
    """
    p = ProjectInstance.__new__(ProjectInstance)
    p.project_id = "P1"
    p.sync_lock = threading.Lock()
    p.logger = DummyLogger()
    p.engine = DummyEngine()
    return p


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_multiple_events_merge_into_one_sync(dummy_project):
    """
    多次事件 → 合併為一次 sync
    """
    p = dummy_project

    p._on_file_change()
    p._on_file_change()
    p._on_file_change()

    # 合併窗口到期：只需要把「當下」排到的 timer 跑掉
    fire_all_current_timers()

    assert len(p.engine.calls) == 1
    assert p.engine.calls[0][1] == "Watcher Sync (dirty)"


def test_lock_busy_will_retry_not_drop(dummy_project):
    """
    sync_lock 被占用時，不會丟事件，會排 retry
    （測試端不要把 retry 全部立刻 fire 掉，否則會無限重試）
    """
    p = dummy_project

    # 模擬「正在同步中」
    p.sync_lock.acquire()

    p._on_file_change()

    # 1) 先 fire 合併窗口那顆 timer：它會發現 lock 忙 → 排一顆 retry timer
    fire_next_timer()

    # 仍然不能同步
    assert len(p.engine.calls) == 0

    # 應該已經排了 retry timer（至少 1 顆）
    assert_timer_count_at_least(1)

    # 2) 放掉 lock
    p.sync_lock.release()

    # 3) fire 下一顆（retry timer）：這次應該能同步成功
    fire_next_timer()

    assert len(p.engine.calls) == 1
    assert p.engine.calls[0][1] == "Watcher Sync (dirty)"


def test_change_during_sync_triggers_followup_sync():
    """
    sync 進行中再觸發變更 → sync 結束後補跑「一輪」

    注意：on_run 只能 dirty 一次，否則每輪都 dirty 會變成無限補跑。
    """
    trigger_count = {"n": 0}

    def on_run():
        # 只在第一次 run_sync 的途中再觸發一次變更
        if trigger_count["n"] == 0:
            trigger_count["n"] += 1
            p._on_file_change()

    p = ProjectInstance.__new__(ProjectInstance)
    p.project_id = "P1"
    p.sync_lock = threading.Lock()
    p.logger = DummyLogger()
    p.engine = DummyEngine(on_run=on_run)

    p._on_file_change()

    # 第一次合併窗口到期 → 跑第一輪 sync（期間又 dirty 一次）
    fire_all_current_timers()

    # 此時應該已排「補跑」的下一輪 timer（合併窗口）
    assert_timer_count_at_least(1)

    # 第二次合併窗口到期 → 跑第二輪 sync（這次 on_run 不再 dirty）
    fire_all_current_timers()

    assert len(p.engine.calls) == 2
    assert all(call[1] == "Watcher Sync (dirty)" for call in p.engine.calls)
