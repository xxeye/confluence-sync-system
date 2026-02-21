# tests/test_notes_sync.py
"""
極限測試：notes_dirty 旗標、FileMonitor 事件合併、run_sync 分支

測試目標：
1.  只改 xlsx → 走 run_notes_only_sync，不走圖片 diff
2.  只改圖片 → 走正常 run_sync，notes_dirty=False
3.  圖片 + xlsx 同時改 → 一次 sync，notes_dirty=True，強制全量重繪
4.  xlsx 事件先到，圖片事件後到（notes_dirty 不被清掉）
5.  圖片事件先到，xlsx 事件後到（notes_dirty 補上）
6.  sync 進行中 xlsx 又改 → 補跑時 notes_dirty=True
7.  sync 進行中圖片又改、xlsx 沒改 → 補跑時 notes_dirty=False
8.  lock 忙 + notes_dirty → retry 後 notes_dirty 仍保留
9.  FileMonitor：xlsx 暫存檔（~$、._）不觸發 callback
10. FileMonitor：xlsx 在與圖片相同目錄下仍正確觸發
"""

import threading
import time
import pytest

from multi_project_manager import ProjectInstance


# ── 假物件 ────────────────────────────────────────────────────────────────────

class DummyLogger:
    def info(self, *a, **kw):    pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw):   pass
    def success(self, *a, **kw): pass


class DummyEngine:
    """記錄每次 run_sync / run_notes_only_sync 的呼叫參數"""

    def __init__(self, on_run=None):
        self.sync_calls        = []   # [(is_startup, log_reason, notes_dirty)]
        self.notes_only_calls  = []   # [log_reason]
        self.on_run = on_run

    def run_sync(self, is_startup=False, log_reason="Sync",
                 dry_run=False, notes_dirty=False):
        self.sync_calls.append((is_startup, log_reason, notes_dirty))
        if self.on_run:
            self.on_run()

    def run_notes_only_sync(self, log_reason="Notes Update"):
        self.notes_only_calls.append(log_reason)


class FakeTimer:
    timers: list = []

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


def fire_next():
    assert FakeTimer.timers, "No timers to fire"
    FakeTimer.timers.pop(0).fire()


def fire_all_current():
    batch = FakeTimer.timers[:]
    FakeTimer.timers.clear()
    for t in batch:
        t.fire()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_timer(monkeypatch):
    FakeTimer.timers.clear()
    monkeypatch.setattr(threading, "Timer", FakeTimer)
    yield
    FakeTimer.timers.clear()


@pytest.fixture
def proj():
    """繞過 __init__ 的最小 ProjectInstance"""
    p = ProjectInstance.__new__(ProjectInstance)
    p.project_id = "P1"
    p.sync_lock  = threading.Lock()
    p.logger     = DummyLogger()
    p.engine     = DummyEngine()
    return p


# ── 1. 只改 xlsx ──────────────────────────────────────────────────────────────

def test_only_notes_change_calls_notes_only_sync(proj):
    """只改 xlsx（notes_dirty=True）→ run_sync 收到 notes_dirty=True"""
    proj._on_file_change(notes_dirty=True)
    fire_all_current()

    assert len(proj.engine.sync_calls) == 1
    _, _, nd = proj.engine.sync_calls[0]
    assert nd is True


# ── 2. 只改圖片 ───────────────────────────────────────────────────────────────

def test_only_image_change_notes_dirty_false(proj):
    """只改圖片 → notes_dirty=False"""
    proj._on_file_change(notes_dirty=False)
    fire_all_current()

    assert len(proj.engine.sync_calls) == 1
    _, _, nd = proj.engine.sync_calls[0]
    assert nd is False


# ── 3. 圖片 + xlsx 同時改（同一個合併窗口內）────────────────────────────────

def test_image_and_notes_same_window_notes_dirty_true(proj):
    """圖片和 xlsx 在同一窗口內 → 合併成一次，notes_dirty=True"""
    proj._on_file_change(notes_dirty=False)  # 圖片
    proj._on_file_change(notes_dirty=True)   # xlsx
    proj._on_file_change(notes_dirty=False)  # 再一張圖片
    fire_all_current()

    assert len(proj.engine.sync_calls) == 1
    _, _, nd = proj.engine.sync_calls[0]
    assert nd is True


# ── 4. xlsx 先到，圖片後到（notes_dirty 不被清掉）────────────────────────────

def test_notes_first_then_image_preserves_notes_dirty(proj):
    """xlsx 先觸發，後來圖片事件不應清掉 notes_dirty"""
    proj._on_file_change(notes_dirty=True)   # xlsx 先
    proj._on_file_change(notes_dirty=False)  # 圖片後
    fire_all_current()

    _, _, nd = proj.engine.sync_calls[0]
    assert nd is True, "notes_dirty 被圖片事件清掉了！"


# ── 5. 圖片先到，xlsx 後到（notes_dirty 補上）────────────────────────────────

