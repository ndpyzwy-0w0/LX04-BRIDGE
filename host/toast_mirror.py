"""Read and operate Windows toast popups via UI Automation, not screenshots."""
from __future__ import annotations

import ctypes
import os
import queue
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field

import screen_mirror

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ole32 = ctypes.oledll.ole32
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:
    dwmapi = None

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(screen_mirror.RECT)]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.MonitorFromRect.argtypes = [ctypes.POINTER(screen_mirror.RECT), wintypes.DWORD]
user32.MonitorFromRect.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(screen_mirror.MONITORINFOEXW)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.PeekMessageW.argtypes = [
    ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.MsgWaitForMultipleObjects.argtypes = [
    wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD
]
user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype = wintypes.BOOL
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.SetEvent.restype = wintypes.BOOL
kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
kernel32.ResetEvent.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
if dwmapi is not None:
    dwmapi.DwmGetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    ]

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTONEAREST = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WM_CLOSE = 0x0010
COINIT_APARTMENTTHREADED = 0x2
POLL_IDLE_S = 0.04
POLL_LIVE_S = 0.05
POLL_FILL_S = 0.015
HOLD_OFF_S = 0.55
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
OBJID_WINDOW = 0
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
UIA_LEGACY = 10018

SKIP_CLASSES = {
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "Progman",
    "WorkerW",
    "ForegroundStaging",
    "IME",
    "MSCTFIME UI",
    "tooltips_class32",
    "#32768",
    "#32769",
    "DummyDWMListenerWindow",
    "TaskListOverlayWnd",
    "TaskListThumbnailWnd",
    "Windows.Internal.Shell.TabProxyWindow",
    "EdgeUiInputTopWndClass",
    "ApplicationManager_DesktopShellWindow",
    "Windows.UI.Input.InputSite.WindowClass",
}
TOAST_CLASSES = {
    "Windows.UI.Core.CoreWindow",
    "Windows.UI.Composition.DesktopWindowContentBridge",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
    "Microsoft.UI.Content.DesktopChildSiteBridge",
    "Xaml_WindowedPopupClass",
    "NativeHWNDHost",
    "ApplicationFrameWindow",
}
TOAST_TITLES = {
    "new notification",
    "new notifications",
    "notification",
    "notifications",
    "新通知",
    "通知",
}
TOAST_WINDOW_NAMES = (
    "新通知",
    "New notification",
    "New notifications",
    "Notifications",
    "Notification",
)
TOAST_PROCESSES = {
    "explorer.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "cursor.exe",
    "code.exe",
}
CHROME_BUTTONS = {
    "此通知的设置",
    "将此通知移动到通知中心",
    "settings for this notification",
    "move this notification to notification center",
    "close",
    "关闭",
    "dismiss",
    "dismiss notification",
    "notification settings",
    "see more",
    "更多",
    "打开通知中心",
}
UIA_WINDOW = 50032
UIA_BUTTON = 50000
UIA_HYPERLINK = 50005
UIA_SPLITBUTTON = 50031
UIA_MENUITEM = 50011
UIA_TEXT = 50020


@dataclass
class ToastButtonInfo:
    id: str
    label: str


@dataclass
class ToastContent:
    app: str = ""
    title: str = ""
    body: str = ""
    buttons: list[ToastButtonInfo] = field(default_factory=list)
    hwnd: int = 0
    partial: bool = False

    def fingerprint(self) -> tuple:
        return (
            self.hwnd,
            self.app,
            self.title,
            self.body,
            tuple((b.id, b.label) for b in self.buttons),
            self.partial,
        )

    def as_control(self) -> dict:
        return {
            "app": self.app,
            "title": self.title or "系统弹窗",
            "body": self.body,
            "buttons": [{"id": b.id, "label": b.label} for b in self.buttons],
        }

    def text_key(self) -> tuple[str, str, str]:
        return (self.app, self.title, self.body)


_UIA = None
_UIA_LOCK = threading.Lock()
_THREAD_UIA = threading.local()
HOST_APP_NAMES = {
    "windows powershell",
    "windows command processor",
    "powershell",
    "cmd",
    "命令提示符",
}


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD,
)
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HMODULE,
    WINEVENTPROC,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


