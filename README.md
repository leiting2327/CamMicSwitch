# CamMicSwitch - 一键替换摄像头与麦克风

Windows 软件：一键替换摄像头画面和麦克风声音，支持上传自定义图片/视频/音频，支持一键更改和一键修复功能。

## 功能
- 📷 摄像头画面替换：选择图片或视频，推流到 OBS Virtual Camera（无需打开 OBS）
- 🎤 麦克风声音替换：选择音频文件，循环播放到虚拟音频设备
- ⚙️ 开机自启、启动后最小化到托盘、自动开始推送
- 🔒 单实例运行（不能连续开窗口）

## 构建
```bash
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --windowed --name CamMicSwitch main.py
```
