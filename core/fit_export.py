import struct
import time
import math
from datetime import datetime, timezone


FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


def _fit_timestamp(dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    return int((dt - FIT_EPOCH).total_seconds())


def _semicircles(degrees):
    return int(degrees * (2**31 / 180))


def _crc16(data):
    crc_table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
        crc_table.append(crc)

    crc = 0
    for byte in data:
        crc = (crc >> 8) ^ crc_table[(crc ^ byte) & 0xFF]
    return crc


class FitWriter:
    def __init__(self):
        self._records = bytearray()
        self._definitions = {}

    def _write_definition(self, local_msg, global_msg, fields):
        record_header = 0x40 | (local_msg & 0x0F)
        data = struct.pack('<BBHB', record_header, 0, global_msg, len(fields))
        for field_num, size, base_type in fields:
            data += struct.pack('<BBB', field_num, size, base_type)
        self._records.extend(data)
        self._definitions[local_msg] = fields

    def _write_data(self, local_msg, values):
        record_header = local_msg & 0x0F
        data = struct.pack('<B', record_header)
        fields = self._definitions[local_msg]
        for (_, size, base_type), value in zip(fields, values):
            if base_type == 0x00:  # enum/uint8
                data += struct.pack('<B', value & 0xFF)
            elif base_type == 0x84:  # uint16
                data += struct.pack('<H', value & 0xFFFF)
            elif base_type == 0x86:  # uint32
                data += struct.pack('<I', value & 0xFFFFFFFF)
            elif base_type == 0x85:  # sint32
                data += struct.pack('<i', value)
            elif base_type == 0x07:  # string
                encoded = value.encode('utf-8')[:size]
                data += encoded + b'\x00' * (size - len(encoded))
            elif base_type == 0x88:  # float32
                data += struct.pack('<f', value)
        self._records.extend(data)

    def build(self):
        data_size = len(self._records)

        header = struct.pack('<BBHI4s',
            14,      # header size
            0x20,    # protocol version 2.0
            0x0816,  # profile version
            data_size,
            b'.FIT',
        )
        header_crc = _crc16(header)
        header += struct.pack('<H', header_crc)

        file_data = header + bytes(self._records)
        file_crc = _crc16(file_data)
        file_data += struct.pack('<H', file_crc)

        return file_data


def export_power_course(result: dict, course_name: str, output_path: str) -> str:
    segments = result['segments']
    writer = FitWriter()

    ts = _fit_timestamp()

    # File ID message (global msg 0)
    writer._write_definition(0, 0, [
        (0, 1, 0x00),   # type: course
        (1, 2, 0x84),   # manufacturer
        (2, 2, 0x84),   # product
        (3, 4, 0x86),   # serial_number
        (4, 4, 0x86),   # time_created
    ])
    writer._write_data(0, [6, 1, 1, 12345, ts])  # type=6 is course

    # Course message (global msg 31)
    name_len = min(len(course_name) + 1, 32)
    writer._write_definition(1, 31, [
        (5, 32, 0x07),   # name (string)
    ])
    writer._write_data(1, [course_name[:31]])

    # Lap message (global msg 19)
    writer._write_definition(2, 19, [
        (253, 4, 0x86),  # timestamp
        (0, 4, 0x86),    # event (timer)
        (2, 4, 0x85),    # start_position_lat
        (3, 4, 0x85),    # start_position_long
        (4, 4, 0x85),    # end_position_lat
        (5, 4, 0x85),    # end_position_long
        (9, 4, 0x86),    # total_distance (in cm)
        (7, 4, 0x86),    # total_elapsed_time (ms)
    ])

    total_dist_cm = int(sum(s['distance_m'] for s in segments) * 100)
    total_time_ms = int(result['total_time_s'] * 1000)

    writer._write_data(2, [
        ts,
        0,
        _semicircles(segments[0]['lat']),
        _semicircles(segments[0]['lon']),
        _semicircles(segments[-1]['lat']),
        _semicircles(segments[-1]['lon']),
        total_dist_cm,
        total_time_ms,
    ])

    # Record messages (global msg 20) - one per segment
    writer._write_definition(3, 20, [
        (253, 4, 0x86),  # timestamp
        (0, 4, 0x85),    # position_lat
        (1, 4, 0x85),    # position_long
        (5, 4, 0x86),    # distance (in cm)
        (2, 2, 0x84),    # altitude (offset by +500, scale 5)
        (7, 2, 0x84),    # power
    ])

    current_ts = ts
    for seg in segments:
        alt_fit = int((seg['elevation_m'] + 500) * 5)
        dist_cm = int(seg['cumulative_m'] * 100)
        power = int(round(seg['power_w']))

        writer._write_data(3, [
            current_ts,
            _semicircles(seg['lat']),
            _semicircles(seg['lon']),
            dist_cm,
            alt_fit,
            power,
        ])
        current_ts += int(seg['time_s'])

    fit_data = writer.build()
    with open(output_path, 'wb') as f:
        f.write(fit_data)

    return output_path


def export_zwift_zwo(result: dict, output_path: str) -> str:
    segments = result['segments']
    ftp = result.get('mean_power_w', 200)

    lines = ['<workout_file>']
    lines.append('  <author>CyclingPacer</author>')
    lines.append(f'  <name>Pacing Plan</name>')
    lines.append('  <description>Auto-generated pacing plan</description>')
    lines.append('  <sportType>bike</sportType>')
    lines.append('  <workout>')

    for seg in segments:
        power_frac = seg['power_w'] / ftp if ftp > 0 else 1.0
        duration = int(seg['time_s'])
        lines.append(f'    <SteadyState Duration="{duration}" Power="{power_frac:.3f}"/>')

    lines.append('  </workout>')
    lines.append('</workout_file>')

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    return output_path