def _pump() -> None:
    msg = MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def _pump_for(seconds: float) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        remain = int(max(1.0, (deadline - time.monotonic()) * 1000))
        user32.MsgWaitForMultipleObjects(0, None, False, min(remain, 30), QS_ALLINPUT)
        _pump()


def _uia_mod():
    global _UIA
    with _UIA_LOCK:
        if _UIA is not None:
            return _UIA
        import comtypes.client
        try:
            from comtypes.gen import UIAutomationClient as uia
        except (ImportError, OSError, AttributeError):
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
        _UIA = uia
        return uia


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    n = user32.GetClassNameW(hwnd, buf, 256)
    return buf.value if n else ""


def _title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    n = user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value if n else ""


def _cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    value = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value))
    return hr == 0 and value.value != 0


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def _work_area(rect: screen_mirror.RECT) -> screen_mirror.RECT | None:
    hmon = user32.MonitorFromRect(ctypes.byref(rect), MONITOR_DEFAULTTONEAREST)
    if not hmon:
        return None
    info = screen_mirror.MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(screen_mirror.MONITORINFOEXW)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    return info.rcWork


def _in_toast_dock(left: int, top: int, right: int, bottom: int, work: screen_mirror.RECT) -> bool:
    work_w = max(1, int(work.right - work.left))
    work_h = max(1, int(work.bottom - work.top))
    dock_left = int(work.right) - min(520, int(work_w * 0.46))
    dock_top = int(work.bottom) - min(640, int(work_h * 0.62))
    overlap_w = min(right, int(work.right)) - max(left, dock_left)
    overlap_h = min(bottom, int(work.bottom)) - max(top, dock_top)
    if overlap_w <= 8 or overlap_h <= 8:
        return False
    margin_r = int(work.right) - right
    margin_b = int(work.bottom) - bottom
    return margin_r <= 96 and margin_b <= 96


def _looks_like_toast(
    class_name: str,
    title: str,
    width: int,
    height: int,
    work: screen_mirror.RECT,
    ex_style: int,
    proc: str,
) -> bool:
    work_w = max(1, int(work.right - work.left))
    work_h = max(1, int(work.bottom - work.top))
    if width < 160 or height < 48:
        return False
    if width > min(720, int(work_w * 0.55)) or height > min(560, int(work_h * 0.58)):
        return False
    title_l = title.strip().lower()
    if title_l in TOAST_TITLES:
        return True
    if class_name in TOAST_CLASSES:
        return True
    if proc in TOAST_PROCESSES and (ex_style & WS_EX_TOPMOST or class_name.startswith("Chrome_WidgetWin_")):
        return True
    if class_name.startswith("Chrome_WidgetWin_") and (ex_style & (WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)):
        return True
    return bool(ex_style & WS_EX_TOPMOST) and proc in TOAST_PROCESSES


def _hwnd_is_toast(hwnd: int, our_pid: int = 0, require_visible: bool = True) -> bool:
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if require_visible:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or _cloaked(hwnd):
            return False
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if our_pid and int(pid.value) == our_pid:
        return False
    class_name = _class_name(hwnd)
    if class_name in SKIP_CLASSES:
        return False
    rect = screen_mirror.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    left, top, right, bottom = int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    width, height = right - left, bottom - top
    if width < 120 or height < 32:
        return False
    work = _work_area(rect)
    if work is None:
        return False
    if not _in_toast_dock(left, top, right, bottom, work):
        return False
    style = int(user32.GetWindowLongW(hwnd, GWL_STYLE) or 0)
    ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0)
    if ex_style & WS_EX_TRANSPARENT:
        return False
    if require_visible and not (style & WS_VISIBLE):
        return False
    proc = _process_name(int(pid.value))
    title = _title(hwnd)
    return _looks_like_toast(class_name, title, width, height, work, ex_style, proc)


def find_toast_hwnds() -> list[int]:
    screen_mirror._thread_dpi()
    found: list[int] = []
    our_pid = os.getpid()

    def _enum(hwnd, _lparam):
        if _hwnd_is_toast(int(hwnd), our_pid):
            found.append(int(hwnd))
        return 1

    cb = WNDENUMPROC(_enum)
    user32.EnumWindows(cb, 0)
    return found


def _create_uia():
    import comtypes.client
    uia = _uia_mod()
    return comtypes.client.CreateObject(uia.CUIAutomation), uia


