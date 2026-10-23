"""Read-only Ogg page/PCM comparison. Writes evidence only into a new output directory.

CRC definition: https://xiph.org/ogg/doc/framing.html (direct 0x04c11db7,
initial/final XOR zero, checksum bytes cleared). Neither input is rewritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc_table():
    table = []
    for i in range(256):
        value = i << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xffffffff
        table.append(value)
    return table


TABLE = crc_table()


def pages(data):
    offset, result = 0, []
    while offset < len(data):
        if data[offset:offset + 4] != b'OggS' or offset + 27 > len(data):
            raise ValueError(f'invalid/truncated Ogg page at {offset}')
        header_end = offset + 27 + data[offset + 26]
        end = header_end + sum(data[offset + 27:header_end])
        if header_end > len(data) or end > len(data):
            raise ValueError(f'truncated page at {offset}')
        page = bytearray(data[offset:end])
        stored = int.from_bytes(page[22:26], 'little')
        page[22:26] = bytes(4)
        computed = 0
        for byte in page:
            computed = ((computed << 8) & 0xffffffff) ^ TABLE[(computed >> 24) ^ byte]
        result.append(dict(offset=offset, body_offset=header_end, end=end,
                           sequence=int.from_bytes(page[18:22], 'little'),
                           granule=int.from_bytes(page[6:14], 'little'),
                           stored_crc=f'{stored:08x}', computed_crc=f'{computed:08x}',
                           valid_crc=stored == computed))
        offset = end
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--installed', type=Path, required=True)
    ap.add_argument('--decoder', type=Path, required=True, help='existing FFmpeg executable')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    inputs = {'snapshot': a.snapshot.resolve(), 'installed': a.installed.resolve()}
    data = {k: p.read_bytes() for k, p in inputs.items()}
    a.out.mkdir(parents=True, exist_ok=False)
    offsets = [i for i, (x, y) in enumerate(zip(data['snapshot'], data['installed'])) if x != y]
    result = dict(schema=1, source_spec='https://xiph.org/ogg/doc/framing.html',
                  decoder=dict(path=str(a.decoder.resolve()), sha256=sha(a.decoder.read_bytes())),
                  same_size=len(data['snapshot']) == len(data['installed']),
                  differences=[dict(offset=i, **{k: f'{b[i]:02x}' for k, b in data.items()}) for i in offsets], files={})
    version = subprocess.run([str(a.decoder), '-version'], capture_output=True, timeout=15, check=True)
    result['decoder']['version'] = version.stdout.decode(errors='replace').splitlines()[0]
    for key, path in inputs.items():
        command = [str(a.decoder), '-v', 'warning', '-i', str(path), '-map', '0:a:0',
                   '-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1']
        decoded = subprocess.run(command, capture_output=True, timeout=60)
        (a.out / (key + '-decode.txt')).write_bytes(decoded.stderr)
        page_list = pages(data[key])
        result['files'][key] = dict(path=str(path), size=len(data[key]), sha256=sha(data[key]),
                                    pages=page_list, decode_command=command, decode_exit=decoded.returncode,
                                    pcm_bytes=len(decoded.stdout), pcm_sha256=sha(decoded.stdout),
                                    decode_stderr=decoded.stderr.decode(errors='replace'),
                                    changed_pages=[p for p in page_list if any(p['offset'] <= i < p['end'] for i in offsets)])
    result['sources_unchanged'] = all(p.read_bytes() == data[k] for k, p in inputs.items())
    (a.out / 'report.json').write_text(json.dumps(result, indent=2))
    print(a.out / 'report.json')
    if not result['sources_unchanged']:
        raise RuntimeError('input changed during read-only comparison')


if __name__ == '__main__':
    main()
