[中文版](README.md)
# APEX Pack Pity Counter

A Windows desktop application for manually tracking Apex Legends pack pity progress. It records the number of packs opened and the number of heirlooms obtained, then allows you to reset the pack counter after receiving an heirloom.

## Features

- Increase, decrease, and manually enter the pack count
- Record the number of heirlooms obtained
- Display progress toward the 500-pack pity threshold
- Change the background theme and button theme
- Save counter data locally

## Requirements

- Windows 10 or later
- Python 3.10+

The application uses Tkinter for its interface. If you see an error about a missing `tkinter` module, reinstall Python and enable the Tcl/Tk component.

## Run From Source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

After starting the application, it creates `pack_counter_data.json` in the application directory to store local data.

## Build the Windows Executable

Install the dependencies in a Windows environment, then run:

```powershell
python -m PyInstaller --clean main.spec
```

The build output is placed in `dist/`.

## Disclaimer

This is an independent community tool and is not affiliated with Electronic Arts Inc. or Respawn Entertainment. Apex Legends and related materials belong to their respective rights holders.

If you are a rights holder and would like related materials in this project to be removed, please contact me and I will remove them promptly.