def _auto():
    pair = getattr(_THREAD_UIA, "pair", None)
    if pair is None:
        pair = _create_uia()
        _THREAD_UIA.pair = pair
    return pair


def _hwnd_of(el) -> int:
    try:
        handle = el.CurrentNativeWindowHandle
    except Exception:
        return 0
    if handle is None:
        return 0
    try:
        return int(handle)
    except (TypeError, ValueError):
        return int(getattr(handle, "value", 0) or 0)


def _find_named_toast_windows(automation, uia) -> list:
    root = automation.GetRootElement()
    found = []
    seen: set[int] = set()
    for name in TOAST_WINDOW_NAMES:
        try:
            name_cond = automation.CreatePropertyCondition(uia.UIA_NamePropertyId, name)
            type_cond = automation.CreatePropertyCondition(uia.UIA_ControlTypePropertyId, UIA_WINDOW)
            cond = automation.CreateAndCondition(name_cond, type_cond)
            el = root.FindFirst(uia.TreeScope_Children, cond)
        except Exception:
            continue
        if el is None:
            continue
        hwnd = _hwnd_of(el)
        key = hwnd or id(el)
        if key in seen:
            continue
        if not _live_toast(el):
            continue
        seen.add(key)
        found.append(el)
    return found


def _element_from_hwnd(automation, hwnd: int):
    if not hwnd:
        return None
    try:
        return automation.ElementFromHandle(hwnd)
    except Exception:
        try:
            return automation.ElementFromHandle(ctypes.c_void_p(hwnd))
        except Exception:
            return None


def _has_invoke(el, uia) -> bool:
    try:
        return bool(el.GetCurrentPropertyValue(uia.UIA_IsInvokePatternAvailablePropertyId))
    except Exception:
        return False


def _live_toast(el) -> bool:
    try:
        if bool(el.CurrentIsOffscreen):
            return False
    except Exception:
        pass
    hwnd = _hwnd_of(el)
    if hwnd:
        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or _cloaked(hwnd):
            return False
        rect = screen_mirror.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            width = int(rect.right) - int(rect.left)
            height = int(rect.bottom) - int(rect.top)
            if width < 140 or height < 40:
                return False
        return True
    try:
        box = el.CurrentBoundingRectangle
        width = int(getattr(box, "right", 0) or 0)
        height = int(getattr(box, "bottom", 0) or 0)
        return width >= 140 and height >= 40
    except Exception:
        return False


def _click_point(x: int, y: int) -> None:
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    vs_l = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    vs_t = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    vs_w = max(1, int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)))
    vs_h = max(1, int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)))
    dx = int(round((x - vs_l) * 65535 / vs_w))
    dy = int(round((y - vs_t) * 65535 / vs_h))
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

    def _send(more: int, use_pos: bool = False) -> None:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        if use_pos:
            inp.mi.dx = dx
            inp.mi.dy = dy
            inp.mi.dwFlags = more | flags
        else:
            inp.mi.dwFlags = more
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    user32.SetCursorPos(int(x), int(y))
    _send(MOUSEEVENTF_MOVE, True)
    _pump()
    _send(MOUSEEVENTF_LEFTDOWN)
    _pump()
    _send(MOUSEEVENTF_LEFTUP)
    _pump()
    user32.SetCursorPos(int(old.x), int(old.y))


