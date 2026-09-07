**中文** | [English](README.en.md)
# APEX 组合包保底计数器

一个面向 Windows 的 Apex Legends 组合包保底计数器(手动)桌面应用。它可以记录当前开启的组合包数量，在获得传家宝后记录次数并重置计数。

## 功能

- 组合包数量增减和手动输入
- 传家宝获得次数记录
- 距离 500 包保底的进度显示
- 更换背景主题及按钮主题
- 本地保存计数

## 运行环境

- Windows 10 或更高版本
- Python 3.10+

程序使用 Tkinter 创建界面。如果运行时报缺少 `tkinter`，请重新安装 Python 并启用 Tcl/Tk 组件。

## 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

运行后，程序会在应用目录生成 `pack_counter_data.json` 保存本地状态。

## 构建 Windows 可执行文件

在 Windows 环境中安装依赖后执行：

```powershell
python -m PyInstaller --clean main.spec
```

构建结果位于 `dist/`。

## 免责声明

本项目是独立的社区工具，与 Electronic Arts Inc. 或 Respawn Entertainment 无关。Apex Legends 及相关素材归其各自权利人所有。
如果您是权利所有人并希望移除项目内相关素材，请联系我，我将立刻删除。