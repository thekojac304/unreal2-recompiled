"""Fresh interpreter for non-game inert mapping/production factory checks."""
import importlib.util
import sys
from recheck import OUT,SOURCE
import common
common.O=OUT/'continuation-proposal'
spec=importlib.util.spec_from_file_location('observer',common.O/'observer.py')
m=importlib.util.module_from_spec(spec);sys.modules['observer']=m;spec.loader.exec_module(m)
import qualify
qualify.main()
