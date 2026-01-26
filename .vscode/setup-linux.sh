#!/bin/sh
# Setup Python environment for Linux

if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    
    echo "Upgrading pip, setuptools, and wheel..."
    .venv/bin/python -m pip install --upgrade pip setuptools wheel
    
    echo "Installing av package..."
    .venv/bin/python -m pip install --only-binary=av 'av>=14.0.0,<15.0.0'
    
    echo "Installing unitree_webrtc_connect..."
    .venv/bin/python -m pip install git+https://github.com/legion1581/unitree_webrtc_connect.git@v2.0.4
    
    echo "Installing moderngl, Pillow, PyQt5..."
    .venv/bin/python -m pip install moderngl Pillow PyQt5

    echo "Installing pywavefront..."
    .venv/bin/python -m pip install pywavefront
    
    echo "Environment setup complete!"
else
    echo "Virtual environment already exists."
fi
