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
POLL_IDLE_S = 0.07
POLL_LIVE_S = 0.10
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
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

    def fingerprint(self) -> tuple:
        return (self.hwnd, self.app, self.title, self.body, tuple((b.id, b.label) for b in self.buttons))

    def as_control(self) -> dict:
        return {
            "app": self.app,
            "title": self.title or "系统弹窗",
            "body": self.body,
            "buttons": [{"id": b.id, "label": b.label} for b in self.buttons],
        }


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


def find_toast_hwnds() -> list[int]:
    screen_mirror._thread_dpi()
    found: list[int] = []
    our_pid = os.getpid()

    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or _cloaked(hwnd):
            return 1
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) == our_pid:
            return 1
        class_name = _class_name(hwnd)
        if class_name in SKIP_CLASSES:
            return 1
        rect = screen_mirror.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return 1
        left, top, right, bottom = int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
        width, height = right - left, bottom - top
        work = _work_area(rect)
        if work is None:
            return 1
        if not _in_toast_dock(left, top, right, bottom, work):
            return 1
        style = int(user32.GetWindowLongW(hwnd, GWL_STYLE) or 0)
        ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0)
        if ex_style & WS_EX_TRANSPARENT:
            return 1
        if not (style & WS_VISIBLE):
            return 1
        proc = _process_name(int(pid.value))
        title = _title(hwnd)
        if not _looks_like_toast(class_name, title, width, height, work, ex_style, proc):
            return 1
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


def _toast_elements(automation, uia) -> list:
    found = [el for el in _find_named_toast_windows(automation, uia) if _live_toast(el)]
    if found:
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


def read_current_toast() -> ToastContent | None:
    screen_mirror._thread_dpi()
    automation, uia = _auto()
    for el in _toast_elements(automation, uia):
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


def invoke_toast_button(label: str) -> bool:
    automation, uia = _auto()
    for el in _toast_elements(automation, uia):
        btn = _find_button(el, uia, label)
        if btn is not None and _invoke(btn, uia):
            return True
    return False


def dismiss_toasts() -> None:
    try:
        automation, uia = _auto()
        for el in _toast_elements(automation, uia):
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
    def __init__(self, on_change=None) -> None:
        self.on_change = on_change
        self._alive = False
        self._showing = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._jobs: queue.Queue[tuple[str, str]] = queue.Queue()
        self._content: ToastContent | None = None
        self._fingerprint: tuple | None = None
        self._holdoff = 0.0
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
        if self._alive:
            return
        self.error = ""
        self._showing = False
        self._fingerprint = None
        self._holdoff = 0.0
        self._jobs = queue.Queue()
        self._alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="lx04-toast")
        self._thread.start()

    def stop(self) -> None:
        was_showing = self._showing
        self._alive = False
        self._showing = False
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=1.0)
        with self._lock:
            self._content = None
            self._fingerprint = None
        if was_showing:
            self._emit(False, None)

    def handle_event(self, data: dict) -> None:
        cmd = str(data.get("cmd") or "")
        if cmd == "toast_action":
            if self._showing:
                self.invoke(str(data.get("id") or data.get("label") or ""))
        elif cmd == "toast_dismiss":
            self.dismiss()

    def invoke(self, button_id: str) -> None:
        if button_id:
            self._jobs.put(("invoke", button_id))

    def dismiss(self) -> None:
        self._hide()
        self._jobs.put(("dismiss", ""))

    def _hide(self) -> None:
        self._holdoff = time.monotonic() + 0.7
        if not self._showing:
            return
        self._showing = False
        with self._lock:
            self._content = None
            self._fingerprint = None
        self._emit(False, None)

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
        try:
            _auto()
        except Exception as exc:
            self.error = "无法初始化系统通知接口: " + str(exc)
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
                            with self._lock:
                                content = self._content
                            if content is not None:
                                for btn in content.buttons:
                                    if btn.id == payload or btn.label == payload:
                                        label = btn.label
                                        break
                            if label and invoke_toast_button(label):
                                invoked = True
                                self.error = ""
                            elif label:
                                self.error = "未能点按系统通知按钮「" + label + "」"
                        elif kind == "dismiss":
                            dismiss_toasts()
                    except Exception as exc:
                        self.error = str(exc)
                if invoked:
                    self._hide()
                    _pump_for(0.05)
                try:
                    content = read_current_toast()
                except Exception as exc:
                    self.error = str(exc)
                    content = None
                if content is not None and time.monotonic() < self._holdoff:
                    content = None
                if content is None:
                    if self._showing:
                        self._hide()
                    remain = POLL_IDLE_S - (time.monotonic() - started)
                    if remain > 0 and self._alive:
                        _pump_for(remain)
                    continue
                fp = content.fingerprint()
                self.title = content.title
                with self._lock:
                    self._content = content
                    changed = fp != self._fingerprint
                    self._fingerprint = fp
                if not self._showing:
                    self._showing = True
                    self._emit(True, content)
                elif changed:
                    self._emit(True, content)
                remain = POLL_LIVE_S - (time.monotonic() - started)
                if remain > 0 and self._alive:
                    _pump_for(remain)
        finally:
            try:
                ole32.CoUninitialize()
            except Exception:
                pass
