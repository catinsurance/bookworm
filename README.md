# Bookworm - A Repentance(+) mod and modpack manager!
Bookworm is a mod manager for Repentance and Repentance+ (untested on Afterbirth+). It allows creating and sharing modpacks, as well as managing if your mods are enabled or disabled.

<img src="repo/preview1.png" alt="Preview image" width="500"/>
<img src="repo/preview2.png" alt="Preview image" width="500"/>

## Build Instructions

I use [`pyinstaller`](https://www.geeksforgeeks.org/convert-python-script-to-exe-file/) to package the python script into an EXE. I do so in a virtual environment with only the necessary packages installed.

First, use pip to install the necessary packages:
```
py pip install -r "requirements.txt"
```

To run by itself, you can just run the python script, either by double-clicking it if Python is added to PATH, or by running it in a cmd prompt.
```
cd directory/with/python/script
main.py
```

I also use Pyinstaller to package Bookworm into an `exe`:
```
pyinstaller --onefile --windowed --icon=resources/app_icon.ico "main.py"
```
Make sure that's being run in the same directory with the script. I recommend doing this in a virtual environment.

## Consider supporting me on Ko-Fi
[If you think my work here is worth more than $0, please consider supporting me on Ko-Fi!](https://ko-fi.com/catinsurance)