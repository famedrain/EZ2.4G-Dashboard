import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dashboard_state import (LowBatteryAlerts, clamp_position, device_badge,
                             flyout_position, reading_status, saved_position, summarize)


def reading(**changes):
    values = dict(ok=True, level=75, status="discharging", name="Mouse",
                  present=True, stale=False, ts=1700000000)
    values.update(changes)
    return SimpleNamespace(**values)


class SummaryTests(unittest.TestCase):
    def test_empty_dashboard_remains_discoverable(self):
        summary = summarize({})
        self.assertEqual(summary.total, 0)
        self.assertIsNone(summary.alert_level)
        self.assertIn("Dashboard", summary.tooltip)

    def test_only_fresh_discharging_devices_trigger_low_alert(self):
        samples = {
            "mouse": reading(level=8), "keyboard": reading(level=9),
            "sleep": reading(level=1, stale=True),
            "charging": reading(level=2, status="charging"),
            "offline": reading(level=0, present=False),
            "unknown": reading(level=None, ok=False, status="unknown_proto"),
        }
        summary = summarize(samples)
        self.assertEqual((summary.total, summary.connected, summary.low), (6, 5, 2))
        self.assertEqual(summary.alert_level, 8)
        self.assertEqual(summary.level, 1)  # Ring may use a clearly labelled last value.
        self.assertIn("上次电量", summary.tooltip)

    def test_zero_battery_is_an_alert(self):
        self.assertEqual(summarize({"a": reading(level=0)}).alert_level, 0)

    def test_ring_tracks_minimum_at_all_levels_and_ignores_disconnected(self):
        samples = {"a": reading(level=100), "b": reading(level=69),
                   "off": reading(level=1, present=False)}
        self.assertEqual(summarize(samples).level, 69)
        samples["b"] = reading(level=43)
        self.assertEqual(summarize(samples).level, 43)
        self.assertIsNone(summarize({}).level)

    def test_ten_percent_is_not_low_but_nine_is(self):
        self.assertEqual(summarize({"a": reading(level=10)}).low, 0)
        self.assertEqual(summarize({"a": reading(level=9)}).low, 1)

    def test_low_notification_deduplicates_until_recovery_and_ignores_stale(self):
        alerts = LowBatteryAlerts()
        self.assertEqual(alerts.update({"a": reading(level=10)}), [])
        self.assertEqual(len(alerts.update({"a": reading(level=9)})), 1)
        for level in (8, 9, 10, 9):
            self.assertEqual(alerts.update({"a": reading(level=level)}), [])
        alerts.update({"a": reading(level=12)})
        self.assertEqual(len(alerts.update({"a": reading(level=0)})), 1)
        self.assertEqual(alerts.update({"b": reading(level=1, stale=True)}), [])
        self.assertEqual(alerts.update({"b": reading(level=1, status="charging")}), [])
        self.assertEqual(alerts.update({"b": reading(level=1, present=False)}), [])

    def test_saved_position_validates_and_clamps_after_monitor_removal(self):
        self.assertEqual(saved_position({"x": -1200, "y": 40}), (-1200, 40))
        for value in (None, [], {}, {"x": True, "y": 1}, {"x": "2", "y": 3}):
            self.assertIsNone(saved_position(value))
        self.assertEqual(clamp_position((-2000, -500), (0, 0, 1920, 1040), (640, 460)), (0, 0))
        self.assertEqual(clamp_position((1800, 1000), (0, 0, 1920, 1040), (640, 460)), (1280, 580))

    def test_sleep_and_unknown_are_not_disconnected(self):
        self.assertEqual(reading_status(reading(status="asleep", ok=False)), "设备休眠")
        self.assertEqual(reading_status(reading(status="unknown_proto", ok=False)), "协议未知")
        self.assertEqual(reading_status(reading(present=False)), "未连接")

    def test_tooltip_fits_windows_utf16_limit_with_emoji(self):
        summary = summarize({str(i): reading(name="🎮" * 40) for i in range(20)})
        self.assertLessEqual(len(summary.tooltip.encode("utf-16-le")), 254)
        self.assertTrue(summary.tooltip.endswith("…"))

    def test_badges(self):
        for name, expected in (("ATK Mouse", "鼠"), ("键盘", "键"),
                               ("Headset", "耳"), ("Gamepad", "柄"), ("ATK X1", "设")):
            with self.subTest(name=name):
                self.assertEqual(device_badge(name), expected)

    def test_flyout_stays_inside_work_area(self):
        cases = [
            ((1800, 1040, 1824, 1080), (0, 0, 1920, 1040)),
            ((1800, 0, 1824, 40), (0, 40, 1920, 1080)),
            ((0, 700, 40, 724), (40, 0, 1920, 1080)),
            ((1880, 700, 1920, 724), (0, 0, 1880, 1080)),
            ((-120, 1040, -96, 1080), (-1920, 0, 0, 1040)),
        ]
        for anchor, work in cases:
            with self.subTest(work=work, anchor=anchor):
                x, y = flyout_position(anchor, work, (560, 399))
                self.assertGreaterEqual(x, work[0])
                self.assertGreaterEqual(y, work[1])
                self.assertLessEqual(x + 560, work[2])
                self.assertLessEqual(y + 399, work[3])


