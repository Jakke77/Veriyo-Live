"""CI-only native surface smoke check. Does not change wallpaper/lock settings."""
import ctypes
import faulthandler
import traceback
from ctypes import wintypes
import os
from pathlib import Path
import sys

faulthandler.enable()
def exception_hook(kind,value,trace):
    traceback.print_exception(kind,value,trace)
    sys.stderr.flush()
sys.excepthook=exception_hook
print('Native surface: process started',flush=True)
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if os.name!='nt':raise SystemExit('Windows only')
user=ctypes.WinDLL('user32',use_last_error=True)
user.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];user.FindWindowW.restype=wintypes.HWND
if not user.FindWindowW('Progman',None):
    print('SKIP: runner has no interactive Explorer desktop; visible WorkerW motion needs a desktop check')
    raise SystemExit(0)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import qInstallMessageHandler
qInstallMessageHandler(lambda kind,context,message: print("Qt:",message,flush=True))
from PyQt6.QtTest import QTest
from veriyo_live.ubuntu_pack import MotionEntry
from veriyo_live.windows_motion import MotionDesktop
print('Native surface: creating QApplication',flush=True)
app=QApplication([])
print('Native surface: screens',len(app.screens()),flush=True)
user.GetForegroundWindow.restype=wintypes.HWND
user.GetParent.argtypes=[wintypes.HWND];user.GetParent.restype=wintypes.HWND
foreground=user.GetForegroundWindow()
entry=MotionEntry('test','test','test',(ROOT/'veriyo_live/assets/otava.png',ROOT/'veriyo_live/assets/hiillos.png'),48)
print('Native surface: creating WorkerW child',flush=True)
errors=[];surface=MotionDesktop(entry,errors.append)
print('Native surface: child created',flush=True)
try:
    for _ in range(20):app.processEvents();QTest.qWait(100)
    assert not errors,errors
    assert user.GetParent(int(surface.winId()))==surface.parent_handle
    assert user.GetForegroundWindow()==foreground,'Background surface stole focus'
    print('PASS: native WorkerW child created, rendered, left focus unchanged and closed safely')
finally:
    surface.shutdown();app.processEvents()
