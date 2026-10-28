"""CI-only native surface smoke check. Does not change wallpaper/lock settings."""
import ctypes
import faulthandler
import traceback
from ctypes import wintypes
import os
from pathlib import Path
import sys
from unittest.mock import patch

faulthandler.enable()
exceptions=[]
def exception_hook(kind,value,trace):
    exceptions.append(str(value))
    traceback.print_exception(kind,value,trace)
    sys.stderr.flush()
sys.excepthook=exception_hook
print('Native surface: process started',flush=True)
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
if os.name!='nt':raise SystemExit('Windows only')
user=ctypes.WinDLL('user32',use_last_error=True)
user.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];user.FindWindowW.restype=wintypes.HWND
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import qInstallMessageHandler,QCoreApplication,QEvent
qInstallMessageHandler(lambda kind,context,message: print("Qt:",message,flush=True))
from PyQt6.QtTest import QTest
from veriyo_live.ubuntu_pack import MotionEntry
from veriyo_live.windows_motion import MotionDesktop,DesktopSurfaceUnavailable
print('Native surface: creating QApplication',flush=True)
app=QApplication([sys.argv[0]])
print('Native surface: screens',len(app.screens()),flush=True)
user.GetForegroundWindow.restype=wintypes.HWND
user.GetParent.argtypes=[wintypes.HWND];user.GetParent.restype=wintypes.HWND
foreground=user.GetForegroundWindow()
entry=MotionEntry('test','test','test',(ROOT/'veriyo_live/assets/otava.png',ROOT/'veriyo_live/assets/hiillos.png'),48)
print('Native surface: creating WorkerW child',flush=True)
errors=[];synthetic=None
try:surface=MotionDesktop(entry,errors.append)
except DesktopSurfaceUnavailable as error:
    print('SKIP: Explorer on this runner exposes no WorkerW wallpaper surface. '+str(error),flush=True)
    user.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
                                  ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                                  wintypes.HWND,wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p]
    user.CreateWindowExW.restype=wintypes.HWND
    user.DestroyWindow.argtypes=[wintypes.HWND];user.DestroyWindow.restype=wintypes.BOOL
    synthetic=user.CreateWindowExW(0x08000080,'STATIC','Veriyo CI test surface',0x80000000,
                                   0,0,640,360,None,None,None,None)
    if not synthetic:raise ctypes.WinError(ctypes.get_last_error())
    with patch('veriyo_live.windows_motion.desktop_parent',return_value=synthetic):
        surface=MotionDesktop(entry,errors.append)
print('Native surface: child created',flush=True)
try:
    for _ in range(20):app.processEvents();QTest.qWait(100)
    assert not errors,errors
    assert not exceptions,exceptions
    assert user.GetParent(int(surface.winId()))==surface.parent_handle
    assert user.GetForegroundWindow()==foreground,'Background surface stole focus'
    image=surface.grab().toImage()
    assert not image.isNull()
    from veriyo_live.scenes import SceneEntry
    from veriyo_live.settings import Settings
    surface.entry=SceneEntry(Settings(theme='deep_space',date_mode='none'))
    for _ in range(10):app.processEvents();QTest.qWait(100)
    animated=surface.grab().toImage()
    assert not animated.isNull() and animated!=image
    assert not errors and not exceptions
    assert user.GetForegroundWindow()==foreground,'Procedural scene stole focus'
    print('PASS: native procedural scene rendered without changing focus or wallpaper settings',flush=True)
    for theme in ('stream','rose_garden','lighthouse'):
        surface.entry=SceneEntry(Settings(theme=theme,date_mode='none'))
        app.processEvents();first=surface.grab().toImage()
        for _ in range(5):app.processEvents();QTest.qWait(100)
        later=surface.grab().toImage()
        assert not later.isNull() and later!=first,theme+' did not animate'
        assert not errors and not exceptions
        assert user.GetForegroundWindow()==foreground,theme+' stole focus'
    print('PASS: native stream, rose_garden and lighthouse scenes animate with unchanged focus',flush=True)
    if synthetic:
        print('PASS: native synthetic parent/child embedding, frame rendering and unchanged focus; actual Explorer WorkerW unavailable',flush=True)
    else:
        print('PASS: native WorkerW child created, rendered, left focus unchanged and closed safely',flush=True)
finally:
    surface.shutdown();app.processEvents()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    if synthetic:user.DestroyWindow(synthetic)
