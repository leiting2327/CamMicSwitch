"""
虚拟摄像头控制模块：将图片或视频循环推流到 OBS Virtual Camera。
不需要 OBS 软件运行，直接使用已注册的 DirectShow 驱动。
"""
import os
import threading
import time
from typing import Optional, Callable, Tuple

import numpy as np


class VirtualCamManager:
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"}

    def __init__(self):
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()
        self._current_file = None
        self._on_status_change = None
        self._cam = None

    def set_status_callback(self, callback):
        self._on_status_change = callback

    def _notify(self, msg):
        if self._on_status_change:
            try:
                self._on_status_change(msg)
            except Exception:
                pass

    @property
    def is_running(self):
        return self._running

    @property
    def current_file(self):
        return self._current_file

    @staticmethod
    def detect_file_type(filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext in VirtualCamManager.IMAGE_EXTS:
            return "image"
        if ext in VirtualCamManager.VIDEO_EXTS:
            return "video"
        return "unknown"

    def start(self, filepath):
        if self._running:
            self.stop()
        if not os.path.exists(filepath):
            return False, f"文件不存在: {filepath}"
        ftype = self.detect_file_type(filepath)
        if ftype == "unknown":
            return False, "不支持的文件格式（支持图片或视频）"

        self._stop_event.clear()
        self._current_file = filepath
        self._running = True
        self._thread = threading.Thread(target=self._push_loop, args=(filepath, ftype), daemon=True)
        self._thread.start()
        self._notify(f"正在推流: {os.path.basename(filepath)}")
        return True, "虚拟摄像头已启动"

    def stop(self):
        self._stop_event.set()
        self._running = False
        if self._cam is not None:
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._current_file = None
        self._notify("虚拟摄像头已停止")

    def _push_loop(self, filepath, ftype):
        import pyvirtualcam
        import cv2
        try:
            # 打开源媒体
            if ftype == "image":
                img = cv2.imread(filepath)
                if img is None:
                    raise RuntimeError("无法读取图片")
                frame_h, frame_w = img.shape[:2]
                cap = None
            else:
                cap = cv2.VideoCapture(filepath)
                if not cap.isOpened():
                    raise RuntimeError("无法打开视频")
                frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if frame_w <= 0 or frame_h <= 0:
                    frame_w, frame_h = 640, 480
                img = None

            self._notify(f"源分辨率: {frame_w}x{frame_h}")

            # 连接虚拟摄像头（自动探测 OBS Virtual Camera）
            cam = pyvirtualcam.Camera(width=frame_w, height=frame_h, fps=30, backend="obs")
            self._cam = cam
            self._notify(f"虚拟摄像头已连接: {cam.device}")

            while not self._stop_event.is_set():
                if ftype == "image":
                    frame = img
                else:
                    ret, frame = cap.read()
                    if not ret:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret:
                            continue

                # 确保帧尺寸匹配
                h, w = frame.shape[:2]
                if (w, h) != (frame_w, frame_h):
                    frame = cv2.resize(frame, (frame_w, frame_h))

                cam.send(frame)
                cam.sleep_until_next_frame()

        except Exception as e:
            self._running = False
            self._current_file = None
            self._notify(f"推流错误: {e}")
        finally:
            self._running = False
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            if self._cam is not None:
                try:
                    self._cam.close()
                except Exception:
                    pass
                self._cam = None
