"""
Antigravity × Gemini Catgirl Animated Startup Launcher (Windows)
----------------------------------------------------------------
Non-invasive (zero-hook) startup animation launcher for Google Antigravity.
Plays a hardware-accelerated 60fps Gemini Catgirl zero-gravity intro while
launching Antigravity in the background, locks onto the real Antigravity
window bounds, and smoothly dissolves via Win32 layered alpha directly into
the live Antigravity workspace.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode

import webview

# ---------------------------------------------------------------------------
# Paths & Logging
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"
SPLASH_HTML = ROOT_DIR / "ui" / "splash.html"
ICON_PATH = ROOT_DIR / "assets" / "gemini_catgirl.ico"
LOG_PATH = ROOT_DIR / "launcher.log"

SPLASH_TITLE = "Antigravity Gemini Neko Boot"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("ag_gemini_boot")

# ---------------------------------------------------------------------------
# Win32 API Bindings (64-bit safe argtypes / restype)
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
LWA_ALPHA = 0x00000002

HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

SW_RESTORE = 9
SW_SHOWNOACTIVATE = 4

DWMWA_EXTENDED_FRAME_BOUNDS = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
user32.SetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def enable_dpi_awareness() -> None:
    """Enable per-monitor DPI awareness so window rectangles align pixel-perfectly."""
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def get_primary_screen_size() -> tuple[int, int]:
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def get_window_dpi_scale(hwnd: int) -> float:
    try:
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        dpi = user32.GetDpiForWindow(wintypes.HWND(hwnd))
        if dpi > 0:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


def get_process_exe(pid: int) -> str:
    hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hproc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(hproc)
    return ""


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if hr != 0:
        user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def find_antigravity_windows(exclude_pid: int) -> list[dict]:
    """Return all candidate Antigravity main windows currently present on the desktop."""
    results: list[dict] = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == exclude_pid:
            return True

        title_buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title_buf, 256)
        title = title_buf.value
        if title == SPLASH_TITLE:
            return True

        exe = get_process_exe(pid.value)
        exe_name = os.path.basename(exe).lower()
        # Match ONLY real Antigravity.exe windows (never File Explorer or browser tabs)
        if exe_name != "antigravity.exe":
            return True

        cls_buf = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls_buf, 128)
        cls_name = cls_buf.value

        left, top, right, bottom = get_window_rect(hwnd)
        w, h = right - left, bottom - top
        iconic = bool(user32.IsIconic(hwnd))

        # Accept real Chromium/Electron main windows (visible >= 480x320 or minimized main window with title)
        is_main_cls = cls_name.startswith("Chrome_WidgetWin")
        if (w >= 480 and h >= 320) or (iconic and is_main_cls and bool(title.strip())):
            results.append(
                {
                    "hwnd": int(hwnd),
                    "pid": int(pid.value),
                    "title": title,
                    "cls": cls_name,
                    "exe": exe,
                    "left": left,
                    "top": top,
                    "width": w,
                    "height": h,
                    "iconic": iconic,
                    "is_main_cls": is_main_cls,
                    "area": max(0, w * h),
                }
            )
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    # Prefer main Chromium window class, non-iconic, largest area first
    results.sort(key=lambda item: (item["is_main_cls"], not item["iconic"], item["area"]), reverse=True)
    return results


def find_splash_hwnd(my_pid: int) -> int | None:
    """Locate our own pywebview splash window HWND."""
    found: list[int] = []

    def _cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != my_pid:
            return True
        title_buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title_buf, 256)
        if title_buf.value == SPLASH_TITLE:
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(_cb), 0)
    if found:
        return found[0]
    h = user32.FindWindowW(None, SPLASH_TITLE)
    return int(h) if h else None


def enable_layered_window(hwnd: int, initial_alpha: int = 255) -> None:
    ex_style = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    new_style = ex_style | WS_EX_LAYERED | WS_EX_TOOLWINDOW
    user32.SetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE, new_style)
    user32.SetLayeredWindowAttributes(wintypes.HWND(hwnd), 0, initial_alpha, LWA_ALPHA)


def set_window_alpha(hwnd: int, alpha: int) -> None:
    a = max(0, min(255, int(alpha)))
    user32.SetLayeredWindowAttributes(wintypes.HWND(hwnd), 0, a, LWA_ALPHA)


def animate_alpha(hwnd: int, start_a: int, end_a: int, duration_ms: int) -> None:
    if not hwnd or not user32.IsWindow(wintypes.HWND(hwnd)):
        return
    duration_s = max(0.05, duration_ms / 1000.0)
    t0 = time.perf_counter()
    while True:
        elapsed = time.perf_counter() - t0
        p = min(1.0, elapsed / duration_s)
        # Smooth cubic ease-out
        eased = 1.0 - (1.0 - p) ** 3
        val = int(round(start_a + (end_a - start_a) * eased))
        set_window_alpha(hwnd, val)
        if p >= 1.0:
            break
        time.sleep(1.0 / 75.0)


def bring_to_foreground(target_hwnd: int) -> None:
    """Reliably activate and focus the real Antigravity window after dissolve."""
    if not target_hwnd or not user32.IsWindow(wintypes.HWND(target_hwnd)):
        return
    h = wintypes.HWND(target_hwnd)
    if user32.IsIconic(h):
        user32.ShowWindow(h, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tgt_tid = user32.GetWindowThreadProcessId(h, None)

    attached_fg = False
    attached_tgt = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        if tgt_tid and tgt_tid != cur_tid:
            attached_tgt = bool(user32.AttachThreadInput(cur_tid, tgt_tid, True))
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
    finally:
        if attached_tgt:
            user32.AttachThreadInput(cur_tid, tgt_tid, False)
        if attached_fg:
            user32.AttachThreadInput(cur_tid, fg_tid, False)


# ---------------------------------------------------------------------------
# Config & Executable Discovery
# ---------------------------------------------------------------------------
def load_config() -> dict:
    defaults = {
        "antigravity_exe": "",
        "fullscreen": True,
        "windowed_width": 1280,
        "windowed_height": 720,
        "sound_enabled": True,
        "sound_volume": 0.28,
        "min_duration_ms": 3400,
        "max_wait_ms": 14000,
        "paint_settle_ms": 650,
        "fade_in_ms": 200,
        "fade_out_ms": 460,
        "subtitle": "GEMINI NEKO PROTOCOL · ZERO-G WORKSPACE",
        "greeting": "星轨已就绪，准备进入反重力空间",
    }
    if CONFIG_PATH.exists():
        try:
            user_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            defaults.update(user_cfg)
        except Exception as exc:
            log.warning("Failed reading config.json: %s", exc)
    return defaults


def resolve_antigravity_exe(cfg: dict) -> Path | None:
    candidates = []
    if cfg.get("antigravity_exe"):
        candidates.append(Path(cfg["antigravity_exe"]))
    local_app = os.environ.get("LOCALAPPDATA", "")
    prog_files = os.environ.get("ProgramFiles", "")
    if local_app:
        candidates.append(Path(local_app) / "Programs" / "Antigravity" / "Antigravity.exe")
        candidates.append(Path(local_app) / "Antigravity" / "Antigravity.exe")
    if prog_files:
        candidates.append(Path(prog_files) / "Antigravity" / "Antigravity.exe")
    which = shutil.which("Antigravity.exe") or shutil.which("antigravity")
    if which:
        candidates.append(Path(which))

    for p in candidates:
        if p and p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Launcher Orchestrator
# ---------------------------------------------------------------------------
class BootBridge:
    def __init__(self, skip_event: threading.Event):
        self._skip_event = skip_event

    def request_skip(self) -> bool:
        self._skip_event.set()
        return True


def safe_eval_js(win: webview.Window, code: str) -> None:
    try:
        win.evaluate_js(code)
    except Exception:
        pass


def orchestrate_boot(
    win: webview.Window,
    cfg: dict,
    preview: bool,
    extra_args: list[str],
    skip_event: threading.Event,
) -> None:
    my_pid = os.getpid()
    t_start = time.perf_counter()

    # 1. Locate our own splash HWND & apply smooth layered alpha fade-in
    splash_hwnd = None
    for _ in range(40):
        try:
            native = getattr(win, "native", None)
            if native is not None and getattr(native, "Handle", None) is not None:
                splash_hwnd = int(native.Handle.ToInt64())
                if splash_hwnd:
                    break
        except Exception:
            pass
        splash_hwnd = find_splash_hwnd(my_pid)
        if splash_hwnd:
            break
        time.sleep(0.025)

    if splash_hwnd:
        try:
            enable_layered_window(splash_hwnd, initial_alpha=0)
            # Keep topmost explicitly
            user32.SetWindowPos(
                wintypes.HWND(splash_hwnd),
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            animate_alpha(splash_hwnd, 0, 255, int(cfg["fade_in_ms"]))
        except Exception as exc:
            log.warning("Layered fade-in skipped: %s", exc)

    # 2. Snapshot existing Antigravity windows & launch Antigravity ONLY if not already running (or extra args given)
    pre_existing = find_antigravity_windows(exclude_pid=my_pid)
    pre_hwnds = {w["hwnd"] for w in pre_existing}
    already_running = bool(pre_existing) and not extra_args

    if not preview:
        if already_running:
            log.info("Antigravity is already open (hwnd=%s); skipping redundant launch to prevent focus hijack.", pre_existing[0]["hwnd"])
            safe_eval_js(win, "window.onBootProgress(42, '02 // 检测到 Antigravity 已在运行 · 准备无缝接管...', 'WARM HANDOFF')")
        else:
            exe_path = resolve_antigravity_exe(cfg)
            if exe_path:
                log.info("Launching Antigravity: %s args=%s", exe_path, extra_args)
                safe_eval_js(win, "window.onBootProgress(42, '02 // 正在后台拉起 Antigravity 主进程...', 'SPAWNING ENGINE')")
                try:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = SW_SHOWNOACTIVATE
                    subprocess.Popen(
                        [str(exe_path), *extra_args],
                        close_fds=True,
                        startupinfo=si,
                        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    )
                except Exception as exc:
                    log.error("Failed to launch Antigravity: %s", exc)
                    safe_eval_js(win, "window.onBootProgress(60, '未能自动启动主程序，请检查 config.json 路径', 'LAUNCH ERROR')")
            else:
                log.error("Antigravity.exe not found.")
                safe_eval_js(win, "window.onBootProgress(60, '未找到 Antigravity.exe，请检查 config.json', 'EXE NOT FOUND')")
    else:
        safe_eval_js(win, "window.onBootProgress(52, '02 // 预览模式 · 正在探测当前工作区窗口...', 'PREVIEW MODE')")

    # 3. Poll for target Antigravity window ready while guarding splash TOPMOST Z-order
    min_dur_s = float(cfg["min_duration_ms"]) / 1000.0
    max_wait_s = float(cfg["max_wait_ms"]) / 1000.0
    settle_s = float(cfg["paint_settle_ms"]) / 1000.0

    target_win: dict | None = pre_existing[0] if already_running else None
    first_detected_ts: float | None = time.perf_counter() if target_win else None
    reported_detected = False

    while True:
        elapsed = time.perf_counter() - t_start

        # Continuously keep splash above everything so Electron cold-start/focus can NEVER cover the animation
        if splash_hwnd:
            user32.SetWindowPos(
                wintypes.HWND(splash_hwnd),
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

        candidates = find_antigravity_windows(exclude_pid=my_pid)

        if target_win is None and candidates:
            # Cold start: prefer a newly spawned window; fallback to existing main window
            new_wins = [c for c in candidates if c["hwnd"] not in pre_hwnds]
            if new_wins:
                target_win = new_wins[0]
                first_detected_ts = time.perf_counter()
                log.info("Detected new Antigravity window: %s", target_win)
            elif (preview or elapsed >= 1.35) and candidates:
                target_win = candidates[0]
                first_detected_ts = time.perf_counter()
                log.info("Adopted existing Antigravity window: %s", target_win)

        # Keep target Antigravity window tucked cleanly underneath our topmost splash during playback
        if target_win and splash_hwnd and not target_win.get("iconic"):
            th = wintypes.HWND(target_win["hwnd"])
            if user32.IsWindow(th):
                user32.SetWindowPos(
                    th,
                    wintypes.HWND(splash_hwnd),
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )

        # Report detected window status smoothly once the left HUD is visible (~7.4s+)
        if target_win and not reported_detected and elapsed >= 7.4:
            reported_detected = True
            tw_w, tw_h = target_win["width"], target_win["height"]
            dim_label = f"HWND {tw_w}×{tw_h}" if tw_w >= 400 else "WORKSPACE READY"
            safe_eval_js(
                win,
                f"window.onBootProgress(88, '03 // 已捕捉 Antigravity 窗口 · 准备无缝衔接...', '{dim_label}')",
            )

        if skip_event.is_set():
            log.info("User requested immediate skip at %.2fs", elapsed)
            break

        if elapsed >= max_wait_s:
            log.info("Max wait timeout reached (%.2fs), proceeding to handoff", elapsed)
            break

        if target_win is not None and first_detected_ts is not None:
            settled = (time.perf_counter() - first_detected_ts) >= settle_s
            if settled and elapsed >= min_dur_s:
                break
        elif preview and elapsed >= min_dur_s:
            # Preview mode with no Antigravity window open: cleanly finish animation
            break

        time.sleep(0.05)

    # 4. Lock-On Frame Alignment + Seamless Layered-Alpha Dissolve Handoff!
    target_hwnd = target_win["hwnd"] if target_win else None
    if target_hwnd and user32.IsWindow(wintypes.HWND(target_hwnd)):
        # If minimized, restore silently RIGHT BEFORE dissolve while keeping splash TOPMOST!
        if user32.IsIconic(wintypes.HWND(target_hwnd)):
            user32.ShowWindow(wintypes.HWND(target_hwnd), SW_SHOWNOACTIVATE)
            if splash_hwnd:
                user32.SetWindowPos(
                    wintypes.HWND(splash_hwnd),
                    HWND_TOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
            time.sleep(0.14)

        tl, tt, tr, tb = get_window_rect(target_hwnd)
        tw, th = max(0, tr - tl), max(0, tb - tt)

        if splash_hwnd:
            sl, st, _sr, _sb = get_window_rect(splash_hwnd)
            scale = get_window_dpi_scale(splash_hwnd)
            rel_rect = {
                "x": int(round((tl - sl) / scale)),
                "y": int(round((tt - st) / scale)),
                "w": int(round(tw / scale)),
                "h": int(round(th / scale)),
            }
            safe_eval_js(win, f"window.onWindowLocked({json.dumps(rel_rect)})")
            # Place Antigravity directly beneath our topmost splash so alpha fade reveals it seamlessly!
            user32.SetWindowPos(
                wintypes.HWND(target_hwnd),
                wintypes.HWND(splash_hwnd),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            user32.SetWindowPos(
                wintypes.HWND(splash_hwnd),
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        else:
            safe_eval_js(win, "window.onWindowLocked(null)")

        if not skip_event.is_set():
            time.sleep(0.32)
    else:
        safe_eval_js(win, "window.onWindowLocked(null)")

    # Trigger starlight portal expansion in JS + silky 60fps Win32 alpha fade-out
    safe_eval_js(win, "window.beginHandoff()")
    time.sleep(0.08)

    fade_ms = 220 if skip_event.is_set() else int(cfg["fade_out_ms"])
    if splash_hwnd:
        animate_alpha(splash_hwnd, 255, 0, fade_ms)

    # Hand keyboard & mouse focus cleanly to Antigravity
    if target_hwnd and user32.IsWindow(wintypes.HWND(target_hwnd)):
        bring_to_foreground(target_hwnd)

    log.info("Handoff complete; closing splash window.")
    try:
        win.destroy()
    except Exception:
        pass

    # Hard watchdog: guarantee zero zombie pythonw process if WebView2/WinForms lags on teardown
    def _force_exit():
        time.sleep(1.2)
        logging.shutdown()
        os._exit(0)

    threading.Thread(target=_force_exit, daemon=True).start()


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


def start_local_asset_server(root_dir: Path) -> tuple[ThreadingHTTPServer, int]:
    """Serve ROOT_DIR on an ephemeral localhost port so WebView2 loads query params & assets cleanly."""
    handler = functools.partial(_QuietStaticHandler, directory=str(root_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


def main() -> int:
    enable_dpi_awareness()

    parser = argparse.ArgumentParser(description="Antigravity Gemini Catgirl Startup Launcher")
    parser.add_argument("--preview", action="store_true", help="Preview animation without launching a new Antigravity process")
    parser.add_argument("--windowed", action="store_true", help="Run in centered frameless 1280x720 window instead of fullscreen")
    parser.add_argument("--mute", action="store_true", help="Mute startup starlight chime")
    args, extra_args = parser.parse_known_args()

    # Single-instance guard (skip guard in preview mode so repeated previews never block)
    mutex = None
    if not args.preview:
        mutex = kernel32.CreateMutexW(None, False, "Local\\AntigravityGeminiNekoBootMutex")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return 0

    cfg = load_config()
    fullscreen = bool(cfg.get("fullscreen", True)) and not args.windowed
    sound_on = bool(cfg.get("sound_enabled", True)) and not args.mute

    # Use pywebview logical screen dimensions so 100%/125%/150%/200% DPI scaling matches pixel-perfectly
    screens = webview.screens
    if screens:
        primary = screens[0]
        sw, sh = int(primary.width), int(primary.height)
        sx, sy = int(getattr(primary, "x", 0)), int(getattr(primary, "y", 0))
    else:
        sw, sh = get_primary_screen_size()
        sx, sy = 0, 0

    if fullscreen:
        win_w, win_h = sw, sh
        win_x, win_y = sx, sy
    else:
        win_w = min(int(cfg.get("windowed_width", 1280)), max(640, sw - 40))
        win_h = min(int(cfg.get("windowed_height", 720)), max(360, sh - 40))
        win_x = sx + (sw - win_w) // 2
        win_y = sy + (sh - win_h) // 2

    server, port = start_local_asset_server(ROOT_DIR)
    query = urlencode(
        {
            "mute": "0" if sound_on else "1",
            "vol": str(cfg.get("sound_volume", 0.28)),
            "subtitle": str(cfg.get("subtitle", "")),
            "greeting": str(cfg.get("greeting", "")),
        }
    )
    splash_url = f"http://127.0.0.1:{port}/ui/splash.html?{query}"

    skip_event = threading.Event()
    bridge = BootBridge(skip_event)

    window = webview.create_window(
        title=SPLASH_TITLE,
        url=splash_url,
        js_api=bridge,
        width=win_w,
        height=win_h,
        x=win_x,
        y=win_y,
        resizable=False,
        fullscreen=False,  # Use borderless exact-screen frameless window so Win32 layered alpha works 100%
        frameless=True,
        easy_drag=False,
        shadow=False,
        on_top=True,
        background_color="#070913",
        text_select=False,
        zoomable=False,
    )

    icon_arg = str(ICON_PATH) if ICON_PATH.exists() else None
    cache_dir = ROOT_DIR / ".webview_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info("Starting splash window (preview=%s, fullscreen=%s, port=%d)", args.preview, fullscreen, port)
    try:
        webview.start(
            func=orchestrate_boot,
            args=(window, cfg, args.preview, extra_args, skip_event),
            gui="edgechromium",
            http_server=False,
            private_mode=False,
            storage_path=str(cache_dir),
            icon=icon_arg,
        )
    except Exception:
        log.exception("Unhandled error in webview.start")
    finally:
        # Daemon HTTP server & WebView2 teardown: release mutex and exit immediately without hanging
        if mutex:
            try:
                kernel32.CloseHandle(mutex)
            except Exception:
                pass
        logging.shutdown()
        os._exit(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
