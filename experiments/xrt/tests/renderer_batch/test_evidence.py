"""Disposable OS tests and synthetic negative tests. No GPU compatibility claim."""
import copy, json, shutil, struct, unittest, uuid
from pathlib import Path
import prepare_evidence as E
import evidence_check as A
from evidence_capture import Collector, save, read
P=E.P
class CollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=E.O/('validation-'+uuid.uuid4().hex);cls.root.mkdir();cls.collector=Collector();cls.runs={}
        for arch in ['x86','x64']:
            b=E.O/'build'/arch;d=cls.root/arch
            cls.collector.capture(b/'smoke.exe',['--smoke'],d,build_record=b/'build-record.json',backend=[b/'disposable.dll'],extra_env={'XRT_SMOKE_DLL':str(b/'disposable.dll')})
            cls.runs[arch]=d
        save(cls.root/'scope.json',dict(graphics_devices_created=0,genuine_launches=0,scope='message-only HWND and disposable DLL; no renderer test executed'))

    def check(self,d,arch='x64'):
        b=E.O/'build'/arch
        rs,s,events=A.process(d,physical=False,expected_exe=b/'smoke.exe',expected_args=['--smoke'],expected_build=b/'build-record.json',expected_backend=[b/'disposable.dll'])
        self.assertEqual(rs,[dict(kind='smoke-cleanup',destroyed=True,window_valid=False,unloaded=True,module_loaded=False)])
        self.assertEqual([e['event'] for e in events],['smoke-observation'])
    def test_actual_x86(self):self.check(self.runs['x86'],'x86')
    def test_actual_x64(self):self.check(self.runs['x64'])
    def test_actual_group_abi_and_runtime_streams(self):
        reports=[]
        for group in range(1,8):
            for arch,translated in [('x86',False),('x64',False),('x64',True)]:
                name=f'{P.GROUPS[group]}-{arch}-{"translated" if translated else "native"}';b=E.O/'build'/name;d=self.root/('abi-'+name)
                self.collector.capture(b/'fixture.exe',['--abi-evidence'],d,build_record=b/'build-record.json')
                rs,s,events=A.process(d,physical=False,expected_exe=b/'fixture.exe',expected_args=['--abi-evidence'],expected_build=b/'build-record.json')
                expected=[c for c in A.read(P.O/'cases.json')['cases'] if c['group']==group for seed in range(4) for repeat in range(2)]
                self.assertEqual(len(rs),len(expected)+1)
                for r in rs[:-1]:A.abi(r,arch);self.assertEqual(r['kind'],'call');self.assertEqual(r['hr'],0);self.assertEqual(r['seed'],r['error'])
                self.assertEqual(rs[-1],dict(kind='abi-only-summary',passed=True,calls=len(expected),graphics=False,double_only=True))
                self.assertEqual(len(events),len(expected)*2 if translated else 0)
                if translated:self.assertEqual([e['event'] for e in events],['adapter-enter','adapter-leave']*len(expected))
                reports.append(dict(group=group,arch=arch,translated=translated,calls=len(expected),runtime_events=len(events),graphics=False))
        save(self.root/'actual-abi-results.json',reports)
    def rejection(self,file,mutate=None,remove=False):
        # Rewrite cwd only to bind the disposable copy to its own location.
        d=self.root/uuid.uuid4().hex;shutil.copytree(self.runs['x64'],d)
        r=read(d/'process.json');r['cwd']=str(d);save(d/'process.json',r)
        if remove:(d/file).unlink()
        else:
            v=read(d/file);mutate(v)
            if file.endswith('.jsonl'):(d/file).write_text(json.dumps(v)+'\n')
            else:save(d/file,v)
        with self.assertRaises((A.Incomplete,KeyError,FileNotFoundError,ValueError)):self.check(d)
    def test_missing_environment(self):self.rejection('loaded-environment.json',remove=True)
    def test_missing_owner(self):self.rejection('owner-before.json',lambda v:v.update(owner_sid=''))
    def test_wrong_pid(self):self.rejection('loaded-environment.json',lambda v:v.update(pid=1))
    def test_reused_pid(self):self.rejection('exit.json',lambda v:v.update(creation_filetime=1))
    def test_wrong_executable(self):self.rejection('process.json',lambda v:v.update(executable_sha256='0'*64))
    def test_wrong_command(self):self.rejection('process.json',lambda v:v['command'].append('--forged'))
    def test_missing_backend_binding(self):self.rejection('process.json',lambda v:v.update(backend={}))
    def test_missing_build_binding(self):self.rejection('process.json',lambda v:v.update(build_record_sha256=None))
    def test_wrong_child_owner(self):self.rejection('loaded-environment.json',lambda v:v.update(owner_sid='S-1-0'))
    def test_wrong_desktop(self):self.rejection('loaded-self.json',lambda v:v.update(desktop='other'))
    def test_environment_outside_lifetime(self):self.rejection('loaded-environment.json',lambda v:v.update(filetime=1))
    def test_missing_module_list(self):self.rejection('loaded-environment.json',lambda v:v.update(modules_complete=False))
    def test_unloaded_before_capture(self):
        self.rejection('loaded-environment.json',lambda v:v.update(modules=[m for m in v['modules'] if Path(m['path']).name!='disposable.dll']))
    def test_module_still_loaded(self):
        module=next(m for m in read(self.runs['x64']/'loaded-environment.json')['modules'] if Path(m['path']).name=='disposable.dll')
        self.rejection('cleaned-environment.json',lambda v:v['modules'].append(module))
    def test_process_not_exited(self):self.rejection('exit.json',lambda v:v.update(wait=258))
    def test_exit_observation_predates_kernel_exit(self):
        self.rejection('exit.json',lambda v:v.update(observed_filetime=v['exit_filetime']-1))
    def test_descendant_missing(self):self.rejection('exit.json',lambda v:v.update(total_processes=2))
    def test_process_tree_leak(self):self.rejection('exit.json',lambda v:v.update(active_processes=1))
    def test_job_missing(self):self.rejection('exit.json',lambda v:v.update(assigned_before_resume=False))
    def test_job_membership_missing(self):self.rejection('loaded-job.json',remove=True)
    def test_job_member_unknown(self):self.rejection('loaded-job.json',lambda v:v['pids'].append(1))
    def test_job_member_wrong_image(self):self.rejection('loaded-job.json',lambda v:v['processes'][0].update(image='other.exe'))
    def test_forced_cleanup(self):self.rejection('process.json',lambda v:v.update(forced_cleanup=True))
    def test_invented_drop_count(self):self.rejection('cleaned-self.json',lambda v:v['runtime_stream'].update(dropped_event_count=0))
    def test_runtime_write_error(self):self.rejection('cleaned-self.json',lambda v:v['runtime_stream'].update(write_errors=1))
    def test_runtime_missing(self):self.rejection('runtime-events.jsonl',remove=True)
    def test_runtime_count_mismatch(self):self.rejection('cleaned-self.json',lambda v:v['runtime_stream'].update(written=2))
    def test_runtime_wrong_pid(self):self.rejection('runtime-events.jsonl',lambda v:v.update(pid=1))
    def test_runtime_gap(self):self.rejection('runtime-events.jsonl',lambda v:v.update(sequence=2))
    def test_runtime_stale(self):self.rejection('runtime-events.jsonl',lambda v:v.update(filetime=1))
    def test_actual_early_exit_cleanup(self):
        b=E.O/'build/x64';d=self.root/'early-exit'
        with self.assertRaises(AssertionError):self.collector.capture(b/'smoke.exe',['--early-exit'],d)
        r=read(d/'failure-exit.json');self.assertEqual(r['active_processes'],0);self.assertEqual(r['exit'],17)
        self.assertTrue(read(d/'process.json')['forced_cleanup'])
    def test_actual_timeout_cleanup(self):
        b=E.O/'build/x64';d=self.root/'timeout'
        with self.assertRaises(AssertionError):self.collector.capture(b/'smoke.exe',['--linger'],d,timeout_ms=200)
        r=read(d/'failure-exit.json');self.assertEqual(r['active_processes'],0);self.assertEqual(r['exit'],98)
    def test_actual_descendant_cleanup(self):
        b=E.O/'build/x64';d=self.root/'descendant'
        with self.assertRaises(AssertionError):self.collector.capture(b/'smoke.exe',['--spawn-descendant'],d,extra_env={'XRT_SMOKE_DLL':str(b/'disposable.dll')})
        r=read(d/'failure-exit.json');self.assertEqual(r['active_processes'],0);self.assertEqual(r['total_processes'],2)