def _invoke(el, uia) -> bool:
    _pump()
    try:
        el.SetFocus()
    except Exception:
        pass
    _pump()
    try:
        pat = el.GetCurrentPattern(uia.UIA_InvokePatternId)
        if pat is not None:
            inv = pat.QueryInterface(uia.IUIAutomationInvokePattern)
            inv.Invoke()
            _pump_for(0.05)
            return True
    except Exception:
        pass
    try:
        pat = el.GetCurrentPattern(UIA_LEGACY)
        if pat is not None:
            acc = pat.QueryInterface(uia.IUIAutomationLegacyIAccessiblePattern)
            acc.DoDefaultAction()
            _pump_for(0.05)
            return True
    except Exception:
        pass
    try:
        point, ok = el.GetClickablePoint()
        if ok:
            _click_point(int(point.x), int(point.y))
            return True
    except Exception:
        pass
    try:
        box = el.CurrentBoundingRectangle
        left = int(getattr(box, "left", 0) or 0)
        top = int(getattr(box, "top", 0) or 0)
        width = int(getattr(box, "right", 0) or 0)
        height = int(getattr(box, "bottom", 0) or 0)
        if width >= 8 and height >= 8:
            _click_point(left + width // 2, top + height // 2)
            return True
    except Exception:
        pass
    return False


def _is_chrome_label(name: str) -> bool:
    low = name.strip().lower()
    if not low:
        return True
    if low in CHROME_BUTTONS:
        return True
    if "的新通知" in name or "new notification from" in low:
        return True
    if low.startswith("来自 ") and "的新通知" in name:
        return True
    return False


def _walk(el, uia):
    automation, _ = _auto()
    return el.FindAll(uia.TreeScope_Descendants, automation.CreateTrueCondition())


def read_toast(el, uia) -> ToastContent | None:
    if el is None:
        return None
    try:
        kids = _walk(el, uia)
        count = int(kids.Length)
    except Exception:
        return None
    texts: list[str] = []
    buttons: list[str] = []
    seen_btn: set[str] = set()
    for i in range(count):
        try:
            node = kids.GetElement(i)
            name = (node.CurrentName or "").strip()
            ct = int(node.CurrentControlType)
        except Exception:
            continue
        if not name or _is_chrome_label(name):
            continue
        is_btn = ct in (UIA_BUTTON, UIA_HYPERLINK, UIA_SPLITBUTTON, UIA_MENUITEM)
        if is_btn or (ct != UIA_TEXT and _has_invoke(node, uia) and ct != UIA_WINDOW):
            if name not in seen_btn:
                seen_btn.add(name)
                buttons.append(name)
            continue
        if name not in seen_btn and name not in texts:
            texts.append(name)
    leftover = [item for item in texts if item.strip().lower() not in TOAST_TITLES]
    app = title = body = ""
    if len(leftover) == 1:
        title = leftover[0]
    elif len(leftover) == 2:
        title, body = leftover[0], leftover[1]
    elif leftover:
        app, title, body = leftover[0], leftover[1], leftover[2]
        extra = leftover[3:]
        if extra and len(extra[-1]) <= 24:
            attr = extra[-1]
            extra = extra[:-1]
            if app.strip().lower() in HOST_APP_NAMES or not app:
                app = attr
        if extra:
            body = body + "\n" + "\n".join(extra)
    if app.strip().lower() in HOST_APP_NAMES:
        app = ""
    if not title:
        try:
            title = (el.CurrentName or "").strip()
        except Exception:
            title = ""
        if title.strip().lower() in TOAST_TITLES:
            title = "系统弹窗"
    return ToastContent(
        app=app,
        title=title,
        body=body,
        buttons=[ToastButtonInfo(str(i), label) for i, label in enumerate(buttons)],
        hwnd=_hwnd_of(el),
    )


def _toast_elements(automation, uia, hwnd_hint: int = 0, enum_windows: bool = False) -> list:
    found = []
    if hwnd_hint:
        el = _element_from_hwnd(automation, hwnd_hint)
        if el is not None and _live_toast(el):
            found.append(el)
            return found
    found = [el for el in _find_named_toast_windows(automation, uia) if _live_toast(el)]
    if found or not enum_windows:
        return found
    seen = {_hwnd_of(el) for el in found}
    for hwnd in find_toast_hwnds():
        if hwnd in seen:
            continue
        el = _element_from_hwnd(automation, hwnd)
        if el is not None and _live_toast(el):
            found.append(el)
            seen.add(hwnd)
    return found


def stale_toast(content: ToastContent | None, ignore_hwnd: int, ignore_key: tuple | None) -> bool:
    """True if this is the notification the speaker already dismissed."""
    if content is None:
        return False
    key = content.text_key()
    if ignore_hwnd and content.hwnd == ignore_hwnd:
        return ignore_key is None or key == ignore_key
    return ignore_key is not None and key == ignore_key


def read_current_toast(hwnd_hint: int = 0, enum_windows: bool = False) -> ToastContent | None:
    screen_mirror._thread_dpi()
    automation, uia = _auto()
    for el in _toast_elements(automation, uia, hwnd_hint, enum_windows):
        content = read_toast(el, uia)
        if content is not None and (content.title or content.body or content.buttons):
            return content
    return None


def _find_button(el, uia, label: str, chrome: bool = False):
    try:
        kids = _walk(el, uia)
        count = int(kids.Length)
    except Exception:
        return None
    want = label.strip()
    for i in range(count):
        try:
            node = kids.GetElement(i)
            name = (node.CurrentName or "").strip()
            ct = int(node.CurrentControlType)
        except Exception:
            continue
        if name.replace(" ", "") != want.replace(" ", ""):
            continue
        if not chrome and _is_chrome_label(name):
            continue
        if ct == UIA_BUTTON:
            return node
        if ct in (UIA_HYPERLINK, UIA_SPLITBUTTON, UIA_MENUITEM) or _has_invoke(node, uia):
            return node
    return None


def invoke_toast_button(label: str, hwnd_hint: int = 0) -> bool:
    automation, uia = _auto()
    for el in _toast_elements(automation, uia, hwnd_hint, enum_windows=True):
        btn = _find_button(el, uia, label)
        if btn is not None and _invoke(btn, uia):
            return True
    return False


def dismiss_toasts() -> None:
    try:
        automation, uia = _auto()
        for el in _toast_elements(automation, uia, enum_windows=True):
            for chrome in (
                "将此通知移动到通知中心",
                "Move this notification to Notification Center",
                "关闭",
                "Close",
            ):
                btn = _find_button(el, uia, chrome, chrome=True)
                if btn is not None and _invoke(btn, uia):
                    return
            hwnd = _hwnd_of(el)
            if hwnd:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                return
    except Exception:
        pass
    for hwnd in find_toast_hwnds():
        if hwnd and user32.IsWindow(hwnd):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


class ToastSender:
    def __init__(self, on_change=None, on_log=None) -> None:
        self.on_change = on_change
        self.on_log = on_log
        self._alive = False
        self._showing = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._life = threading.Lock()
        self._wake_lock = threading.Lock()
        self._jobs: queue.Queue[tuple[str, str]] = queue.Queue()
        self._content: ToastContent | None = None
        self._last_buttons: list[ToastButtonInfo] = []
        self._fingerprint: tuple | None = None
        self._holdoff = 0.0
        self._ignore_hwnd = 0
        self._ignore_key: tuple | None = None
        self._wake = None
        self._hint_hwnd = 0
        self._pending_hwnd = 0
        self._idle_n = 0
        self._hooks: list = []
        self._winevent_proc = None
        self.title = ""
        self.error = ""

    def running(self) -> bool:
        return self._alive

    def showing(self) -> bool:
        return self._alive and self._showing

    def content(self) -> ToastContent | None:
        with self._lock:
            return self._content

    def start(self) -> None:
        with self._life:
            thread = self._thread
            if self._alive and thread is not None and thread.is_alive():
                return
            if thread is not None and thread.is_alive():
                self._alive = False
                self._signal()
                thread.join(timeout=5.0)
                if thread.is_alive():
                    self.error = "系统弹窗线程未能结束，请再试一次"
                    return
            self.error = ""
            self._showing = False
            self._fingerprint = None
            self._holdoff = 0.0
            self._ignore_hwnd = 0
            self._ignore_key = None
            self._hint_hwnd = 0
            self._pending_hwnd = 0
            self._last_buttons = []
            self._idle_n = 0
            self._hooks = []
            self._jobs = queue.Queue()
            self._alive = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="lx04-toast")
            self._thread.start()

    def stop(self) -> None:
        with self._life:
            was_showing = self._showing
            self._alive = False
            self._showing = False
            self._signal()
            thread = self._thread
            if thread is not None and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=5.0)
            if thread is not None and not thread.is_alive():
                self._thread = None
            with self._lock:
                self._content = None
                self._fingerprint = None
                self._last_buttons = []
                self._ignore_hwnd = 0
                self._ignore_key = None
                self._pending_hwnd = 0
            if was_showing:
                self._emit(False, None)

    def handle_event(self, data: dict) -> None:
        cmd = str(data.get("cmd") or "")
        if cmd == "toast_action":
            label = str(data.get("label") or data.get("id") or "")
            resolved = self._label_for(label)
            self._note("音箱点了按钮「" + (resolved or label or "?") + "」")
            if resolved:
                self._jobs.put(("invoke", resolved))
                self._signal()
            else:
                self._note("没有对应的系统通知按钮，无法点按")
            self._hide()
        elif cmd == "toast_dismiss":
            self._note("音箱关闭了弹窗页")
            self.dismiss()

    def invoke(self, button_id: str) -> None:
        if button_id:
            self._jobs.put(("invoke", button_id))
            self._signal()

    def dismiss(self) -> None:
        self._hide()
        self._jobs.put(("dismiss", ""))
        self._signal()

    def _label_for(self, token: str) -> str:
        token = (token or "").strip()
        with self._lock:
            buttons = list(self._content.buttons if self._content is not None else self._last_buttons)
        for btn in buttons:
            if btn.id == token or btn.label == token:
                return btn.label
        return token

    def _hide(self) -> None:
        self._holdoff = time.monotonic() + HOLD_OFF_S
        with self._lock:
            was = self._showing
            self._showing = False
            if self._content is not None:
                self._ignore_hwnd = self._content.hwnd
                self._ignore_key = self._content.text_key()
                self._last_buttons = list(self._content.buttons)
                self._content = None
                self._fingerprint = None
            self._pending_hwnd = 0
        if was:
            self._emit(False, None)

    def _show_skeleton(self, hwnd: int) -> None:
        if not self._alive or self._showing or not hwnd:
            return
        if hwnd == self._ignore_hwnd or time.monotonic() < self._holdoff:
            return
        content = ToastContent(title="系统弹窗", hwnd=hwnd, partial=True)
        with self._lock:
            if not self._alive or self._showing:
                return
            self._content = content
            self._fingerprint = content.fingerprint()
            self._showing = True
            self._pending_hwnd = hwnd
        self._emit(True, content)

    def _blocked(self, content: ToastContent | None) -> bool:
        if content is None:
            return True
        return time.monotonic() < self._holdoff or stale_toast(content, self._ignore_hwnd, self._ignore_key)

    def _forget_dead_ignore(self) -> None:
        hwnd = self._ignore_hwnd
        if hwnd:
            if user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd) and not _cloaked(hwnd):
                return
            self._ignore_hwnd = 0
            self._ignore_key = None
            return
        if self._ignore_key is not None and time.monotonic() >= self._holdoff:
            self._ignore_key = None

    def _note(self, line: str) -> None:
        cb = self.on_log
        if cb is None:
            self.error = line
            return
        try:
            cb(line)
        except Exception:
            self.error = line

    def _signal(self) -> None:
        with self._wake_lock:
            handle = self._wake
            if handle:
                kernel32.SetEvent(handle)

    def _close_wake(self) -> None:
        with self._wake_lock:
            handle = self._wake
            self._wake = None
        if handle:
            kernel32.CloseHandle(handle)

    def _unhook(self) -> None:
        hooks = list(self._hooks)
        self._hooks = []
        for hook in hooks:
            try:
                user32.UnhookWinEvent(hook)
            except Exception:
                pass
        _pump()

    def _on_win_event(self, _hook, _event, hwnd, id_object, id_child, _thread, _time) -> None:
        try:
            if not self._alive or not hwnd or int(id_object) != OBJID_WINDOW or int(id_child) != 0:
                return
            handle = int(hwnd)
            if handle == self._ignore_hwnd:
                return
            class_name = _class_name(handle)
            if not class_name or class_name in SKIP_CLASSES:
                return
            title = _title(handle).strip().lower()
            if (
                class_name in TOAST_CLASSES
                or class_name.startswith("Chrome_WidgetWin_")
                or title in TOAST_TITLES
            ):
                self._hint_hwnd = handle
                if _hwnd_is_toast(handle, os.getpid(), require_visible=False):
                    self._show_skeleton(handle)
                self._signal()
        except Exception:
            pass

    def _hook_windows(self) -> None:
        proc = WINEVENTPROC(self._on_win_event)
        self._winevent_proc = proc
        flags = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
        hook = user32.SetWinEventHook(
            EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, None, proc, 0, 0, flags
        )
        if hook:
            self._hooks.append(hook)

    def _wait(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        handle = self._wake
        while self._alive and time.monotonic() < deadline:
            if not self._jobs.empty():
                return
            remain = int((deadline - time.monotonic()) * 1000)
            if remain <= 0:
                return
            wait_ms = min(remain, 25)
            try:
                if handle:
                    slot = wintypes.HANDLE(int(handle))
                    user32.MsgWaitForMultipleObjects(1, ctypes.byref(slot), False, wait_ms, QS_ALLINPUT)
                    kernel32.ResetEvent(handle)
                else:
                    user32.MsgWaitForMultipleObjects(0, None, False, wait_ms, QS_ALLINPUT)
            except Exception:
                return
            _pump()
            if self._hint_hwnd and self._hint_hwnd != self._ignore_hwnd:
                return

    def _emit(self, showing: bool, content: ToastContent | None) -> None:
        cb = self.on_change
        if cb is None:
            return
        try:
            cb(showing, content)
        except Exception:
            pass

    def _loop(self) -> None:
        try:
            ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        except Exception:
            try:
                ole32.CoInitialize(None)
            except Exception:
                pass
        screen_mirror._thread_dpi()
        self._wake = kernel32.CreateEventW(None, True, False, None)
        try:
            _auto()
            self._hook_windows()
        except Exception as exc:
            self.error = "无法初始化系统通知接口: " + str(exc)
            self._note(self.error)
        try:
            while self._alive:
                started = time.monotonic()
                invoked = False
                while True:
                    try:
                        kind, payload = self._jobs.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        if kind == "invoke":
                            label = payload
                            hint = self._hint_hwnd
                            self._note("正在点按电脑通知「" + label + "」")
                            ok = bool(label) and invoke_toast_button(label, hint)
                            if ok:
                                invoked = True
                                self._note("已点按电脑通知「" + label + "」")
                            else:
                                self._note("未能点按电脑通知「" + label + "」")
                        elif kind == "dismiss":
                            dismiss_toasts()
                            self._note("已关闭电脑通知")
                    except Exception as exc:
                        self._note("点按电脑通知出错: " + str(exc))
                if invoked:
                    self._hide()
                    self._hint_hwnd = 0
                    _pump_for(0.03)
                hint = self._hint_hwnd
                self._hint_hwnd = 0
                if hint and hint == self._ignore_hwnd:
                    hint = 0
                if not hint and self._pending_hwnd and self._pending_hwnd != self._ignore_hwnd:
                    hint = self._pending_hwnd
                if not hint and not self._showing:
                    hwnds = find_toast_hwnds()
                    if hwnds and hwnds[0] != self._ignore_hwnd:
                        hint = hwnds[0]
                if hint:
                    self._show_skeleton(hint)
                self._idle_n += 1
                enum_windows = bool(hint) or (self._idle_n % 10 == 0)
                try:
                    content = read_current_toast(hint, enum_windows)
                except Exception as exc:
                    self._note("读取系统通知失败: " + str(exc))
                    content = None
                if content is not None and self._blocked(content):
                    content = None
                if content is None:
                    keep_hwnd = hint or self._pending_hwnd
                    if self._showing and keep_hwnd and keep_hwnd != self._ignore_hwnd and _hwnd_is_toast(
                        keep_hwnd, os.getpid()
                    ):
                        remain = POLL_FILL_S - (time.monotonic() - started)
                        if remain > 0 and self._alive:
                            self._wait(remain)
                        continue
                    if self._showing:
                        self._hide()
                    self._forget_dead_ignore()
                    remain = POLL_IDLE_S - (time.monotonic() - started)
                    if remain > 0 and self._alive:
                        self._wait(remain)
                    continue
                fp = content.fingerprint()
                self.title = content.title
                with self._lock:
                    if self._blocked(content):
                        blocked = True
                        start_show = False
                        changed = False
                    else:
                        blocked = False
                        self._ignore_hwnd = 0
                        self._ignore_key = None
                        self._content = content
                        self._last_buttons = list(content.buttons)
                        self._pending_hwnd = content.hwnd or hint
                        changed = fp != self._fingerprint
                        self._fingerprint = fp
                        start_show = not self._showing
                        if start_show:
                            self._showing = True
                if blocked:
                    self._forget_dead_ignore()
                    remain = POLL_IDLE_S - (time.monotonic() - started)
                    if remain > 0 and self._alive:
                        self._wait(remain)
                    continue
                if start_show:
                    if self._showing:
                        self._emit(True, content)
                elif changed and self._showing:
                    self._emit(True, content)
                remain = POLL_LIVE_S - (time.monotonic() - started)
                if remain > 0 and self._alive:
                    self._wait(remain)
        finally:
            self._unhook()
            self._close_wake()
            self._winevent_proc = None
            try:
                ole32.CoUninitialize()
            except Exception:
                pass
