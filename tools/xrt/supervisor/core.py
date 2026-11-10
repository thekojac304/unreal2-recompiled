"""Strict queue protocol and durable authorization. No process execution here."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
HOME = ROOT / "out/desktop-supervisor"
SCOPE = "renderer-init-before-0696f292"
FIXTURE_SCOPE = "supervisor-fixture"
MAX_BYTES = 262144


class Rejected(ValueError):
    pass


class IntegrityFailure(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Rejected(reason)


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def independent(path):
    """Reject junctions, symlinks, ADS, hard links, and device/path aliases."""
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            s = p.lstat()
            require(not (getattr(s, "st_file_attributes", 0) & 0x400) and not p.is_symlink(), "reparse path")
    if path.is_file():
        require(path.stat().st_nlink == 1, "hardlinked file")
    return path


def project_path(relative, prefixes, *, root=ROOT, exists=True):
    require(isinstance(relative, str) and 0 < len(relative) < 220, "invalid relative path")
    require("\\" not in relative and ":" not in relative, "Windows path alias/ADS")
    parts = relative.split("/")
    require(all(p and p not in (".", "..") and p == p.rstrip(" .") for p in parts), "path traversal/alias")
    require(not any(os.path.isreserved(p) if hasattr(os.path, "isreserved") else PureWindowsPath(p).is_reserved() for p in parts), "reserved device path")
    require(any(relative.startswith(p.rstrip("/") + "/") for p in prefixes), "path outside approved locations")
    path = independent(root / relative)
    require(path.resolve().is_relative_to(root.resolve()), "path escaped workspace")
    if exists:
        require(path.is_file(), "missing file: " + relative)
    return path


def exact(obj, keys):
    require(isinstance(obj, dict) and set(obj) == set(keys.split()), "unknown or missing fields")


def uuid_text(value):
    require(isinstance(value, str), "UUID must be text")
    try:
        require(str(uuid.UUID(value)) == value, "noncanonical UUID")
    except (ValueError, AttributeError):
        raise Rejected("invalid UUID") from None
    return value


def hash_text(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value), "invalid SHA-256")
    return value


def loads(data):
    require(len(data) <= MAX_BYTES, "oversized JSON")
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, "duplicate JSON key")
            d[k] = v
        return d
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Rejected("nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError) as e:
        raise Rejected("malformed JSON: " + str(e)) from None


def read(path):
    independent(path)
    with Path(path).open("rb") as f:
        return loads(f.read(MAX_BYTES + 1))


def atomic(path, value):
    path = Path(path)
    independent(path.parent)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with tmp.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def tree(root):
    independent(root)
    return {p.relative_to(root).as_posix(): sha(independent(p))
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


REQUEST_KEYS = "version id batch_id created_at expires_at objective candidate manifest_sha256 expected_stop scope timeout_seconds"


def parse_request(data, batch, *, now=None):
    now = time.time() if now is None else now
    exact(data, REQUEST_KEYS)
    require(type(data["version"]) is int and data["version"] == 1, "protocol version")
    uuid_text(data["id"])
    require(data["batch_id"] == batch["id"], "unauthorized batch")
    require(isinstance(data["objective"], str) and 12 <= len(data["objective"]) <= 1000, "declare exact objective")
    for key in ("created_at", "expires_at"):
        require(type(data[key]) in (int, float), "numeric timestamp required")
    require(batch["started_at"] <= data["created_at"] <= now + 2, "stale/future request")
    require(now < data["expires_at"] <= min(data["created_at"] + 300, batch["expires_at"]), "expired request/TTL")
    require(data["expires_at"] > data["created_at"], "invalid TTL")
    require(type(data["timeout_seconds"]) is int and 1 <= data["timeout_seconds"] <= 60, "attempt limit 1..60 seconds")
    require(data["scope"] in (SCOPE, FIXTURE_SCOPE), "unauthorized execution scope")
    require(data["scope"] == FIXTURE_SCOPE or batch["genuine_limit"] > 0, "genuine execution not authorized")
    require(data["candidate"] == "out/desktop-supervisor/candidates/" + data["id"] + ".json", "candidate must be request-bound")
    hash_text(data["manifest_sha256"])
    stop = data["expected_stop"]
    require(isinstance(stop, dict), "expected stop required")
    if data["scope"] == FIXTURE_SCOPE:
        exact(stop, "kind")
        require(stop["kind"] in ("fixture-complete", "fixture-breakpoint"), "fixture stop")
    elif stop.get("kind") == "first-unsupported-or-permanent":
        exact(stop, "kind guest_address")
        require(stop["guest_address"] == "0x0696f292", "permanent stop cannot advance")
    elif stop.get("kind") == "permanent-stop":
        exact(stop, "kind guest_address")
        require(stop["guest_address"] == "0x0696f292", "permanent stop cannot advance")
    else:
        exact(stop, "kind code format")
        require(stop["kind"] == "unsupported-method" and type(stop["code"]) is int and stop["code"] in (75,76), "unsupported stop")
        require(isinstance(stop["format"], str) and 1 <= len(stop["format"]) <= 512, "fatal format")
        require(routine_format(stop["format"]), "unclassified fatal format")
    return data


def routine_format(fmt):
    # Narrow unsupported-method families; correctness, CPU and memory traps are excluded.
    family=(fmt == "call to import %s, which has no host implementation (from %s)" or
            bool(re.fullmatch(r"IDirect3D8::[A-Za-z_][A-Za-z_0-9]* is unmeasured \(interface %08x, caller %08x\)",fmt)) or
            fmt.startswith(("WM_GETOBJECT:", "WM_GETICON:", "dialog callback message ", "window callback 0xae:",
                            "IDirect3DDevice8 unsupported slot ", "D3D8:", "D3D8 ",
                            "unsupported import user32.dll!", "unsupported import d3d8.dll!")))
    return family and not any(x in fmt.lower() for x in ("mismatch", "corrupt", "x87", "overflow", "invalid pointer"))


def expected_fatal(rows, expected):
    fatals=[r for r in rows if r["kind"]=="fatal_entry"]
    if len(fatals)!=1:return False
    f=fatals[0]
    if expected["kind"]=="unsupported-method":
        if f["code"]!=expected["code"] or f["format"]!=expected["format"]:return False
    elif expected["kind"]!="first-unsupported-or-permanent":return False
    if f["diagnostic_read_errors"] or f["runtime_fatal_body_executed"]:return False
    if not any(r["kind"]=="terminated_before_continue" for r in rows):return False
    if f["code"]==75:
        imports=[r for r in rows if r["kind"]=="import_boundary"]
        return (f["format"]=="call to import %s, which has no host implementation (from %s)" and len(imports)==1
                and bool(re.fullmatch(r"(?:user32|imm32|d3d8)\.dll![A-Za-z_][A-Za-z_0-9]*",imports[0]["symbol"],re.I)))
    return f["code"]==76 and routine_format(f["format"])


MANIFEST_KEYS = "version kind executable sha256 pdb_sha256 build_record build_record_sha256 sources dependencies fixture_case"


def validate_manifest(m, request, *, root=ROOT):
    exact(m, MANIFEST_KEYS)
    require(type(m["version"]) is int and m["version"] == 1, "manifest version")
    kind = "genuine" if request["scope"] == SCOPE else "fixture"
    require(m["kind"] == kind, "candidate kind/scope mismatch")
    exe = project_path(m["executable"], ["experiments/xrt/build"], root=root)
    require(exe.suffix.lower() == ".exe", "PE executable required")
    hash_text(m["sha256"])
    if sha(exe) != m["sha256"]:
        raise IntegrityFailure("candidate hash mismatch")
    require(isinstance(m["sources"], dict) and bool(m["sources"]), "source identity missing")
    require(isinstance(m["dependencies"], dict), "dependency identities missing")
    for table, prefixes in ((m["sources"], ["tools/xrt", "experiments/xrt/runtime", "experiments/xrt/tests", "experiments/xrt/gen"]),
                            (m["dependencies"], ["experiments/xrt/build", "experiments/xrt/results/raw/directmusic", "third_party/graphics"])):
        for rel, h in table.items():
            hash_text(h)
            if sha(project_path(rel, prefixes, root=root)) != h:
                raise IntegrityFailure("source/dependency changed: " + rel)
    if kind == "fixture":
        require(m["executable"] == "experiments/xrt/build/desktop-supervisor/fixture.exe", "fixture executable allowlist")
        require(m["fixture_case"] in ("ok-a", "ok-b", "hard-stop", "routine-failure"), "fixture argument allowlist")
        require(m["pdb_sha256"] is None and m["build_record"] is None and m["build_record_sha256"] is None, "fixture metadata")
        require(m["dependencies"] == {}, "fixture dependencies fixed")
    else:
        require(exe.name == "xrt_ucc.exe" and m["fixture_case"] is None, "genuine candidate allowlist")
        if sha(independent(exe.with_suffix(".pdb"))) != hash_text(m["pdb_sha256"]):
            raise IntegrityFailure("PDB hash mismatch")
        record_path = project_path(m["build_record"], ["out/recovery"], root=root)
        if sha(record_path) != hash_text(m["build_record_sha256"]):
            raise IntegrityFailure("build record mismatch")
        # Build records originate from the existing serial client builder. Validate
        # their complete source/generated/object inventories, including additions.
        b = read_large(record_path)
        require(b.get("passed") is True and Path(b["root"]).resolve() == exe.parent.resolve(), "successful exact build required")
        for folder in ("runtime", "generated"):
            actual = tree(root / ("experiments/xrt/runtime" if folder == "runtime" else "experiments/xrt/gen"))
            if actual != b[folder]:
                raise IntegrityFailure(folder + " differs from build")
        if tree(exe.parent) != b["outputs"] or b["binary_sha256"] != m["sha256"] or b["pdb_sha256"] != m["pdb_sha256"]:
            raise IntegrityFailure("build outputs differ")
    return exe


def read_large(path):
    # Trusted local build/qualification records may exceed the queue limit.
    independent(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Ledger:
    """One exclusive supervisor owns this append-only ledger for its lifetime."""
    def __init__(self, path):
        self.path = Path(path)
        independent(self.path)
        self.rows = []
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                try:
                    row = loads(line)
                    require(row["sequence"] == len(self.rows) + 1 and row["previous"] == (digest(self.rows[-1]) if self.rows else "0" * 64), "ledger chain")
                    self.rows.append(row)
                except Exception as e:
                    raise IntegrityFailure("damaged attempt ledger") from e

    def append(self, kind, **values):
        row = dict(sequence=len(self.rows) + 1, previous=digest(self.rows[-1]) if self.rows else "0" * 64,
                   time=time.time(), kind=kind, **values)
        # Freeze nested authorizations/holds; later changes to a caller's dict
        # must not mutate history or the in-memory chain head.
        row = loads(json.dumps(row, allow_nan=False))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.rows.append(row)

    def claim(self, request, manifest, batch):
        require(not any(r.get("request_id") == request["id"] for r in self.rows), "replay request")
        if manifest["kind"] == "genuine":
            attempts = [r for r in self.rows if r["kind"] == "launch-claimed"]
            require(not any(r.get("sha256") == manifest["sha256"] for r in attempts), "unchanged genuine binary already attempted")
            require(sum(r["batch_id"] == batch["id"] for r in attempts) < batch["genuine_limit"], "batch exhausted")
        self.append("launch-claimed" if manifest["kind"] == "genuine" else "fixture-claimed",
                    request_id=request["id"], batch_id=batch["id"], sha256=manifest["sha256"])