@unittest.skipUnless(sys.platform == "win32", "Win32 integration")
class WindowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import my_devices
        cls.appmod = my_devices

    def test_single_icon_survives_empty_offline_and_more_than_four_devices(self):
        m = self.appmod
        app = SimpleNamespace(snapshot=Mock(return_value={}), theme_light=False)
        tray = m.Tray(app)
        with patch.object(m.shell32, "Shell_NotifyIconW", return_value=True) as notify:
            try:
                tray.sync_icons()
                self.assertEqual(list(tray.nids), [1])
                app.snapshot.return_value = {str(i): reading() for i in range(8)}
                tray.sync_icons()
                self.assertEqual(list(tray.nids), [1])
                app.snapshot.return_value = {"off": reading(present=False)}
                tray.sync_icons()
                self.assertEqual(list(tray.nids), [1])
                calls = [call.args[0] for call in notify.call_args_list]
                self.assertEqual(calls.count(m.NIM_ADD), 1)
                self.assertEqual(calls.count(m.NIM_MODIFY), 2)
            finally:
                tray.destroy()

    def test_native_icons_render_both_themes_and_low_battery(self):
        m = self.appmod
        for light in (True, False):
            for level in (0, 12, 100):
                icon = m.make_battery_icon(level, light)
                self.assertTrue(icon)
                self.assertTrue(m.user32.DestroyIcon(icon))

    def test_ring_red_threshold_and_minimum_are_passed_to_native_renderer(self):
        m = self.appmod
        self.assertEqual(m._level_color(9), (239, 68, 68))
        self.assertNotEqual(m._level_color(10), (239, 68, 68))
        app = SimpleNamespace(snapshot=lambda: {"a": reading(level=80), "b": reading(level=69)},
                              theme_light=False)
        tray = m.Tray(app)
        nid = tray._make_nid(1)
        with patch.object(m, "make_battery_icon", return_value=123) as render:
            tray._fill_icon(nid, "dashboard")
        render.assert_called_once_with(69, False, False)

    def test_native_warning_contains_message_and_preserves_ring(self):
        m = self.appmod
        tray = m.Tray(SimpleNamespace())
        nid = tray._make_nid(1)
        nid.hIcon = 123
        tray.nids[1] = nid
        sent = []

        def send(operation, pointer):
            value = pointer._obj
            sent.append((operation, value.szInfo, value.szInfoTitle, value.dwInfoFlags))
            return True

        with patch.object(m.shell32, "Shell_NotifyIconW", side_effect=send):
            self.assertTrue(tray.notify("鼠标电量仅剩 9%", "设备电量不足 10%", True))
        self.assertEqual(sent, [(m.NIM_MODIFY, "鼠标电量仅剩 9%", "设备电量不足 10%", 2)])
        self.assertEqual(nid.hIcon, 123)

    def test_drag_persists_position_and_reopen_does_not_reanchor(self):
        m = self.appmod
        panel = object.__new__(m.Panel)
        panel._drag = (0, 0, 100, 100)
        panel.root = Mock()
        panel.root.winfo_x.return_value, panel.root.winfo_y.return_value = -900, 240
        with patch.object(m, "load_config", return_value={"interval": 60}), \
                patch.object(m, "save_config") as save:
            panel._on_release(None)
        self.assertEqual(panel._saved_position, (-900, 240))
        save.assert_called_once_with({"interval": 60, "panel_position": {"x": -900, "y": 240}})
        panel.app = SimpleNamespace(theme_light=False, tray=Mock())
        panel._restore_position = Mock(return_value=True)
        panel._shadow = None
        panel.render = Mock()
        with patch.object(m, "startup_enabled", return_value=False):
            panel.show()
        panel.app.tray.position_dashboard.assert_not_called()
        panel._restore_position.assert_called_once()

    def test_restore_position_uses_nearest_monitor_work_area(self):
        m = self.appmod
        panel = object.__new__(m.Panel)
        panel._saved_position = (-1500, 800)
        panel.W, panel.H = 640, 460
        panel._move_to = Mock()

        def monitor_info(handle, pointer):
            pointer._obj.rcWork = m.wt.RECT(-1920, 0, 0, 1040)
            return True

        with patch.object(m.user32, "MonitorFromRect", return_value=1), \
                patch.object(m.user32, "GetMonitorInfoW", side_effect=monitor_info):
            self.assertTrue(panel._restore_position())
        panel._move_to.assert_called_once_with(-1500, 580)

    def test_explorer_restart_releases_and_recreates_icon(self):
        m = self.appmod
        tray = m.Tray(SimpleNamespace(snapshot=lambda: {}, theme_light=False))
        with patch.object(m.shell32, "Shell_NotifyIconW", return_value=True), \
                patch.object(m.user32, "DestroyIcon", wraps=m.user32.DestroyIcon) as destroy:
            try:
                tray.sync_icons()
                tray._add_icons()
                self.assertEqual(list(tray.nids), [1])
                self.assertEqual(destroy.call_count, 1)
            finally:
                tray.destroy()

    def test_left_click_enqueues_dashboard_without_device_polling(self):
        m = self.appmod
        import queue
        app = SimpleNamespace(_actions=queue.Queue(), refresh=Mock())
        tray = m.Tray(app)
        tray._proc(0, m.WM_TRAYICON, 1, m.WM_LBUTTONUP)
        self.assertEqual(app._actions.get_nowait()[0], "toggle")
        app.refresh.assert_not_called()

    def test_right_menu_queues_action_and_cleans_up(self):
        m = self.appmod
        import queue
        app = SimpleNamespace(_actions=queue.Queue(), _tray_menu_open=False)
        tray = m.Tray(app)
        with patch.object(m.user32, "CreatePopupMenu", return_value=1), \
                patch.object(m.user32, "AppendMenuW", return_value=True), \
                patch.object(m.user32, "GetCursorPos", return_value=True), \
                patch.object(m.user32, "SetForegroundWindow"), \
                patch.object(m.user32, "TrackPopupMenu", return_value=3), \
                patch.object(m.user32, "PostMessageW"), \
                patch.object(m.user32, "DestroyMenu") as destroy, \
                patch.object(m, "startup_enabled", return_value=False):
            tray.context_menu()
        self.assertEqual(app._actions.get_nowait()[0], "startup")
        self.assertFalse(app._tray_menu_open)
        destroy.assert_called_once_with(1)

    def test_startup_and_configuration_are_separate_from_upstream(self):
        m = self.appmod
        self.assertTrue(m.config_dir().endswith("BatteryTrayDashboard"))
        self.assertTrue(m.startup_lnk().endswith("EZ2.4G Dashboard.lnk"))
        with patch.object(m.os.path, "isfile", return_value=False), \
                patch.object(m, "install_startup") as install:
            self.assertFalse(m.startup_enabled())
            install.assert_not_called()

    def test_five_minute_refresh_overrides_legacy_interval_and_manual_is_immediate(self):
        m = self.appmod
        with patch.object(m, "is_light_theme", return_value=False), \
                patch.object(m, "load_config", return_value={"interval": 60}), \
                patch.object(m, "load_saved_devices", return_value=[]):
            app = m.TrayApp()
        self.assertEqual(app.interval, 300)
        with patch.object(m.threading, "Thread") as worker:
            app.refresh()
        worker.return_value.start.assert_called_once()
        tray = m.Tray(app)
        with patch.object(m.user32, "KillTimer"), \
                patch.object(m.user32, "SetTimer") as timer:
            tray._proc(123, m.WM_APP_INTERVAL, 0, 0)
        timer.assert_called_once_with(123, 1, 300000, None)

    def test_outside_focus_hides_but_child_dialogs_keep_dashboard_open(self):
        m = self.appmod
        panel = object.__new__(m.Panel)
        panel._visible, panel._help_win, panel._menu = True, None, None
        panel.app = SimpleNamespace(panel_only=False, _add_win=None, _tray_menu_open=False)
        panel.root = Mock()
        panel.root.focus_displayof.return_value = None
        panel.hide = Mock()
        panel._dismiss_if_unfocused()
        panel.hide.assert_called_once()
        for guard in ("_add_win", "_tray_menu_open"):
            panel.hide.reset_mock()
            setattr(panel.app, guard, True)
            panel._dismiss_if_unfocused()
            panel.hide.assert_not_called()
            setattr(panel.app, guard, False)
        panel.hide.reset_mock()
        panel.root.focus_displayof.return_value = panel.root
        panel._dismiss_if_unfocused()
        panel.hide.assert_not_called()

    def test_hidden_tk_canvas_renders_empty_and_many_devices(self):
        """Render our own withdrawn canvas; never capture or inspect the desktop."""
        m = self.appmod
        app = SimpleNamespace(theme_light=False, interval=60, panel_only=False,
                              _stop=False, _tray_menu_open=False, _add_win=None,
                              snapshot=Mock(return_value={}), refresh=Mock())
        original_tk = m.tk.Tk

        def hidden_root():
            root = original_tk()
            root.withdraw()
            return root

        with patch.object(m.tk, "Tk", side_effect=hidden_root), \
                patch.object(m, "ShadowWindow", return_value=None), \
                patch.object(m, "startup_enabled", return_value=False):
            panel = m.Panel(app)
            try:
                for scale in (1.0, 1.5, 2.0):
                    panel.S = scale
                    panel.render()
                    texts = [panel.cv.itemcget(i, "text") for i in panel.cv.find_all()
                             if panel.cv.type(i) == "text"]
                    self.assertIn("设备 Dashboard", texts)
                    self.assertIn("请插入设备", texts)
                panel.S = 1.0
                app.snapshot.return_value = {
                    str(i): m.Reading(ok=True, level=10 + i, name=f"Mouse {i}",
                                     status="charging" if i == 0 else "discharging")
                    for i in range(8)
                }
                panel.render()
                self.assertEqual(len(panel._card_rects), 8)
                self.assertGreater(panel._max_scroll, 0)
                self.assertFalse(panel.root.winfo_viewable())
                # Text bounds are checked in the actual hidden Tk canvas at
                # 100/150/200% scaling, including the user's stale-value case.
                app.snapshot.return_value = {
                    "mouse": m.Reading(ok=True, level=69, stale=True,
                                       name="Rapoo Gaming Device " * 8, detail="诊断信息" * 40),
                    "keyboard": m.Reading(ok=True, level=100, name="2.4G Wireless Receiver"),
                }
                for scale in (1.0, 1.5, 2.0):
                    panel.S = scale
                    panel.render()
                    name_box = panel.cv.bbox("nm_mouse")
                    value_box = panel.cv.bbox("value_mouse")
                    self.assertLess(name_box[2], value_box[0])
                    meta_box = panel.cv.bbox("meta_mouse")
                    status_box = panel.cv.bbox("status_mouse")
                    self.assertLess(meta_box[3], status_box[1])
                    self.assertLessEqual(status_box[2], (panel.LW - 40) * scale)
                    text = panel.cv.itemcget(panel.cv.find_withtag("status_mouse")[0], "text")
                    self.assertIn("上次电量", text)
                    self.assertNotIn("诊断信息", text)
                    self.assertGreaterEqual(status_box[3] - status_box[1], 12 * scale)
            finally:
                panel.close()


if __name__ == "__main__":
    unittest.main()