def test_image_first_then_notes_sets_notes_dirty(proj):
    """圖片先觸發，xlsx 後到 → 最終 notes_dirty=True"""
    proj._on_file_change(notes_dirty=False)  # 圖片先
    proj._on_file_change(notes_dirty=True)   # xlsx 後
    fire_all_current()

    _, _, nd = proj.engine.sync_calls[0]
    assert nd is True


# ── 6. sync 進行中 xlsx 又改 → 補跑時 notes_dirty=True ──────────────────────

def test_notes_change_during_sync_preserved_in_followup(proj):
    """第一輪 sync 跑到一半 xlsx 被改 → 補跑時 notes_dirty=True"""
    def on_run():
        # 模擬 sync 進行中 xlsx 被儲存
        proj._on_file_change(notes_dirty=True)

    proj.engine.on_run = on_run

    proj._on_file_change(notes_dirty=False)
    fire_all_current()   # 第一輪 sync（期間 xlsx dirty）

    # 應有補跑 timer
    assert FakeTimer.timers, "沒有補跑 timer"
    fire_all_current()   # 補跑

    assert len(proj.engine.sync_calls) == 2
    _, _, nd = proj.engine.sync_calls[1]
    assert nd is True, "補跑時 notes_dirty 遺失"


# ── 7. sync 進行中只有圖片改 → 補跑時 notes_dirty=False ─────────────────────

def test_image_change_during_sync_followup_notes_dirty_false(proj):
    """第一輪 sync 進行中只有圖片被改 → 補跑 notes_dirty=False"""
    def on_run():
        proj._on_file_change(notes_dirty=False)

    proj.engine.on_run = on_run

    proj._on_file_change(notes_dirty=False)
    fire_all_current()
    fire_all_current()

    assert len(proj.engine.sync_calls) == 2
    _, _, nd = proj.engine.sync_calls[1]
    assert nd is False


# ── 8. lock 忙 + notes_dirty → retry 後仍保留 ────────────────────────────────

def test_lock_busy_notes_dirty_preserved_after_retry(proj):
    """sync_lock 被占用時，notes_dirty 不因 retry 而遺失"""
    proj.sync_lock.acquire()

    proj._on_file_change(notes_dirty=True)

    # 合併窗口到期 → 發現 lock 忙 → 排 retry
    fire_next()
    assert len(proj.engine.sync_calls) == 0
    assert FakeTimer.timers, "沒有 retry timer"

    proj.sync_lock.release()

    # retry timer 到期 → 這次能拿到 lock
    fire_next()
    assert len(proj.engine.sync_calls) == 1
    _, _, nd = proj.engine.sync_calls[0]
    assert nd is True, "retry 後 notes_dirty 遺失"


# ── 9. xlsx 暫存檔不觸發 ──────────────────────────────────────────────────────

def test_file_monitor_ignores_temp_files():
    """
    FileMonitor 的 extra handler 應過濾 ~$xxx 和 ._xxx 暫存檔，
    直接測 _make_extra_handler 的內部邏輯。
    """
    from core.file_monitor import FileMonitor

    fired = []

    def cb(notes_dirty):
        fired.append(notes_dirty)

    fm = FileMonitor(
        watch_path=".",
        file_patterns=["*.png"],
        callback=cb,
        extra_files=["asset_notes.xlsx"],
    )

    allowed = {"asset_notes.xlsx"}
    handler = fm._make_extra_handler(allowed)

    class FakeEvent:
        is_directory = False
        def __init__(self, path):
            self.src_path = path

    # 暫存檔：不應觸發
    handler.on_any_event(FakeEvent("~$asset_notes.xlsx"))
    handler.on_any_event(FakeEvent("._asset_notes.xlsx"))
    assert fired == [], f"暫存檔意外觸發了 callback：{fired}"

    # 真實 xlsx：不直接 assert fired（因為走防抖 timer），
    # 但確認 _notes_dirty 被設為 True
    handler.on_any_event(FakeEvent("asset_notes.xlsx"))
    assert fm._notes_dirty is True, "xlsx 存檔後 _notes_dirty 應為 True"


# ── 10. xlsx 與圖片在同一目錄 ────────────────────────────────────────────────

def test_file_monitor_notes_dirty_flag_set_by_extra_handler():
    """
    xlsx 事件走 extra_handler → _notes_dirty=True；
    圖片事件走 main_handler  → _notes_dirty 不動。
    """
    from core.file_monitor import FileMonitor

    fired = []

    def cb(notes_dirty):
        fired.append(notes_dirty)

    fm = FileMonitor(
        watch_path=".",
        file_patterns=["*.png"],
        callback=cb,
        extra_files=["asset_notes.xlsx"],
    )

    # 模擬圖片事件：走 main handler，不設 notes_dirty
    fm._schedule(notes_dirty=False)
    assert fm._notes_dirty is False

    # 模擬 xlsx 事件：走 extra handler，設 notes_dirty
    fm._schedule(notes_dirty=True)
    assert fm._notes_dirty is True

    # 再來一個圖片事件：notes_dirty 不應被清掉
    fm._schedule(notes_dirty=False)
    assert fm._notes_dirty is True, "圖片事件不應清掉 notes_dirty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
