"""Native Windows WorkerW child, drawing quiet frame blends behind desktop icons."""
import ctypes
from ctypes import wintypes
import os
import time
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget
from .ubuntu_pack import draw_motion


class DesktopSurfaceUnavailable(RuntimeError):
    """Explorer is present but does not expose a usable wallpaper surface."""


def user32():
    if os.name!='nt':raise RuntimeError('Windowsin live-työpöytä tarvitsee Windowsin.')
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];api.FindWindowW.restype=wintypes.HWND
    api.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR];api.FindWindowExW.restype=wintypes.HWND
    api.SendMessageTimeoutW.argtypes=[wintypes.HWND,wintypes.UINT,ctypes.c_size_t,ctypes.c_ssize_t,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    api.SendMessageTimeoutW.restype=ctypes.c_ssize_t
    api.SetParent.argtypes=[wintypes.HWND,wintypes.HWND];api.SetParent.restype=wintypes.HWND
    api.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];api.GetClientRect.restype=wintypes.BOOL
    api.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    api.SetWindowPos.restype=wintypes.BOOL
    api.IsWindow.argtypes=[wintypes.HWND];api.IsWindow.restype=wintypes.BOOL
    api.GetWindowLongPtrW.argtypes=[wintypes.HWND,ctypes.c_int];api.GetWindowLongPtrW.restype=ctypes.c_ssize_t
    api.SetWindowLongPtrW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t];api.SetWindowLongPtrW.restype=ctypes.c_ssize_t
    return api


def desktop_parent(api):
    progman=api.FindWindowW('Progman',None)
    if not progman:raise DesktopSurfaceUnavailable('Windowsin Explorer-työpöytää ei löydy.')
    result=ctypes.c_size_t()
    for argument,parameter in ((0,0),(0xD,0),(0xD,1)):
        api.SendMessageTimeoutW(progman,0x052C,argument,parameter,0x0002,1000,ctypes.byref(result))
    found=[]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,ctypes.c_ssize_t)
    def visit(window,_):
        if api.FindWindowExW(window,None,'SHELLDLL_DefView',None):
            sibling=api.FindWindowExW(None,window,'WorkerW',None)
            if sibling and not api.FindWindowExW(sibling,None,'SHELLDLL_DefView',None):found.append(sibling)
        return True
    callback=callback_type(visit)
    api.EnumWindows.argtypes=[callback_type,ctypes.c_ssize_t];api.EnumWindows.restype=wintypes.BOOL
    api.EnumWindows(callback,0)
    if not found:
        # Recent Explorer layouts can host the wallpaper WorkerW under Progman.
        child=api.FindWindowExW(progman,None,'WorkerW',None)
        if child and not api.FindWindowExW(child,None,'SHELLDLL_DefView',None):found.append(child)
    if not found:raise DesktopSurfaceUnavailable('Windows ei tarjoa live-taustalle WorkerW-pintaa. Tavallinen pysäytyskuva on silti käytettävissä.')
    return found[0]


class MotionDesktop(QWidget):
    def __init__(self,entry,on_error):
        super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.Tool|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.entry=entry;self.on_error=on_error;self.api=user32();self.parent_handle=None;self.registered=False
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setWindowTitle('Veriyö Live · taustapinta')
        self.timer=QTimer(self);self.timer.setInterval(100)  # 10 fps is ample for a few pixels over 48 seconds.
        self.timer.timeout.connect(self.tick)
        self.last_check=0
        self.setWindowOpacity(0)
        self.show()
        try:self.attach()
        except Exception:
            self.hide();self.close();self.deleteLater();raise
        self.setWindowOpacity(1)
        self.timer.start()
        try:
            self.wts=ctypes.WinDLL('wtsapi32',use_last_error=True)
            self.wts.WTSRegisterSessionNotification.argtypes=[wintypes.HWND,wintypes.DWORD]
            self.wts.WTSRegisterSessionNotification.restype=wintypes.BOOL
            self.registered=bool(self.wts.WTSRegisterSessionNotification(int(self.winId()),0))
        except OSError:pass

    def attach(self):
        parent=desktop_parent(self.api)
        handle=int(self.winId())
        # Qt owns this child only. We never destroy or re-style Explorer's windows.
        style=self.api.GetWindowLongPtrW(handle,-16)
        self.api.SetWindowLongPtrW(handle,-16,(style & ~0x80000000)|0x40000000)
        extended=self.api.GetWindowLongPtrW(handle,-20)
        self.api.SetWindowLongPtrW(handle,-20,extended|0x08000000|0x00000020|0x00000080)
        ctypes.set_last_error(0)
        previous=self.api.SetParent(handle,parent)
        error=ctypes.get_last_error()
        if not previous and error:raise ctypes.WinError(error)
        rect=wintypes.RECT()
        if not self.api.GetClientRect(parent,ctypes.byref(rect)):raise ctypes.WinError(ctypes.get_last_error())
        width,height=rect.right-rect.left,rect.bottom-rect.top
        if width<=0 or height<=0:raise RuntimeError('Windowsin työpöydän koko on virheellinen.')
        ratio=max(1,self.devicePixelRatioF())
        self.resize(round(width/ratio),round(height/ratio))
        if not self.api.SetWindowPos(handle,None,0,0,width,height,0x0010|0x0004|0x0040):
            raise ctypes.WinError(ctypes.get_last_error())
        self.parent_handle=parent

    def tick(self):
        try:
            if time.monotonic()-self.last_check>5:
                self.last_check=time.monotonic()
                if not self.api.IsWindow(self.parent_handle):self.attach()
            self.update()
        except Exception as error:
            self.timer.stop();self.hide();self.on_error(str(error))

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        try:draw_motion(painter,self.entry,time.time(),QRectF(self.rect()))
        except Exception as error:
            self.timer.stop();self.hide()
            QTimer.singleShot(0,lambda message=str(error):self.on_error(message))
        finally:painter.end()

    def nativeEvent(self,event_type,message):
        if os.name=='nt':
            event=wintypes.MSG.from_address(int(message))
            if event.message==0x02B1:  # WM_WTSSESSION_CHANGE
                if event.wParam==7:self.timer.stop()  # Locked: don't spend CPU animating an invisible desktop.
                elif event.wParam==8:self.timer.start()
        # Let Qt's Windows dispatcher handle all unconsumed messages. QWidget's
        # nativeEvent has no default result value; passing through its protected
        # Python wrapper can leave an undefined LRESULT during window creation.
        return False,0

    def shutdown(self):
        self.timer.stop()
        if self.registered:
            self.wts.WTSUnRegisterSessionNotification.argtypes=[wintypes.HWND]
            self.wts.WTSUnRegisterSessionNotification(int(self.winId()))
            self.registered=False
        self.hide();self.close();self.deleteLater()