class SyntheticRejections(unittest.TestCase):
    def abi(self,arch='x64'):
        pre=bytearray(512);pre[:2]=b'\x7f\x02';pre[24:28]=struct.pack('<I',0x3f80)
        return dict(regs=([0x12345678,0x23456789,0x3456789a,0x456789ab,0,0,0,0] if arch=='x86' else [0x1111111112345678,0x2222222223456789,0x333333333456789a,0x44444444456789ab,0x5555555556789abc,0x666666666789abcd,0x77777777789abcde,0x8888888889abcdef]),
            xmm=(bytes(160) if arch=='x86' else struct.pack('<4I',0x12345678,0x23456789,0x3456789a,0x456789ab)*10).hex(),pre=pre.hex(),post=pre.hex(),stack_delta=0)
    def synthetic(self):
        rs=[dict(kind='create',hr=0,nonnull=True),dict(kind='ownership',add=2,balance=1,parent_hr=0,same_parent=True,parent_release=2,creation_hr=0,same_window=True,flags=66),dict(kind='adapter-identity'),dict(kind='backend-adapter')]
        for c in A.read(P.O/'cases.json')['cases']:
            if c['group']!=1:continue
            for seed in [18,0,0x13572468,0xffffffff]:
                for _ in range(2):
                    rs.append(dict(c,**self.abi(),kind='call',seed=seed,error=seed,hr=0,fpu_preserved=True))
                    rs.append(dict(kind='readback',slot=c['slot'],hr=0,equal=True,value=c['b'],extra=0xa5a5a5a5))
        rs.extend([dict(kind='release',device_release=0,parent_release=0),dict(kind='lifecycle',destroyed=True,unregistered=True,window_valid=False,free_d3d8=True,free_d3d9=True,d3d8_loaded=False,d3d9_loaded=False),dict(kind='summary',passed=True,calls=16,graphics=True,translated=False)])
        return rs
    def reject(self,mutate):
        rs=self.synthetic();mutate(rs)
        with self.assertRaises((A.Incomplete,KeyError,ValueError)):A.group_observations(rs,1,'x64',False,[])
    def test_schema_only_positive(self):self.assertEqual(len(A.group_observations(self.synthetic(),1,'x64',False,[])),16)
    def test_missing_abi(self):self.reject(lambda r:r[4].pop('regs'))
    def test_bad_gpr(self):self.reject(lambda r:r[4]['regs'].__setitem__(0,0))
    def test_bad_xmm(self):self.reject(lambda r:r[4].update(xmm='00'*160))
    def test_x87_status(self):self.reject(lambda r:r[4].update(post='00'*512))
    def test_mxcsr_changed(self):
        def change(r):
            b=bytearray.fromhex(r[4]['post']);b[24]^=1;r[4]['post']=b.hex()
        self.reject(change)
    def test_ownership_absent(self):self.reject(lambda r:r.pop(1))
    def test_ownership_forged(self):self.reject(lambda r:r[1].update(add=999))
    def test_leaked_com(self):self.reject(lambda r:r[-3].update(device_release=1))
    def test_missing_window_observation(self):self.reject(lambda r:r[-2].pop('destroyed'))
    def test_failed_window_destruction(self):self.reject(lambda r:r[-2].update(destroyed=False))
    def test_window_still_alive(self):self.reject(lambda r:r[-2].update(window_valid=True))
    def test_module_not_unloaded(self):self.reject(lambda r:r[-2].update(d3d9_loaded=True))
    def test_runtime_stdout_conflated(self):self.reject(lambda r:r.insert(5,dict(kind='adapter-enter')))
    def test_missing_call(self):self.reject(lambda r:r.pop(4))
    def test_hresult_unchanged(self):self.reject(lambda r:r[4].update(hr=0x8876086c))
    def test_last_error_failure(self):self.reject(lambda r:r[4].update(error=0))
    def test_readback_changed(self):self.reject(lambda r:r[5].update(value=999))
    def test_runtime_stream_required_translated(self):
        r=self.synthetic();r[-1]['translated']=True
        with self.assertRaises(A.Incomplete):A.group_observations(r,1,'x64',True,[])
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):P.core.loads(b'{"x":1,"x":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(ValueError):P.core.loads(b'{"x":NaN}')
    def test_missing_physical_desktop(self):
        s=dict(pid=1,collector_pid=2,filetime=1,creation_filetime=1,image='synthetic',image_sha256='0'*64,owner_sid='S-1-0',user='synthetic',domain='synthetic',window_station='WinSta0',station_flags_ok=True,station_flags=1,desktop='Default',input_desktop='Default',session=1,collector_session=1,active_console=1,protocol=0,connect_state=0,remote=False,display_status=0,paths=[dict(source_status=0,target_status=0,gdi_name='synthetic',monitor_path='synthetic',width=1,height=1,refresh_d=1)],dxgi_hr=0,adapters=[{}],display_devices=[{}])
        A.environment(s,physical=True)
        for field,value in [('active_console',2),('protocol',2),('connect_state',4),('remote',True),('input_desktop','Winlogon'),('station_flags',0),('paths',[]),('adapters',[])]:
            bad=copy.deepcopy(s);bad[field]=value
            with self.subTest(field=field),self.assertRaises(A.Incomplete):A.environment(bad,physical=True)

class AdapterRejections(unittest.TestCase):
    def setUp(self):
        self.root=E.O/('synthetic-adapter-'+uuid.uuid4().hex);self.root.mkdir()
        (self.root/'fixture_d3d9.log').write_text('info: DXVK: v3.1.1\ninfo: Creating device:\ninfo: Synthetic GPU:\n')
        self.rs=[dict(kind='backend-adapter',hr=0,ordinal=0,luid_low=123,luid_high=0,query_parent_release=0)]
        self.s=dict(adapters=[dict(name='Synthetic GPU',vendor=0x10de,device=1,subsystem=2,revision=3,flags=0,luid_low=123,luid_high=0)],paths=[dict(source_luid_low=123,source_luid_high=0)],
            modules=[dict(path='synthetic/nvoglv64.dll',company='NVIDIA Corporation',version_ok=True,version_ms=1,machine=0x8664,sha256='synthetic-not-evidence')])
    def check(self):return A.adapter(self.rs,self.s,self.root,'x64')
    def test_schema_only_positive(self):self.assertEqual(self.check()['adapter']['luid_low'],123)
    def reject(self,mutate):
        mutate()
        with self.assertRaises((A.Incomplete,KeyError)):self.check()
    def test_missing_luid(self):self.reject(lambda:self.rs.clear())
    def test_failed_luid_query(self):self.reject(lambda:self.rs[0].update(hr=1))
    def test_wrong_luid(self):self.reject(lambda:self.rs[0].update(luid_low=999))
    def test_ambiguous_adapter(self):self.reject(lambda:self.s['adapters'].append(copy.deepcopy(self.s['adapters'][0])))
    def test_software_adapter(self):self.reject(lambda:self.s['adapters'][0].update(flags=2))
    def test_no_display_binding(self):self.reject(lambda:self.s['paths'].clear())
    def test_driver_missing(self):self.reject(lambda:self.s['modules'].clear())
    def test_driver_version_missing(self):self.reject(lambda:self.s['modules'][0].update(version_ok=False))
    def test_wrong_driver_vendor(self):self.reject(lambda:self.s['modules'][0].update(company='Microsoft'))
    def test_vendor_overlay_insufficient(self):self.reject(lambda:self.s['modules'][0].update(path='synthetic/overlay.dll'))
    def test_wrong_driver_architecture(self):self.reject(lambda:self.s['modules'][0].update(machine=0x14c))
    def test_log_missing(self):self.reject(lambda:(self.root/'fixture_d3d9.log').unlink())
    def test_log_wrong_adapter(self):self.reject(lambda:self.s['adapters'][0].update(name='Other GPU'))

if __name__=='__main__':unittest.main()
