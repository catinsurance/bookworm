# isaac mod manager (name pending)

## Build Instructions

I use [`pyinstaller`](https://www.geeksforgeeks.org/convert-python-script-to-exe-file/) to package the python script into an EXE. I do so in a virtual environment with only the necessary packages installed.

First, use pip to install the necessary packages:
```
py pip install -r "requirements.txt"
```

Then just use pyinstaller:
```
pyinstaller --onefile --windowed "main.py"
```