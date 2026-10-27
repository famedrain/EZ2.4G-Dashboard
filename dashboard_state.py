"""Presentation rules shared by the Win32 tray and Tk dashboard (no I/O)."""
from dataclasses import dataclass
from typing import Mapping
import time


LOW_BATTERY = 20


def device_badge(name: str) -> str:
    name = name.casefold()
    for words, label in (
        (("mouse", "鼠标"), "鼠"),
        (("keyboard", "键盘"), "键"),
        (("headset", "headphone", "耳机"), "耳"),
        (("controller", "gamepad", "手柄"), "柄"),
    ):
        if any(word in name for word in words):
            return label
    return "设"


def reading_status(reading) -> str:
    if not reading.present:
        return "未连接"
    if reading.stale:
        return "设备休眠 · 上次电量"
    if reading.status == "unknown_proto":
        return "协议未知"
    if reading.status == "asleep":
        return "设备休眠"
    if reading.ok and reading.level is not None:
        return {"charging": "充电中", "full": "已充满", "wired": "有线模式"}.get(
            reading.status, "已连接")
    return "暂未读到电量"


@dataclass(frozen=True)
class TraySummary:
    total: int
    connected: int
    low: int
    alert_level: int | None
    tooltip: str


def summarize(readings: Mapping) -> TraySummary:
    """Cached/charging/disconnected readings never trigger a low-battery badge."""
    low = [r.level for r in readings.values()
           if r.present and r.ok and not r.stale and r.level is not None
           and r.status not in ("charging", "full", "wired", "asleep", "unplugged", "unknown_proto")
           and r.level <= LOW_BATTERY]
    connected = sum(bool(r.present) for r in readings.values())
    lines = [f"EZ2.4G Dashboard · {connected}/{len(readings)} 台连接"]
    for r in readings.values():
        level = f"{r.level}% · " if r.ok and r.level is not None else ""
        stamp = time.strftime("%H:%M", time.localtime(r.ts)) if r.ts else "--:--"
        name = " ".join((r.name or "设备").split())[:22]
        lines.append(f"{name}：{level}{reading_status(r)}（{stamp}）")
    if not readings:
        lines.append("点击打开 Dashboard，拔插接收器添加设备")
    # NOTIFYICONDATAW stores 128 UTF-16 code units, including the terminator.
    tip = "\n".join(lines)
    if len(tip.encode("utf-16-le")) > 254:
        tip = tip.encode("utf-16-le")[:252].decode("utf-16-le", errors="ignore") + "…"
    return TraySummary(len(readings), connected, len(low), min(low) if low else None, tip)


def flyout_position(anchor, work, size, gap=10):
    """Fit beside a tray rectangle, including top/side taskbars and negative monitors."""
    left, top, right, bottom = work
    ax1, ay1, ax2, ay2 = anchor
    width, height = size
    x = ax2 - width
    if ay1 - height - gap >= top:
        y = ay1 - height - gap
    elif ay2 + height + gap <= bottom:
        y = ay2 + gap
    else:
        y = ay2 - height
        x = ax1 - width - gap if ax1 - width - gap >= left else ax2 + gap
    return (max(left, min(x, right - width)),
            max(top, min(y, bottom - height)))
