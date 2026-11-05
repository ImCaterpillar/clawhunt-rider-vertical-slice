# -*- coding: utf-8 -*-
"""Run all automated suites; browser E2E requires a running local server."""
import os, subprocess, sys
ROOT=os.path.dirname(os.path.abspath(__file__))
commands=[
    [sys.executable,'run_tests.py'],
    [sys.executable,'-m','unittest','test_workflow','test_dashboard','-v'],
    [sys.executable,'-m','unittest','test_api','-v'],
]
if os.environ.get('RUN_BROWSER_E2E')=='1':
    commands.append([sys.executable,'e2e.py'])
for command in commands:
    print('+',' '.join(command),flush=True)
    result=subprocess.run(command,cwd=ROOT)
    if result.returncode: raise SystemExit(result.returncode)
print('ALL ENABLED CHECKS PASSED')
