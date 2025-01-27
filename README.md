# isaac mod manager (name pending)

## Build Instructions

I use [`pyinstaller`](https://www.geeksforgeeks.org/convert-python-script-to-exe-file/) to package the python script into an EXE. I do so in a virtual environment with only the necessary packages installed.

First, use pip to install `requirements.txt`. After doing so, run the following commands:
```
pip install Cython
pip install h5py
```

You can thank [this bug](https://github.com/h5py/h5py/issues/535) for that.

Then just use pyinstaller:
```
pyinstaller --onefile --windowed "main.py"
```