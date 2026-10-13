"""CamMicSwitch 主程序入口"""
import sys
import os
import ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_MUTEX = "Global\\CamMicSwitch_SingleInstance_Mutex"
_global_mutex = None


def already_running():
    """检测是否已有实例在运行。"""
    global _global_mutex
    _global_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX)
    ERROR_ALREADY_EXISTS = 183
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        user32 = ctypes.windll.user32
        hwnd_found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        def enum_cb(hwnd, lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if "CamMicSwitch" in buf.value:
                    hwnd_found.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        if hwnd_found:
            hwnd = hwnd_found[0]
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
        return True
    return False


if __name__ == "__main__":
    if already_running():
        sys.exit(0)
    from gui.main_window import MainWindow
    app = MainWindow()
    app.start_hidden()
    app.mainloop()
