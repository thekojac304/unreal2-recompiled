"""Explicit race/error doubles plus real x86/x64 non-graphical mapping checks."""
import contextlib
import copy
import ctypes as C
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid
import prepare_evidence as E
from evidence_capture import Collector,read,save
import evidence_check as A
import module_identity as M


class Provider:
    creation=123
    def __init__(self):
        self.bases=[1];self.rounds=None;self.errors={};self.unmapped=set();self.alias=False
    def enumerate(self):return self.rounds.pop(0) if self.rounds else list(self.bases)
    def check_creation(self):pass
    def probe(self,base):
        return dict(base=base,allocation_base=base,mapped=base not in self.unmapped,
            mapped_path='\\Device\\Volume\\Windows\\SysWOW64\\test.dll',
            reported_path='C:\\Windows\\System32\\test.dll',machine=0x14c,timestamp=17,size_of_image=4096)
    @contextlib.contextmanager
    def pin_image(self,probe):
        if probe['base'] in self.errors:raise self.errors[probe['base']]
        yield dict(path='C:\\Windows\\SysWOW64\\test.dll',sha256='1'*64,machine=0x14c,timestamp=17,size_of_image=4096)


class ModuleIdentityTests(unittest.TestCase):
    def test_path_alias_uses_kernel_mapping(self):
        p=Provider();modules,r=M.collect(p,[dict(base=1,path='C:\\Windows\\System32\\test.dll')])
        self.assertTrue(r['complete']);self.assertEqual(modules[0]['path'],'C:\\Windows\\SysWOW64\\test.dll')
        self.assertEqual(modules[0]['reported_path'],'C:\\Windows\\System32\\test.dll')
    def test_missing_file_is_unresolved_not_hashed(self):
        p=Provider();p.errors[1]=FileNotFoundError(2,'missing image')
        modules,r=M.collect(p,[]);self.assertFalse(r['complete']);self.assertEqual(modules,[])
        self.assertEqual(r['unresolved'][0]['category'],'missing-file');self.assertEqual(len(r['rounds']),3)
        self.assertEqual(r['unresolved'][0]['memory_image']['mapped_path'],p.probe(1)['mapped_path'])
    def test_access_denied_is_distinct(self):
        p=Provider();p.errors[1]=PermissionError(13,'inaccessible image')
        modules,r=M.collect(p,[]);self.assertFalse(r['complete']);self.assertEqual(modules,[])
        self.assertEqual(r['unresolved'][0]['category'],'access-denied')
    def test_unloaded_module_has_explicit_absence_proof(self):
        p=Provider();p.bases=[2];p.unmapped.add(1)
        modules,r=M.collect(p,[dict(base=1,path='unloaded.dll')])
        self.assertTrue(r['complete']);self.assertEqual([m['base'] for m in modules],[2])
        self.assertEqual(r['unloaded'][0]['status'],'unloaded');self.assertNotIn('sha256',r['unloaded'][0])
    def test_stale_loader_enumeration_retries(self):
        p=Provider();p.rounds=[[1,2],[2],[2],[2]];p.unmapped.add(1)
        modules,r=M.collect(p,[]);self.assertTrue(r['complete']);self.assertEqual(len(r['rounds']),2)
        self.assertEqual([m['base'] for m in modules],[2])
    def test_absent_from_loader_but_still_mapped_is_unresolved(self):
        p=Provider();p.bases=[2]
        modules,r=M.collect(p,[dict(base=1,path='hidden.dll')]);self.assertFalse(r['complete'])
        self.assertIn('still mapped',r['rounds'][0]['unresolved'][0]['message'])
    def test_unstable_enumeration_rejected(self):
        p=Provider();p.rounds=[[1],[1,2]]*3
        modules,r=M.collect(p,[]);self.assertFalse(r['complete']);self.assertEqual(r['unresolved'][0]['category'],'enumeration-unstable')
    def test_changed_mapping_rejected(self):
        p=Provider();original=p.probe;count=0
        def probe(base):
            nonlocal count
            result=original(base);count+=1;result['timestamp']+=count%2
            return result
        p.probe=probe;modules,r=M.collect(p,[]);self.assertFalse(r['complete'])
    def test_partial_copy_only_allowed_before_first_resume(self):
        p=Provider();error=OSError('loader unavailable');error.winerror=299
        def enumerate():raise error
        p.enumerate=enumerate
        self.assertEqual(M.collect(p,[],pre_resume=True)[1]['status'],'pre-resume-loader-unavailable')
        self.assertFalse(M.collect(p,[])[1]['complete'])
        self.assertFalse(M.collect(p,[dict(base=1,path='reported.dll')],pre_resume=True)[1]['complete'])
    def test_pinned_driver_and_project_images_are_not_skipped(self):
        for name in ['d3d8.dll','nvoglv64.dll','collector.dll']:
            with self.subTest(name=name):
                p=Provider();p.errors[1]=FileNotFoundError(2,'missing mapped image')
                modules,r=M.collect(p,[dict(base=1,path=name)])
                self.assertFalse(r['complete']);self.assertEqual(modules,[])
    def test_empty_loader_list_requires_pre_resume_stage(self):
        p=Provider();p.bases=[]
        self.assertFalse(M.collect(p,[])[1]['complete'])
        self.assertEqual(M.collect(p,[],pre_resume=True)[1]['status'],'pre-resume-loader-unavailable')
    def test_mapped_pe_must_match_file(self):
        p=Provider();original=p.pin_image
        @contextlib.contextmanager
        def pin_image(probe):
            with original(probe) as disk:
                disk['timestamp']+=1;yield disk
        p.pin_image=pin_image;modules,r=M.collect(p,[])
        self.assertFalse(r['complete']);self.assertIn('PE metadata differs',r['unresolved'][0]['message'])


class LiveModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=E.O/('module-validation-'+uuid.uuid4().hex);cls.root.mkdir();cls.runs={}
        for arch in ['x86','x64']:
            b=E.O/'build'/('module-probe-v2-'+arch);d=cls.root/arch
            Collector().capture(b/'fixture.exe',[],d,build_record=b/'build-record.json')
            cls.runs[arch]=d
        save(cls.root/'scope.json',dict(graphics_devices_created=0,genuine_launches=0,scope='version.dll kernel-mapping identity and WOW64 redirection'))
    def check(self,arch):
        d=self.runs[arch];b=E.O/'build'/('module-probe-v2-'+arch)
        rs,s,events=A.process(d,physical=False,expected_exe=b/'fixture.exe',expected_args=[],expected_build=b/'build-record.json')
        self.assertEqual(len(rs),1);self.assertTrue(rs[0]['released']);self.assertFalse(rs[0]['graphics'])
        module=next(m for m in s['modules'] if m['base']==rs[0]['base'])
        self.assertEqual(module['identity_status'],'verified')
        self.assertEqual(module['machine'],0x14c if arch=='x86' else 0x8664)
        if arch=='x86':self.assertIn('syswow64',module['path'].lower());self.assertTrue(module['memory_image']['wow64'])
        self.assertEqual(module['sha256'],E.P.core.sha(Path(module['path'])))
        save(self.root/(arch+'-verified-module.json'),module)
    def test_live_x86_wow64_mapped_path(self):self.check('x86')
    def test_live_x64_mapped_path(self):self.check('x64')
    def test_unresolved_loaded_identity_rejected(self):
        s=copy.deepcopy(read(self.runs['x64']/'loaded-environment.json'))
        s['modules'][0]['identity_status']='unresolved';s['modules'][0].pop('sha256')
        with self.assertRaises(M.IdentityIncomplete):M.verify_snapshot(s)
    def test_missing_file_hash_rejected(self):
        s=copy.deepcopy(read(self.runs['x64']/'loaded-environment.json'));s['modules'][0]['sha256']='0'*64
        with self.assertRaises(M.IdentityIncomplete):M.verify_snapshot(s)
    def test_file_identity_substitution_rejected(self):
        s=copy.deepcopy(read(self.runs['x64']/'loaded-environment.json'));s['modules'][0]['file_id']['index']+=1
        with self.assertRaises(M.IdentityIncomplete):M.verify_snapshot(s)
    def test_pre_resume_exception_not_allowed_at_checkpoint(self):
        s=read(self.runs['x64']/'suspended.json')
        if s['module_identity']['status']=='pre-resume-loader-unavailable':
            with self.assertRaises(M.IdentityIncomplete):M.verify_snapshot(s)
    def test_real_missing_file_error_is_retained(self):
        with self.assertRaises(OSError) as caught:
            with M.WindowsFiles().pin(self.root/'absent-image.dll'):pass
        self.assertEqual(caught.exception.winerror,2)
    def test_file_pin_denies_write_handle(self):
        files=M.WindowsFiles();path=E.O/'build/x64/disposable.dll'
        before=E.P.core.sha(path)
        with files.pin(path):
            h=files.open(str(path),0x40000000,7,None,3,0,None)
            code=C.get_last_error()
            if h!=C.c_void_p(-1).value:files.close(h)
            self.assertEqual(h,C.c_void_p(-1).value);self.assertEqual(code,32)
        self.assertEqual(E.P.core.sha(path),before)
    def test_open_process_denial_saves_unresolved_receipt(self):
        path=self.root/'denied-process.json'
        with patch('evidence_capture.WindowsProcess',side_effect=PermissionError(13,'test denied')):
            with self.assertRaises(PermissionError):Collector().snapshot(os.getpid(),path)
        s=read(path);self.assertEqual(s['module_identity']['status'],'unresolved')
        self.assertFalse(s['modules_complete']);self.assertTrue(all(m['identity_status']=='unresolved' for m in s['modules']))
        self.assertTrue(path.with_name(path.stem+'.raw.json').exists())
    def test_non_image_mapping_forgery_rejected(self):
        s=copy.deepcopy(read(self.runs['x64']/'loaded-environment.json'));s['modules'][0]['memory_image']['type']=0x20000
        with self.assertRaises(M.IdentityIncomplete):M.verify_snapshot(s)
    def test_precise_clock_fast_exit_repeated(self):
        for arch in ['x86','x64']:
            b=E.O/'build'/('module-probe-v2-'+arch)
            for repeat in range(3):
                d=self.root/f'clock-{arch}-{repeat}'
                Collector().capture(b/'fixture.exe',[],d,build_record=b/'build-record.json')
                A.process(d,physical=False,expected_exe=b/'fixture.exe',expected_args=[],expected_build=b/'build-record.json')


if __name__=='__main__':unittest.main()
