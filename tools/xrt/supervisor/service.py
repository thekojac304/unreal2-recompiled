"""Persistent filesystem queue; no network listener, elevation, shell or retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
import uuid
from . import core
from .policy import State, POLICY, decision, recovery_allowed


def seal_files():
    paths = [core.ROOT / "tools/xrt/desktop_supervisor.py"]
    paths += list((core.ROOT / "tools/xrt/supervisor").rglob("*.py"))
    paths += list((core.ROOT / "tools/xrt/supervisor").glob("*.c"))
    # Historical observers import directly executable phase helpers. Archived
    # source-before trees are evidence, never import locations.
    paths += list((core.ROOT / "out/recovery").glob("*/*.py"))
    paths += list((core.ROOT / "tools/xrt").glob("*.py"))
    paths += [core.ROOT/p for p in ('experiments/xrt/dmusic_helper/main.c',
              'experiments/xrt/dmusic_helper/file_guard.h', 'experiments/xrt/runtime/dmusic_pipe.h',
              'experiments/xrt/runtime/dmusic_backend.h')]
    return {p.relative_to(core.ROOT).as_posix(): core.sha(core.independent(p)) for p in paths if "__pycache__" not in p.parts}


def verify_seal(seal):
    for rel, expected in seal["files"].items():
        if core.sha(core.independent(core.ROOT / rel)) != expected:
            raise core.IntegrityFailure("qualified supervisor dependency changed: " + rel)
    for path,expected in seal["host_files"].items():
        if core.sha(core.independent(path))!=expected:
            raise core.IntegrityFailure("qualified Python/host dependency changed: "+path)
    from .windows import FilePins
    # Source inventory includes additions as well as changed files in the supervisor itself.
    known = {p for p in seal["files"] if p.startswith("tools/xrt/supervisor/")}
    current = {p.relative_to(core.ROOT).as_posix() for p in (core.ROOT / "tools/xrt/supervisor").rglob("*.py")}
    current |= {p.relative_to(core.ROOT).as_posix() for p in (core.ROOT / "tools/xrt/supervisor").glob("*.c")}
    if current != known:
        raise core.IntegrityFailure("supervisor inventory changed; requalify")


class Service:
    def __init__(self, home, limit=0, *, qualification=False):
        self.home = Path(home)
        for name in ("requests", "processing", "responses", "evidence", "candidates", "archive"):
            (self.home / name).mkdir(parents=True, exist_ok=True)
            core.independent(self.home / name)
        self.shutdown = False
        self.qualification = qualification
        self.desktop = None
        self.seal = None
        self.seal_identity = None
        self.ledger = core.Ledger(self.home / "ledger.jsonl")
        self.batch = dict(id=str(uuid.uuid4()), started_at=time.time(), expires_at=time.time() + 4 * 3600,
                          genuine_limit=limit, maximum_seconds=60, scope=core.SCOPE, retry=False)
        self.operational_state = State.RUNNING
        self.hold = None
        transitions = [r for r in self.ledger.rows if r['kind']=='operational-transition']
        if transitions:
            self.operational_state = State(transitions[-1]['state'])
            self.hold = transitions[-1]['hold']
        if (self.home / 'HALTED.json').exists():
            self.operational_state = State.SAFETY_HALT
        # An interrupted claimed request is never retried, even on owner restart.
        for p in (self.home / "processing").glob("*.json"):
            self.halt("interrupted request from an earlier supervisor: " + p.name)

    def stop(self):
        return self.shutdown or (self.home / "STOP").exists()

    @property
    def halted(self):
        return self.operational_state != State.RUNNING

    def bind_seal(self, seal):
        self.seal = seal
        self.seal_identity = core.digest(seal)

    def transition(self, state, hold):
        # The append-only ledger is authoritative; the state file is a projection.
        self.ledger.append('operational-transition', state=state, hold=hold, batch_id=self.batch['id'])
        self.operational_state, self.hold = State(state), hold
        core.atomic(self.home/'operational-state.json', dict(state=state, hold=hold,
                    ledger_sequence=len(self.ledger.rows), ledger_head=core.digest(self.ledger.rows[-1])))

    def halt(self, reason, hold=None):
        # Never rewrite the first historical halt, even if another fault follows.
        latch = self.home/'HALTED.json'
        if not latch.exists():
            core.atomic(latch, dict(time=time.time(), reason=reason, requires_owner_review=True))
        self.transition(State.SAFETY_HALT, hold or dict(reason=reason, recoverable=False, batch_id=self.batch['id']))

    def apply_decision(self, finding, out):
        if finding['state'] == State.RUNNING:
            return  # A successful diagnostic cannot clear any previous blocker.
        record = dict(finding, batch_id=self.batch['id'], time=time.time(), evidence=core.tree(out))
        record_path = out/'failure.json'
        core.atomic(record_path, record)
        failures = list((self.hold or {}).get('failures', []))
        failures.append(dict(path=str(record_path), sha256=core.sha(record_path)))
        hold = dict(record, failures=failures)
        if self.operational_state == State.SAFETY_HALT or finding['state'] == State.SAFETY_HALT:
            self.halt(finding['reason'],hold)
            return
        if self.hold:
            hold['recoverable'] = self.hold.get('recoverable') is True and finding['recoverable']
            hold['isolation_guard_unresolved'] = (self.hold.get('isolation_guard_unresolved',False)
                                                 or finding.get('isolation_guard_unresolved',False))
        self.transition(State.DIAGNOSTIC_HOLD, hold)

    def try_recover(self):
        """Called only after a successful pinned diagnostic; no queue recovery verb."""
        if (self.home/'HALTED.json').exists():
            self.operational_state = State.SAFETY_HALT
        if self.operational_state != State.DIAGNOSTIC_HOLD or not recovery_allowed(self.hold,self.batch,now=time.time()):
            return False
        approved = [r for r in self.ledger.rows if r['kind']=='batch-authorized' and r.get('batch')==self.batch
                    and r.get('qualification_sha256')==self.seal_identity
                    and (r.get('genuine_owner_console') is True or self.qualification)]
        if not approved or not self.seal or core.digest(self.seal)!=self.seal_identity or self.stop():
            return False
        out = self.home/'evidence'/('recovery-'+uuid.uuid4().hex); out.mkdir()
        try:
            verify_seal(self.seal)
            for failure in self.hold['failures']:
                path = core.independent(failure['path'])
                if core.sha(path)!=failure['sha256']:
                    raise core.IntegrityFailure('diagnostic failure evidence changed')
                for rel,h in core.read_large(path)['evidence'].items():
                    if core.sha(core.independent(path.parent/rel))!=h:
                        raise core.IntegrityFailure('original attempt evidence changed: '+rel)
            from .recovery import validate
            validation = validate(out, self.seal, self.hold, self.batch)
            core.atomic(out/'validation.json', validation)
            if validation.get('passed') is not True:
                return False
            verify_seal(self.seal)
            if self.desktop is not None:
                self.desktop.check(out,'recovery')
            elif not self.qualification:
                return False
            # Recheck authorization after the independent validation consumes time.
            if self.stop() or not recovery_allowed(self.hold,self.batch,now=time.time()):
                return False
            if (self.home/'HALTED.json').exists():
                self.operational_state = State.SAFETY_HALT
                return False
            used = sum(r['kind']=='launch-claimed' and r.get('batch_id')==self.batch['id'] for r in self.ledger.rows)
            if not self.qualification and used >= self.batch['genuine_limit']:
                return False
            self.ledger.append('qualified-recovery', batch_id=self.batch['id'], hold=self.hold,
                               validation=str(out/'validation.json'), sha256=core.sha(out/'validation.json'))
            self.transition(State.RUNNING,None)
            return True
        except core.IntegrityFailure as e:
            self.halt(str(e))
        except Exception as e:
            core.atomic(out/'validation-error.json',dict(reason=str(e),passed=False))
        return False

    def publish(self, **values):
        core.atomic(self.home / "status.json", dict(batch=self.batch, pid=os.getpid(), halted=self.halted,
                                                   operational_state=self.operational_state, hold=self.hold,
                                                   stop_file=str(self.home / "STOP"), **values))

    def process(self, path):
        claimed = self.home / "processing" / path.name
        core.require(not claimed.exists(), "duplicate processing path")
        os.rename(path, claimed)
        out = self.home / "evidence" / uuid.uuid4().hex
        out.mkdir()
        result = dict(version=1, request_file=path.name, batch_id=self.batch["id"], evidence=str(out),
                      started_at=time.time(), gameplay_verified=False, strict_x87="FAILED; retained separately",
                      strict_wndproc_equality="FAILED; retained separately")
        request = manifest = None
        reserved = False
        finding = None
        try:
            core.require(not self.stop(), "supervisor stopping")
            request = core.parse_request(core.read(claimed), self.batch)
            if (self.home/'HALTED.json').exists():
                self.operational_state = State.SAFETY_HALT
            core.require(self.operational_state != State.SAFETY_HALT, 'SAFETY HALT; owner review required')
            core.require(self.operational_state == State.RUNNING or request['scope']==core.FIXTURE_SCOPE,
                         'DIAGNOSTIC HOLD; genuine execution blocked; pinned non-game diagnostics remain available')
            core.require(path.name == request["id"] + ".json", "request filename/ID mismatch")
            candidate_path = (core.independent(self.home/'candidates'/(request['id']+'.json')) if self.qualification else
                              core.project_path(request["candidate"], ["out/desktop-supervisor/candidates"]))
            raw_manifest = candidate_path.read_bytes()
            if hashlib.sha256(raw_manifest).hexdigest() != request["manifest_sha256"]:
                raise core.IntegrityFailure("manifest hash mismatch")
            manifest = core.loads(raw_manifest)
            exe = core.validate_manifest(manifest, request)
            core.require(not any(r.get("request_id") == request["id"] for r in self.ledger.rows), "replay request")
            if self.seal:
                verify_seal(self.seal)
                if manifest["kind"] == "fixture":
                    core.require(manifest["sha256"] == self.seal["fixture_sha256"], "fixture differs from qualification")
            if manifest["kind"] == "genuine":
                core.require(self.desktop is not None and self.seal is not None and not self.qualification, "genuine owner gate absent")
                core.require(manifest["dependencies"] == self.seal["candidate_dependencies"], "genuine dependencies must equal pinned profile")
                self.desktop.check(out, "request-preflight")
                from .helper_checks import qualify as qualify_helper
                try:
                    guard = qualify_helper(out, helper=core.ROOT/self.seal['helper']['path'])
                    core.require(guard['guard_verified'] and guard['helper_sha256']==self.seal['helper']['sha256'],
                                 'independent isolated disk-open guard verification required')
                except Exception as e:
                    raise core.IntegrityFailure('helper isolation preflight unverified: '+str(e)) from e
            # Reserve capacity durably before creating any graphical process.
            core.parse_request(request,self.batch)  # Expensive preflights cannot extend authorization.
            core.require(not self.stop(), 'supervisor stopped during preflight')
            self.ledger.claim(request, manifest, self.batch)
            reserved = True
            sandbox = core.ROOT / "sandbox_cmp" / ("desktop-" + request["id"])
            core.independent(sandbox)
            sandbox.mkdir(exist_ok=False)
            core.atomic(out / "request.json", request)
            core.atomic(out / "candidate.json", manifest)
            from .windows import FilePins
            with FilePins() as pins:
                pins.pin(exe, manifest["sha256"])
                for rel, expected in manifest["dependencies"].items():
                    pins.pin(core.ROOT / rel, expected)
                if manifest["kind"] == "fixture":
                    from .fixture import run
                    observed = run(manifest, request, out, sandbox, self.stop)
                else:
                    pins.pin(exe.with_suffix(".pdb"), manifest["pdb_sha256"])
                    from .genuine import run
                    observed = run(manifest, request, out, sandbox, self.stop, self.desktop, self.seal)
                core.validate_manifest(manifest, request)
            result.update(observed, sandbox=str(sandbox), id=request["id"])
            assurance = core.read(out/'assurance.json') if (out/'assurance.json').exists() else {}
            finding = decision(observed,assurance=assurance)
            result['failure_category'] = finding['category']
        except core.Rejected as e:
            result.update(classification='unclassified-discrepancy' if reserved else 'rejected', passed=False, reason=str(e))
            if reserved:
                assurance = core.read(out/'assurance.json') if (out/'assurance.json').exists() else {}
                finding = self.assess_failure(result,e,assurance,manifest,request)
                result['failure_category'] = finding['category']
        except BaseException as e:
            result.update(classification="integrity-or-unclassified-failure", passed=False, reason=str(e))
            (out / "exception.txt").write_text(traceback.format_exc())
            assurance = core.read(out/'assurance.json') if (out/'assurance.json').exists() else {}
            finding = self.assess_failure(result,e,assurance,manifest,request)
            result['failure_category'] = finding['category']
        result['operational_state'] = (finding['state'] if finding and finding['state']!=State.RUNNING else self.operational_state)
        if finding and finding['state']!=State.RUNNING:
            result['passed'] = False
        result["finished_at"] = time.time()
        self.ledger.append("result", request_id=request["id"] if request else path.stem,
                           classification=result["classification"], passed=result.get("passed", False))
        core.atomic(out / "result.json", result)
        if finding:
            self.apply_decision(finding,out)
        # A replay receives its own result; it cannot overwrite the original response.
        response = self.home / "responses" / path.name
        if response.exists():
            response = self.home / "responses" / (path.stem + "-rejected-" + uuid.uuid4().hex + ".json")
        core.atomic(response, result)
        os.rename(claimed, self.home / "archive" / (out.name + ".json"))
        return result

    def assess_failure(self, result, error, assurance, manifest, request):
        # Failed handlers must not skip the post-run manifest/source audit.
        if manifest is not None and request is not None:
            try:
                core.validate_manifest(manifest,request)
            except Exception as e:
                error = core.IntegrityFailure('failed attempt identity check: '+str(e))
        return decision(result,error=error,assurance=assurance)

    def serve(self):
        self.publish(state="waiting")
        while not self.stop():
            if time.time() > self.batch["expires_at"]:
                self.shutdown = True
                break
            files = sorted((self.home / "requests").glob("*.json"))
            if files:
                for p in files:
                    if self.stop():
                        break
                    self.publish(state="processing", request=p.name)
                    result = self.process(p)
                    print(result["classification"], p.name, flush=True)
                    self.publish(state="halted" if self.halted else "waiting")
                    if result.get('passed') and result.get('classification')=='fixture-complete':
                        self.try_recover()
                        self.publish(state='waiting' if not self.halted else 'halted')
            time.sleep(.2)
        self.publish(state="stopped")


def submit_fixture(case):
    batch = core.read(core.HOME / "status.json")["batch"]
    ident = str(uuid.uuid4())
    exe = core.ROOT / "experiments/xrt/build/desktop-supervisor/fixture.exe"
    manifest = dict(version=1, kind="fixture", executable=exe.relative_to(core.ROOT).as_posix(), sha256=core.sha(exe),
                    pdb_sha256=None, build_record=None, build_record_sha256=None,
                    sources={"tools/xrt/supervisor/fixture.c": core.sha(core.ROOT / "tools/xrt/supervisor/fixture.c")},
                    dependencies={}, fixture_case=case)
    core.atomic(core.HOME / "candidates" / (ident + ".json"), manifest)
    req = dict(version=1, id=ident, batch_id=batch["id"], created_at=time.time(), expires_at=time.time() + 240,
               objective="Verify persistent non-game request/result cycle: " + case,
               candidate="out/desktop-supervisor/candidates/" + ident + ".json",
               manifest_sha256=core.sha(core.HOME / "candidates" / (ident + ".json")),
               expected_stop=dict(kind="fixture-breakpoint" if case == "hard-stop" else "fixture-complete"),
               scope=core.FIXTURE_SCOPE, timeout_seconds=15)
    core.atomic(core.HOME / "requests" / (ident + ".json"), req)
    print(ident)


def submit_renderer(build_record, objective, fatal_format=None):
    status=core.read(core.HOME / "status.json")
    core.require(status["state"]=="waiting" and not status["halted"],"owner supervisor is not waiting")
    batch=status["batch"];core.require(batch["genuine_limit"]>0,"owner genuine batch absent")
    path=core.project_path(build_record,["out/recovery"])
    build=core.read_large(path)
    executable=Path(build["root"])/"xrt_ucc.exe"
    ident=str(uuid.uuid4())
    seal=core.read_large(core.HOME / "qualification.json")
    manifest=dict(version=1,kind="genuine",executable=executable.relative_to(core.ROOT).as_posix(),
        sha256=build["binary_sha256"],pdb_sha256=build["pdb_sha256"],build_record=build_record,
        build_record_sha256=core.sha(path),fixture_case=None,dependencies=seal["candidate_dependencies"],
        sources={p.relative_to(core.ROOT).as_posix():core.sha(p) for p in (core.ROOT / "experiments/xrt/runtime").rglob("*") if p.is_file()})
    expected=(dict(kind="unsupported-method",code=76,format=fatal_format) if fatal_format else
              dict(kind="first-unsupported-or-permanent",guest_address="0x0696f292"))
    candidate=core.HOME / "candidates" / (ident+".json")
    request=dict(version=1,id=ident,batch_id=batch["id"],created_at=time.time(),
        expires_at=min(time.time()+240,batch["expires_at"]),objective=objective,
        candidate=candidate.relative_to(core.ROOT).as_posix(),manifest_sha256="0"*64,
        expected_stop=expected,scope=core.SCOPE,timeout_seconds=60)
    # Complete reviewable identity/path validation before anything enters the queue.
    core.validate_manifest(manifest,request)
    core.atomic(candidate,manifest);request["manifest_sha256"]=core.sha(candidate)
    core.parse_request(request,batch)
    core.atomic(core.HOME / "requests" / (ident+".json"),request)
    print(ident)


def review_halt():
    """An explicit local owner review, never called by serve or a queue request."""
    from .environment import ordinary_user
    from .windows import Exclusive, FilePins
    ordinary_user()
    core.require(sys.stdin.isatty(), 'safety review requires the local owner console')
    with Exclusive(core.HOME/'supervisor.lock'):
        service=Service(core.HOME,0)
        core.require(service.halted, 'no operational hold to review')
        core.require(not list((core.HOME/'processing').glob('*.json')), 'preserve and investigate interrupted claims before review')
        seal=core.read_large(core.HOME/'qualification.json')
        core.require(seal.get('passed') is True and seal.get('helper_guard',{}).get('guard_verified') is True,
                     'current qualification and independent guard verification required')
        verify_seal(seal)
        identity=core.digest(seal)
        print('Review supervisor enforcement changes, qualification evidence, and the original halt before accepting.')
        print('Qualification:',identity,'Evidence:',seal['evidence'])
        print('Current hold:',service.hold or core.read(core.HOME/'HALTED.json'))
        phrase='REVIEW SAFETY HALT '+identity[:16]
        print('Type exactly:',phrase)
        core.require(input().strip()==phrase,'owner safety review not accepted')
        verify_seal(seal)
        archive=core.HOME/'owner-reviews'/str(uuid.uuid4());archive.mkdir(parents=True)
        latch=core.HOME/'HALTED.json'
        record=dict(reviewed_at=time.time(),qualification_sha256=identity,qualification_evidence=seal['evidence'],
                    previous_hold=service.hold,original_halt_sha256=core.sha(latch) if latch.exists() else None,
                    ledger_rows_before=len(service.ledger.rows),fresh_authorization_required=True)
        core.atomic(archive/'review.json',record)
        # Append review before archiving. Interruption remains closed by either
        # the latch or the previous durable safety transition; no batch is resumed.
        service.ledger.append('owner-safety-review',review=str(archive/'review.json'),**record)
        if latch.exists():
            core.independent(latch);core.independent(archive/'HALTED.json')
            os.rename(latch,archive/'HALTED.json')
        service.transition(State.RUNNING,None)
        service.publish(state='reviewed-stopped')
        print('Original halt archived at',archive,'; STOP remains. Start a fresh authorized batch after removing STOP.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--authorize-genuine-attempts", type=int, choices=range(1, 6))
    serve.add_argument("--fixtures-only", action="store_true")
    serve.add_argument('--recovery-policy', choices=(POLICY,))
    fixture = sub.add_parser("submit-fixture")
    fixture.add_argument("case", choices=("ok-a", "ok-b", "hard-stop", "routine-failure"))
    renderer=sub.add_parser("submit-renderer")
    renderer.add_argument("--build-record",required=True)
    renderer.add_argument("--objective",required=True)
    renderer.add_argument("--expected-fatal-format")
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("qualify")
    sub.add_parser('review-halt', help='Owner console only; archive reviewed halt and require a fresh batch')
    args = ap.parse_args()
    if args.command == "qualify":
        from .qualify import main as qualify
        qualify()
        return
    if args.command == 'review-halt':
        review_halt()
        return
    if args.command == "submit-fixture":
        submit_fixture(args.case)
        return
    if args.command == "submit-renderer":
        submit_renderer(args.build_record,args.objective,args.expected_fatal_format)
        return
    if args.command == "stop":
        (core.HOME / "STOP").touch(exist_ok=True)
        print("Stop requested. Active child tree will be terminated.")
        return
    if args.command == "status":
        print(json.dumps(core.read(core.HOME / "status.json"), indent=2))
        return
    core.require(bool(args.fixtures_only) != bool(args.authorize_genuine_attempts), "choose fixtures-only or explicit genuine batch")
    core.require(not args.recovery_policy or args.authorize_genuine_attempts, 'recovery policy requires owner genuine authorization')
    core.require(not sys.flags.optimize and os.name == "nt", "Windows with assertions required")
    from .windows import Exclusive, FilePins
    from .environment import ordinary_user, Desktop
    ordinary_user()
    core.HOME.mkdir(parents=True, exist_ok=True)
    with Exclusive(core.HOME / "supervisor.lock"):
        service = Service(core.HOME, args.authorize_genuine_attempts or 0)
        core.require(service.operational_state!=State.SAFETY_HALT, "HALTED.json requires owner investigation; see documentation")
        core.require(not service.halted or args.fixtures_only, 'restart of DIAGNOSTIC HOLD permits fixtures only; prior authorization is not renewed')
        core.require(not (core.HOME / "STOP").exists(), "remove STOP locally before starting a new owner batch")
        seal = core.read_large(core.HOME / "qualification.json")
        core.require(seal.get("passed") is True, "non-game qualification must pass")
        verify_seal(seal)
        with FilePins() as pins:
            for rel, expected in seal["files"].items():
                pins.pin(core.ROOT / rel, expected)
            for path,expected in seal["host_files"].items():
                pins.pin(Path(path),expected)
            service.bind_seal(seal)
            startup = service.home / "evidence" / ("startup-" + service.batch["id"])
            startup.mkdir()
            if args.authorize_genuine_attempts:
                core.require(sys.stdin.isatty(), "owner must authorize on their local interactive console")
                service.desktop = Desktop()
                service.desktop.check(startup, "first")
                service.desktop.check(startup, "second")
                phrase = "AUTHORIZE " + str(args.authorize_genuine_attempts) + " RENDERER INIT"
                if args.recovery_policy:
                    service.batch['recovery_policy'] = args.recovery_policy
                    phrase += ' WITH ' + args.recovery_policy.upper()
                print("Batch scope: renderer initialization; permanent stop before guest 0x0696f292; 60s/attempt; no retry.")
                print("Type exactly: " + phrase)
                core.require(input().strip() == phrase, "owner batch not authorized")
            service.ledger.append("batch-authorized", batch=service.batch, genuine_owner_console=bool(args.authorize_genuine_attempts),
                                  qualification_sha256=service.seal_identity)
            core.atomic(startup / "authorization.json", service.batch)
            def shutdown(*_):
                service.shutdown = True
            signal.signal(signal.SIGINT, shutdown)
            signal.signal(signal.SIGTERM, shutdown)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, shutdown)
            print("Supervisor waiting. Ctrl+C or desktop_supervisor.py stop terminates the active child tree.", flush=True)
            service.serve()

