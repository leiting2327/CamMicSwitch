"""
虚拟麦克风控制模块：将音频文件循环播放到虚拟音频设备。
"""
import os
import threading
from typing import Optional, Callable, Tuple

import numpy as np
import soundfile as sf
import sounddevice as sd


class VirtualMicManager:
    AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}

    def __init__(self):
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()
        self._current_file = None
        self._device_id = None
        self._on_status_change = None
        self._stream = None

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
    def is_supported_audio(filepath):
        return os.path.splitext(filepath)[1].lower() in VirtualMicManager.AUDIO_EXTS

    @staticmethod
    def get_audio_info(filepath):
        try:
            info = sf.info(filepath)
            channels = "立体声" if info.channels >= 2 else "单声道"
            return info.duration, info.samplerate, channels
        except Exception:
            return None, None, "未知"

    def start(self, filepath, device_id):
        if self._running:
            self.stop()
        if not os.path.exists(filepath):
            return False, f"文件不存在: {filepath}"
        if not self.is_supported_audio(filepath):
            return False, f"不支持的音频格式"

        self._stop_event.clear()
        self._current_file = filepath
        self._device_id = device_id
        self._running = True
        self._thread = threading.Thread(target=self._play_loop, args=(filepath, device_id), daemon=True)
        self._thread.start()
        self._notify(f"正在播放: {os.path.basename(filepath)}")
        return True, "虚拟麦克风已启动"

    def stop(self):
        self._stop_event.set()
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._current_file = None
        self._notify("虚拟麦克风已停止")

    def _play_loop(self, filepath, device_id):
        try:
            data, samplerate = sf.read(filepath, dtype="float32", always_2d=True)
            channels = data.shape[1]
            self._notify(f"虚拟麦克风已启动 ({samplerate}Hz, {channels}声道)")
            self._stream = sd.OutputStream(
                samplerate=samplerate, channels=channels,
                device=device_id, dtype="float32", blocksize=1024,
            )
            self._stream.start()
            pos = 0
            chunk_size = 1024
            while not self._stop_event.is_set():
                end = min(pos + chunk_size, len(data))
                chunk = data[pos:end]
                if len(chunk) < chunk_size:
                    pad = np.zeros((chunk_size - len(chunk), channels), dtype=np.float32)
                    chunk = np.vstack([chunk, pad])
                self._stream.write(chunk)
                pos += chunk_size
                if pos >= len(data):
                    pos = 0  # 循环播放
        except Exception as e:
            self._running = False
            self._current_file = None
            self._notify(f"播放错误: {e}")
        finally:
            self._running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
