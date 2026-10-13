"""
设备检测模块：检测 OBS Virtual Camera 和虚拟音频设备是否可用。
"""
import subprocess
import sys
from typing import Optional, Tuple


def get_virtual_cam_status() -> Tuple[bool, str]:
    """检测 OBS Virtual Camera 是否注册可用。"""
    # 检查注册表中的 OBS Virtual Camera CLSID
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Classes\CLSID\{A3FCE0F5-3493-419F-958A-ABA1250EC20B}\InprocServer32",
                             0, winreg.KEY_READ)
        try:
            dll_path, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
        except Exception:
            winreg.CloseKey(key)
            dll_path = None

        if dll_path and __import__("os").path.exists(dll_path):
            return True, f"OBS Virtual Camera 可用"
        return False, "未检测到 OBS Virtual Camera（请先安装 OBS Studio）"
    except Exception:
        return False, "未检测到 OBS Virtual Camera"


def find_virtual_mic_device() -> Tuple[Optional[int], str]:
    """查找虚拟音频设备（播放端）。"""
    import sounddevice as sd
    try:
        devices = sd.query_devices()
        # 优先匹配已知虚拟设备名
        keywords = ["cable", "virtual", "vb-audio", "netease", "wangyi", "网易",
                    "voice changer", "voicemeeter", "screaming"]
        matches = []
        for i, d in enumerate(devices):
            name = str(d.get("name", "")).lower()
            if d.get("max_output_channels", 0) > 0:
                for kw in keywords:
                    if kw in name:
                        matches.append((i, d.get("name", "")))
                        break
        if matches:
            dev_id, name = matches[0]
            return dev_id, f"虚拟音频设备: {name}"
        # 回退：返回第一个输出设备
        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0:
                return i, f"使用默认输出设备: {d.get('name', '')}"
        return None, "未找到音频输出设备"
    except Exception as e:
        return None, f"音频设备检测失败: {e}"


def get_install_guide_html() -> str:
    """返回驱动安装指引文本。"""
    return """【OBS Virtual Camera 安装指引】

1. 下载并安装 OBS Studio：https://obsproject.com/
2. 安装完成后，OBS Virtual Camera 驱动会自动注册到系统
3. 本软件会直接向该驱动推流，无需打开 OBS 软件

【虚拟音频设备（可选）】
如需替换麦克风声音，请安装任一虚拟音频设备：
- VB-CABLE：https://vb-audio.com/Cable/
- Voicemeeter：https://vb-audio.com/Voicemeeter/
安装后重启软件即可自动识别。

【使用说明】
1. 选择图片/视频 → 点击「一键更改画面」→ 推流到 OBS Virtual Camera
2. 选择音频文件 → 点击「一键更改声音」→ 循环播放到虚拟麦克风
3. 其他应用（如掌上看家、微信、Zoom）在设置中选择对应虚拟设备即可
"""
