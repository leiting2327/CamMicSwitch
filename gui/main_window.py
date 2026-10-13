"""
主界面 GUI - 支持系统托盘、开机自启、静默启动、单实例
"""
import os
import sys
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw

from core.virtual_cam import VirtualCamManager
from core.virtual_mic import VirtualMicManager
from core.device_detector import (
    get_virtual_cam_status, find_virtual_mic_device, get_install_guide_html,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "CamMicSwitch"
AUTOSTART_REG = r"Software\Microsoft\Windows\CurrentVersion\Run"


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - 一键替换摄像头与麦克风")
        self.geometry("520x780")
        self.resizable(False, False)

        self.cam_mgr = VirtualCamManager()
        self.mic_mgr = VirtualMicManager()
        self.cam_mgr.set_status_callback(self._on_cam_status)
        self.mic_mgr.set_status_callback(self._on_mic_status)

        self.selected_cam_file = None
        self.selected_mic_file = None
        self._preview_image = None
        self._mic_dev_id = None
        self._tray_icon = None

        self._build_ui()
        self._load_settings()
        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        # 如果设置了启动后最小化，立即隐藏窗口，不闪现
        if self.minimize_val:
            self._create_tray_icon()
            self.withdraw()
        self.after(500, self._detect_devices)

    # ---------------- UI ----------------

    def _build_ui(self):
        ctk.CTkLabel(self, text="🎥 CamMicSwitch", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(15, 2))
        ctk.CTkLabel(self, text="一键替换摄像头画面 & 麦克风声音（无需OBS）", font=ctk.CTkFont(size=12), text_color="#888").pack(pady=(0, 8))

        # 摄像头
        cf = ctk.CTkFrame(self, corner_radius=10)
        cf.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(cf, text="📷 摄像头画面替换", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        self.cam_preview = ctk.CTkLabel(cf, text="（选择图片或视频后显示预览）", width=440, height=130,
                                        corner_radius=6, fg_color="#1a1a1a", text_color="#555", font=ctk.CTkFont(size=12))
        self.cam_preview.pack(padx=14, pady=4)
        self.cam_file_label = ctk.CTkLabel(cf, text="未选择文件", font=ctk.CTkFont(size=12), text_color="#888", anchor="w")
        self.cam_file_label.pack(fill="x", padx=14, pady=(2, 4))
        r = ctk.CTkFrame(cf, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=(4, 10))
        ctk.CTkButton(r, text="选择图片/视频", command=self._select_cam_file, width=120, fg_color="#2b5797").pack(side="left", padx=(0, 6))
        self.btn_cam_start = ctk.CTkButton(r, text="✅ 一键更改画面", command=self._start_cam, width=135, fg_color="#2d8a4e", state="disabled")
        self.btn_cam_start.pack(side="left", padx=6)
        self.btn_cam_stop = ctk.CTkButton(r, text="🔧 修复", command=self._stop_cam, width=80, fg_color="#8a2d2d", state="disabled")
        self.btn_cam_stop.pack(side="left", padx=6)

        # 麦克风
        mf = ctk.CTkFrame(self, corner_radius=10)
        mf.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(mf, text="🎤 麦克风声音替换", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        self.mic_file_label = ctk.CTkLabel(mf, text="未选择音频文件", font=ctk.CTkFont(size=12), text_color="#888", anchor="w")
        self.mic_file_label.pack(fill="x", padx=14, pady=(4, 2))
        self.mic_info_label = ctk.CTkLabel(mf, text="时长: --    采样率: --", font=ctk.CTkFont(size=11), text_color="#666", anchor="w")
        self.mic_info_label.pack(fill="x", padx=14, pady=(0, 4))
        r2 = ctk.CTkFrame(mf, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(4, 10))
        ctk.CTkButton(r2, text="选择音频文件", command=self._select_mic_file, width=120, fg_color="#2b5797").pack(side="left", padx=(0, 6))
        self.btn_mic_start = ctk.CTkButton(r2, text="✅ 一键更改声音", command=self._start_mic, width=135, fg_color="#2d8a4e", state="disabled")
        self.btn_mic_start.pack(side="left", padx=6)
        self.btn_mic_stop = ctk.CTkButton(r2, text="🔧 修复", command=self._stop_mic, width=80, fg_color="#8a2d2d", state="disabled")
        self.btn_mic_stop.pack(side="left", padx=6)

        # 选项
        of = ctk.CTkFrame(self, corner_radius=10)
        of.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(of, text="⚙️ 开机自启设置", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(8, 2))
        self.chk_autostart = ctk.CTkSwitch(of, text="开机自动启动（无需打开OBS）", command=self._toggle_autostart)
        self.chk_autostart.pack(anchor="w", padx=14, pady=2)
        self.chk_minimize = ctk.CTkSwitch(of, text="启动后最小化到系统托盘", command=self._save_settings)
        self.chk_minimize.pack(anchor="w", padx=14, pady=2)
        self.chk_auto_start = ctk.CTkSwitch(of, text="启动后自动开始推送上次的文件", command=self._save_settings)
        self.chk_auto_start.pack(anchor="w", padx=14, pady=(2, 10))

        # 状态
        df = ctk.CTkFrame(self, corner_radius=10)
        df.pack(fill="x", padx=16, pady=6)
        self.cam_dev_label = ctk.CTkLabel(df, text="虚拟摄像头: 检测中...", font=ctk.CTkFont(size=11), anchor="w")
        self.cam_dev_label.pack(fill="x", padx=14, pady=(8, 2))
        self.mic_dev_label = ctk.CTkLabel(df, text="虚拟麦克风: 检测中...", font=ctk.CTkFont(size=11), anchor="w")
        self.mic_dev_label.pack(fill="x", padx=14, pady=(2, 6))
        ctk.CTkButton(df, text="📖 驱动安装指引", command=self._show_guide, width=150, fg_color="#444").pack(pady=(0, 8))

        # 日志
        self.log_box = ctk.CTkTextbox(self, height=60, font=ctk.CTkFont(size=10), fg_color="#111", text_color="#aaa")
        self.log_box.pack(fill="x", padx=16, pady=(4, 10))
        self.log_box.insert("end", "就绪。\n")
        self.log_box.configure(state="disabled")

    # ---------------- 设置持久化 ----------------

    def _settings_file(self):
        return os.path.join(os.path.expanduser("~"), ".cammicswitch_settings.txt")

    def _load_settings(self):
        path = self._settings_file()
        self.autostart_val = self.minimize_val = self.auto_start_val = False
        self.last_cam = self.last_mic = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k == "autostart": self.autostart_val = v == "1"
                        elif k == "minimize": self.minimize_val = v == "1"
                        elif k == "auto_start": self.auto_start_val = v == "1"
                        elif k == "last_cam": self.last_cam = v
                        elif k == "last_mic": self.last_mic = v
        except Exception:
            pass
        if self.autostart_val: self.chk_autostart.select()
        if self.minimize_val: self.chk_minimize.select()
        if self.auto_start_val: self.chk_auto_start.select()
        if self.last_cam and os.path.exists(self.last_cam):
            self.selected_cam_file = self.last_cam
            self.cam_file_label.configure(text=f"📄 {os.path.basename(self.last_cam)}", text_color="#ccc")
            self._show_cam_preview(self.last_cam)
            self.btn_cam_start.configure(state="normal")
        if self.last_mic and os.path.exists(self.last_mic):
            self.selected_mic_file = self.last_mic
            self.mic_file_label.configure(text=f"🎵 {os.path.basename(self.last_mic)}", text_color="#ccc")
            self.btn_mic_start.configure(state="normal")

    def _save_settings(self):
        try:
            with open(self._settings_file(), "w", encoding="utf-8") as f:
                f.write(f"autostart={1 if self.chk_autostart.get() else 0}\n")
                f.write(f"minimize={1 if self.chk_minimize.get() else 0}\n")
                f.write(f"auto_start={1 if self.chk_auto_start.get() else 0}\n")
                f.write(f"last_cam={self.selected_cam_file or ''}\n")
                f.write(f"last_mic={self.selected_mic_file or ''}\n")
        except Exception:
            pass

    # ---------------- 开机自启 ----------------

    def _toggle_autostart(self):
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG, 0, winreg.KEY_SET_VALUE)
        try:
            if self.chk_autostart.get():
                exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
                self._log("✅ 已设置开机自启动")
            else:
                try: winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError: pass
                self._log("已取消开机自启动")
        finally:
            winreg.CloseKey(key)
        self._save_settings()

    # ---------------- 日志 ----------------

    def _log(self, msg):
        self.log_box.configure(state="normal")
        import datetime
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{t}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------------- 设备检测 ----------------

    def _detect_devices(self):
        self._log("正在检测虚拟设备...")
        def work():
            cam_ok, cam_msg = get_virtual_cam_status()
            mic_dev_id, mic_msg = find_virtual_mic_device()
            self.after(0, lambda: self._update_dev_status(cam_ok, cam_msg, mic_dev_id, mic_msg))
        threading.Thread(target=work, daemon=True).start()

    def _update_dev_status(self, cam_ok, cam_msg, mic_dev_id, mic_msg):
        c1 = "#2d8a4e" if cam_ok else "#cc4444"
        c2 = "#2d8a4e" if mic_dev_id is not None else "#cc4444"
        self.cam_dev_label.configure(text=f"虚拟摄像头: {'✅' if cam_ok else '❌'} {cam_msg}", text_color=c1)
        self.mic_dev_label.configure(text=f"虚拟麦克风: {'✅' if mic_dev_id is not None else '❌'} {mic_msg}", text_color=c2)
        self._mic_dev_id = mic_dev_id
        self._log(f"摄像头: {cam_msg}")
        self._log(f"麦克风: {mic_msg}")
        if self.auto_start_val and self.selected_cam_file:
            self.after(1000, self._start_cam)
        if self.auto_start_val and self.selected_mic_file and mic_dev_id is not None:
            self.after(1500, self._start_mic)

    # ---------------- 文件选择 ----------------

    def _select_cam_file(self):
        path = filedialog.askopenfilename(title="选择图片或视频", filetypes=[
            ("媒体文件", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.avi *.mkv *.mov *.flv *.wmv"),
            ("图片", "*.jpg *.jpeg *.png *.bmp *.webp"),
            ("视频", "*.mp4 *.avi *.mkv *.mov *.flv *.wmv"),
        ])
        if not path: return
        self.selected_cam_file = path
        self.cam_file_label.configure(text=f"📄 {os.path.basename(path)}", text_color="#ccc")
        self._show_cam_preview(path)
        self.btn_cam_start.configure(state="normal")
        self._log(f"已选择画面: {path}")
        self._save_settings()

    def _show_cam_preview(self, path):
        ft = VirtualCamManager.detect_file_type(path)
        try:
            if ft == "image":
                img = Image.open(path)
            else:
                import cv2
                cap = cv2.VideoCapture(path)
                ret, frame = cap.read()
                cap.release()
                if not ret: return
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            img.thumbnail((440, 130), Image.LANCZOS)
            self._preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self.cam_preview.configure(image=self._preview_image, text="")
        except Exception as e:
            self.cam_preview.configure(text=f"预览失败: {e}", image=None)

    def _select_mic_file(self):
        path = filedialog.askopenfilename(title="选择音频文件", filetypes=[
            ("音频文件", "*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.wma"),
        ])
        if not path: return
        self.selected_mic_file = path
        self.mic_file_label.configure(text=f"🎵 {os.path.basename(path)}", text_color="#ccc")
        dur, sr, ch = VirtualMicManager.get_audio_info(path)
        if dur is not None:
            m, s = divmod(int(dur), 60)
            self.mic_info_label.configure(text=f"时长: {m:02d}:{s:02d}    采样率: {sr}Hz    声道: {ch}")
        self.btn_mic_start.configure(state="normal")
        self._log(f"已选择音频: {path}")
        self._save_settings()

    # ---------------- 启动/停止 ----------------

    def _start_cam(self):
        if not self.selected_cam_file:
            messagebox.showwarning("提示", "请先选择图片或视频文件"); return
        ok, msg = self.cam_mgr.start(self.selected_cam_file)
        if ok:
            self.btn_cam_start.configure(state="disabled")
            self.btn_cam_stop.configure(state="normal")
            self._log(f"✅ {msg}")
        else:
            messagebox.showerror("启动失败", msg)

    def _stop_cam(self):
        self.cam_mgr.stop()
        self.btn_cam_start.configure(state="normal" if self.selected_cam_file else "disabled")
        self.btn_cam_stop.configure(state="disabled")
        self._log("🔧 画面已修复")

    def _start_mic(self):
        if not self.selected_mic_file:
            messagebox.showwarning("提示", "请先选择音频文件"); return
        if self._mic_dev_id is None:
            messagebox.showerror("未检测到虚拟麦克风", "请先安装虚拟音频设备"); return
        ok, msg = self.mic_mgr.start(self.selected_mic_file, self._mic_dev_id)
        if ok:
            self.btn_mic_start.configure(state="disabled")
            self.btn_mic_stop.configure(state="normal")
            self._log(f"✅ {msg}")
        else:
            messagebox.showerror("启动失败", msg)

    def _stop_mic(self):
        self.mic_mgr.stop()
        self.btn_mic_start.configure(state="normal" if self.selected_mic_file else "disabled")
        self.btn_mic_stop.configure(state="disabled")
        self._log("🔧 声音已修复")

    def _on_cam_status(self, msg):
        self.after(0, lambda: self._log(f"[摄像头] {msg}"))

    def _on_mic_status(self, msg):
        self.after(0, lambda: self._log(f"[麦克风] {msg}"))

    def _show_guide(self):
        win = ctk.CTkToplevel(self)
        win.title("虚拟驱动安装指引")
        win.geometry("560x400")
        win.transient(self)
        tb = ctk.CTkTextbox(win, font=ctk.CTkFont(size=13))
        tb.pack(fill="both", expand=True, padx=16, pady=16)
        tb.insert("end", get_install_guide_html())
        tb.configure(state="disabled")
        ctk.CTkButton(win, text="关闭", command=win.destroy).pack(pady=(0, 12))

    # ---------------- 系统托盘 ----------------

    def _create_tray_icon(self):
        import pystray
        img = Image.new("RGB", (64, 64), color=(45, 138, 78))
        d = ImageDraw.Draw(img)
        d.text((18, 18), "C", fill="white")
        def on_show(icon, item): self.after(0, self._show_window)
        def on_quit(icon, item):
            icon.stop()
            self.after(0, self._real_quit)
        self._tray_icon = pystray.Icon("CamMicSwitch", img, "CamMicSwitch",
            pystray.Menu(pystray.MenuItem("显示主窗口", on_show), pystray.MenuItem("退出", on_quit)))

    def _minimize_to_tray(self):
        if self._tray_icon is None:
            self._create_tray_icon()
        self.withdraw()
        if not self._tray_icon.visible:
            threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _show_window(self):
        self.deiconify()
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None

    def _real_quit(self):
        self.cam_mgr.stop()
        self.mic_mgr.stop()
        self._save_settings()
        self.destroy()

    def start_hidden(self):
        """已在__init__中处理，无需延迟"""
        pass
