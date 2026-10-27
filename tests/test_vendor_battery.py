"""Source-derived synthetic reports, NOT recordings from the user's devices."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vendor_battery import (MCHOSE_RECEIVER, RAPOO_VT3S, mchose_request,
                            parse_mchose, parse_rapoo, read_battery)


def mchose_report(level=72, flags=0):
    return bytes([0x13, 0x4A, 1, 0, 2, level, flags]) + bytes(13)


def rapoo_report(level=63, status=1):
    return bytes([7, 0, 1, 0, 8, 0, 8, status, level]) + bytes(11)


def iface(pair, page, usage=2, **changes):
    values = dict(vid=pair[0], pid=pair[1], usage_page=page, usage=usage,
                  path="synthetic-device", input_len=20, output_len=20)
    values.update(changes)
    return SimpleNamespace(**values)


class VendorProtocolTests(unittest.TestCase):
    def test_mchose_get_only_frame_matches_official_command_and_checksum(self):
        frame = mchose_request()
        self.assertEqual(frame, bytes.fromhex("13 4A 01") + bytes(16) + b"\x5e")

    def test_mchose_decodes_zero_full_and_charging(self):
        for level in (0, 72, 100):
            self.assertEqual(parse_mchose(mchose_report(level)).level, level)
        self.assertTrue(parse_mchose(mchose_report(flags=1)).charging)
        self.assertFalse(parse_mchose(mchose_report(flags=0x10)).charging)

    def test_mchose_rejects_wrong_command_sequence_length_and_percent(self):
        valid = mchose_report()
        bad = [valid[:7], mchose_report(101), mchose_report(flags=0xF0)]
        for index, value in ((0, 7), (1, 0x49), (2, 2), (3, 1)):
            frame = bytearray(valid)
            frame[index] = value
            bad.append(frame)
        for frame in bad:
            self.assertIsNone(parse_mchose(frame))

    def test_rapoo_decodes_official_report7_and_charge_state(self):
        self.assertEqual(parse_rapoo(rapoo_report(0)).level, 0)
        self.assertEqual(parse_rapoo(rapoo_report(100)).level, 100)
        self.assertTrue(parse_rapoo(rapoo_report(status=2)).charging)

    def test_rapoo_rejects_other_reports_invalid_status_and_percent(self):
        for frame in (b"", rapoo_report()[:8], rapoo_report(101),
                      rapoo_report(status=0), bytes([0xBB]) + rapoo_report()[1:]):
            self.assertIsNone(parse_rapoo(frame))

    def test_mchose_transport_sends_only_get_battery(self):
        dev = Mock()
        dev.write_output.return_value = 20
        dev.read_input.side_effect = [bytes(20), mchose_report()]
        factory = Mock(return_value=dev)
        result = read_battery([iface(MCHOSE_RECEIVER, 0xFF02)], factory)
        self.assertEqual(result.level, 72)
        factory.assert_called_once_with("synthetic-device", write=True)
        dev.write_output.assert_called_once_with(mchose_request())
        dev.close.assert_called_once()

    def test_rapoo_transport_never_sends_output_or_feature_commands(self):
        dev = Mock()
        dev.read_input.return_value = rapoo_report()
        factory = Mock(return_value=dev)
        result = read_battery([iface(RAPOO_VT3S, 0xFF00)], factory)
        self.assertEqual(result.level, 63)
        factory.assert_called_once_with("synthetic-device", write=False)
        dev.write_output.assert_not_called()
        dev.set_feature.assert_not_called()
        dev.set_output_report.assert_not_called()
        dev.close.assert_called_once()

    def test_other_ids_and_firmware_collections_are_never_opened(self):
        factory = Mock()
        candidates = [iface((0x3554, 123), 0xFF02),
                      iface(RAPOO_VT3S, 0xFF00, usage=14),
                      iface(MCHOSE_RECEIVER, 1),
                      iface(MCHOSE_RECEIVER, 0xFF02, output_len=0)]
        self.assertIsNone(read_battery(candidates, factory))
        factory.assert_not_called()

    def test_access_failure_returns_no_reading_and_closes_handle(self):
        dev = Mock()
        dev.read_input.side_effect = OSError("device unavailable")
        self.assertIsNone(read_battery([iface(RAPOO_VT3S, 0xFF00)], Mock(return_value=dev)))
        dev.close.assert_called_once()

    @unittest.skipUnless(sys.platform == "win32", "Win32 app integration")
    def test_app_uses_builtin_without_saving_capture_or_faking_sleep(self):
        import my_devices as app
        device = {"vid": 0x3554, "pid": 0xFA09, "name": "迈从 G75 Pro 键盘"}
        hidiface = iface(MCHOSE_RECEIVER, 0xFF02)
        hidiface.product = "2.4G Wireless Receiver"
        with patch.object(app, "read_standard_battery", return_value=None), \
                patch.object(app, "user_protocols", return_value={}), \
                patch.object(app, "save_config") as save, \
                patch.object(app, "read_vendor_battery", return_value=None):
            result = app.read_saved_device(device, [hidiface])
        self.assertEqual(result.status, "waiting")
        self.assertFalse(result.ok)
        self.assertIsNone(result.level)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
