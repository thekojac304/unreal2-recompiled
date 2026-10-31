"""Passive developer diagnostics reader; no qualification claims."""
import ctypes as C
import importlib.util
import struct
from pathlib import Path
import zlib

_path = Path(__file__).resolve().parents[3] / 'experiments/xrt/tests/practical_init/reader.py'
_spec = importlib.util.spec_from_file_location('trace_layout', _path)
_layout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_layout)
Record = _layout.Record


class Import(C.LittleEndianStructure):
    _fields_ = [('name', C.c_char * 128)] + [(n, C.c_uint64) for n in
        ('begins', 'ends', 'failures', 'aborts', 'minimum', 'maximum', 'changes', 'error_changes')] + [
        (n, Record) for n in ('first_begin', 'first_end', 'last_begin', 'last_end')]


class LegacySnapshot(C.LittleEndianStructure):
    _fields_ = [(n, C.c_uint32) for n in ('magic', 'version', 'size', 'slots')] + [
        (n, C.c_uint64) for n in ('generation', 'observed', 'routine_events', 'critical_records')] + [
        ('transitions', (C.c_uint64 * 65) * 65), ('imports', Import * 64),
        ('recent', Record * 32), ('recent_next', C.c_uint32), ('crc', C.c_uint32)]


class FlightImport(C.LittleEndianStructure):
    _fields_ = [('name', C.c_char * 128)] + [(n, C.c_uint64) for n in
        ('begins', 'ends', 'failures', 'aborts', 'minimum', 'maximum', 'changes', 'error_changes',
         'unclassified', 'suspects', 'bytes', 'short_io', 'metadata_missing')] + [
        (n, Record) for n in ('first_begin', 'first_end', 'last_begin', 'last_end', 'first_failure')]


class Snapshot(C.LittleEndianStructure):
    _fields_ = [(n, C.c_uint32) for n in ('magic', 'version', 'size', 'slots')] + [
        (n, C.c_uint64) for n in ('generation', 'observed', 'routine_events', 'critical_records',
            'overwritten', 'table_overflow', 'selected_records', 'unclassified', 'suspects', 'last_flush_observed')] + [
        ('terminal', C.c_uint32), ('recent_next', C.c_uint32),
        ('imports', FlightImport * 512), ('recent', Record * 512), ('crc', C.c_uint32)]


def snapshot(path):
    raw = Path(path).read_bytes()
    if len(raw) < 16:
        raise ValueError('truncated routine snapshot; recent history unavailable')
    version = struct.unpack_from('<I', raw, 4)[0]
    schema = LegacySnapshot if version == 1 else Snapshot
    if len(raw) != C.sizeof(schema):
        raise ValueError('truncated routine snapshot; recent history unavailable')
    value = schema.from_buffer_copy(raw)
    if (value.magic, value.version, value.size) != (0x31524458, 1 if schema == LegacySnapshot else 2, len(raw)) or value.slots > len(value.imports):
        raise ValueError('unknown routine snapshot schema')
    if value.crc != zlib.crc32(raw[:schema.crc.offset]):
        raise ValueError('torn/corrupt routine snapshot; recent history unavailable')
    return value


def context(r):
    return dict(ordinal=r.sequence, thread=r.thread, event=r.event, name=r.name.decode(),
                guest_pc=hex(struct.unpack_from('<I', r.cpu, 68)[0]),
                result=hex(r.result), last_error=r.error, guest_last_error=r.guest_error,
                flags=hex(r.flags), values=[v.value for v in r.values[:r.count]])


def summary(path):
    value = snapshot(path)
    recent = list(value.recent[value.recent_next:]) + list(value.recent[:value.recent_next])
    result = dict(generation=value.generation, observed=value.observed,
                routine_events=value.routine_events, critical_records_at_flush=value.critical_records,
                imports=[dict(name=s.name.decode(), **{n: getattr(s, n) for n in
                    ('begins', 'ends', 'failures', 'aborts', 'minimum', 'maximum', 'changes', 'error_changes')},
                    **({n: getattr(s, n) for n in ('unclassified', 'suspects', 'bytes', 'short_io', 'metadata_missing')}
                       if value.version == 2 else {}),
                    first_caller=hex(struct.unpack_from('<I', s.first_begin.stack)[0]),
                    last_caller=hex(struct.unpack_from('<I', s.last_begin.stack)[0]))
                    for s in value.imports if s.begins],
                recent=[context(r) for r in recent if r.sequence][-12:])
    if value.version == 2:
        result.update(overwritten=value.overwritten, operation_table_overflow=value.table_overflow,
            selected_records=value.selected_records, unclassified_returns=value.unclassified,
            suspicious_returns=value.suspects,
            terminal={0:'none',1:'orderly close',2:'Init-return checkpoint',3:'handled fatal',4:'monitor gap'}[value.terminal],
            unflushed_history='none at terminal snapshot' if value.terminal else
                'UNKNOWN after last durable snapshot; abrupt termination may lose pending events or tear the snapshot',
            limitation='512 recent events; older history overwritten as counted. Unclassified returns are NOT successes. '
                       'Snapshot interval 16384 events; disk failure/forced kill can prevent a final flush. '
                       'Only dev.Init.return proves the fixed endpoint; orderly close alone does not.')
    else:
        result['limitation'] = 'Legacy bounded routine snapshot; abrupt kills can lose the pending batch.'
    return result


def records(path):
    raw = Path(path).read_bytes()
    size = C.sizeof(Record)
    if len(raw) % size:
        raise ValueError('truncated critical stream')
    chain = 0
    for ordinal, offset in enumerate(range(0, len(raw), size), 1):
        chunk = raw[offset:offset+size]
        r = Record.from_buffer_copy(chunk)
        if (r.magic, r.size, r.sequence, r.previous_crc) != (0x31544d58, size, ordinal, chain):
            raise ValueError('invalid critical stream header/sequence')
        if r.version not in (3, 4, 5) or r.crc != zlib.crc32(chunk[:Record.crc.offset]):
            raise ValueError('critical stream checksum/version failure')
        chain = r.crc
        yield r
