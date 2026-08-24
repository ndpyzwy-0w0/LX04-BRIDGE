"""Push PCM into the LX04 virtual microphone driver (\\\\.\\LX04Mic)."""
from __future__ import annotations

from ctypes import WinDLL, byref, c_char
from ctypes.wintypes import DWORD, HANDLE, LPCWSTR, LPVOID

GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = HANDLE(-1).value
FILE_ATTRIBUTE_NORMAL = 0x80

# CTL_CODE(FILE_DEVICE_UNKNOWN, 0x900, METHOD_BUFFERED, FILE_WRITE_ACCESS)
IOCTL_LX04_PUSH_PCM = 0x0022A400

kernel32 = WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.argtypes = [LPCWSTR, DWORD, DWORD, LPVOID, DWORD, DWORD, HANDLE]
kernel32.CreateFileW.restype = HANDLE
kernel32.DeviceIoControl.argtypes = [HANDLE, DWORD, LPVOID, DWORD, LPVOID, DWORD, LPVOID, LPVOID]
kernel32.DeviceIoControl.restype = DWORD
kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = DWORD


class VirtualMic:
    def __init__(self) -> None:
        self._handle: int | None = None

    def available(self) -> bool:
        if self.opened():
            return True
        handle = kernel32.CreateFileW(
            "\\\\.\\LX04Mic",
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == INVALID_HANDLE_VALUE or handle is None:
            return False
        kernel32.CloseHandle(handle)
        return True

    def opened(self) -> bool:
        return self._handle is not None and self._handle != INVALID_HANDLE_VALUE

    def open(self) -> bool:
        self.close()
        handle = kernel32.CreateFileW(
            "\\\\.\\LX04Mic",
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == INVALID_HANDLE_VALUE or handle is None:
            self._handle = None
            return False
        self._handle = int(handle)
        return True

    def close(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is not None and handle != INVALID_HANDLE_VALUE:
            kernel32.CloseHandle(handle)

    def push(self, pcm: bytes) -> None:
        if not pcm or not self.opened():
            return
        blob = bytes(pcm)
        if len(blob) & 1:
            blob = blob[:-1]
        if not blob:
            return
        returned = DWORD(0)
        buf = (c_char * len(blob)).from_buffer_copy(blob)
        kernel32.DeviceIoControl(
            self._handle,
            IOCTL_LX04_PUSH_PCM,
            buf,
            len(blob),
            None,
            0,
            byref(returned),
            None,
        )
