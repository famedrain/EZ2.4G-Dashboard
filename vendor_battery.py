"""Narrow device adapters derived from the official WebHID drivers.

Only MCHOSE's getBattery request is sent. Rapoo is input-only. No settings,
pairing, EEPROM writes, or firmware commands are implemented here.
Sources and the distinction between synthetic tests and hardware validation
are documented in docs/protocols.md.
"""
from dataclasses import dataclass
import time


MCHOSE_RECEIVER = (0x3554, 0xFA09)
RAPOO_VT3S = (0x24AE, 0x1411)


@dataclass(frozen=True)
class Battery:
    level: int
    charging: bool
    source: str
    raw: bytes


def protocol_name(vid, pid):
    return {
        MCHOSE_RECEIVER: "MCHOSE G75 Pro / G-series WebHID",
        RAPOO_VT3S: "Rapoo VT3S WebHID input report",
    }.get((vid, pid))


def mchose_request():
    # Official wirelessCommand starts with report ID 0x13, then command 0x4A.
    # The official driver appends the low byte of the sum of all 19 bytes.
    frame = bytes.fromhex("13 4A 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")
    return frame + bytes([sum(frame) & 0xFF])


def parse_mchose(report):
    # Windows input contains report ID, unlike WebHID's event.data.
    # Official commonParser: command, totalPackets, currentSequence; a fourth
    # header byte precedes the batteryLevel + fullStatus/chargeStatus payload.
    if len(report) < 20 or report[:4] != bytes([0x13, 0x4A, 1, 0]):
        return None
    level, flags = report[5], report[6]
    if level > 100 or flags >> 4 > 1 or flags & 0x0F > 1:
        return None
    return Battery(level, bool(flags & 0x0F), "迈从 G75 Pro 官方协议", bytes(report))


def parse_rapoo(report):
    # VT_nrf54L handleReport accepts ID 7. Nf() reads status at body[6]
    # (1=valid, 2=charging) and battery percentage at body[7].
    if len(report) < 9 or report[0] != 7:
        return None
    status, level = report[7], report[8]
    if status not in (1, 2) or level > 100:
        return None
    return Battery(level, status == 2, "雷柏 VT3S 官方输入报告", bytes(report))


def read_battery(ifaces, device_factory, timeout=4.0):
    """Try only the pinned VID/PID and configuration collection, always close.

    No fallback probes of mouse/keyboard input or firmware-update collections.
    A successful parse is required; absence of a report is never 0% battery.
    """
    deadline = time.monotonic() + timeout
    for iface in ifaces:
        if time.monotonic() >= deadline:
            break
        pair = (iface.vid, iface.pid)
        if pair == MCHOSE_RECEIVER:
            if (iface.usage_page != 0xFF02 or not 20 <= iface.output_len <= 64
                    or not 8 <= iface.input_len <= 256):
                continue
            parser, write = parse_mchose, True
        elif pair == RAPOO_VT3S:
            if (iface.usage_page != 0xFF00 or iface.usage != 2
                    or not 9 <= iface.input_len <= 256):
                continue
            parser, write = parse_rapoo, False
        else:
            continue
        dev = None
        try:
            dev = device_factory(iface.path, write=write)
            if write:
                request = mchose_request()
                request += bytes(iface.output_len - len(request))
                if dev.write_output(request) != len(request):
                    continue
            while time.monotonic() < deadline:
                remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
                report = dev.read_input(iface.input_len, min(250, remaining_ms))
                if report:
                    result = parser(report)
                    if result is not None:
                        return result
        except Exception:
            # Driver ownership, sleeping hardware, and HID access errors all
            # remain "waiting" at the UI layer rather than fake percentages.
            continue
        finally:
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
    return None
