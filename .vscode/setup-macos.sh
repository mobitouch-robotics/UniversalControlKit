#!/bin/sh
# Setup Python environment for macOS

if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3.11 -m venv .venv
    
    echo "Upgrading pip, setuptools, and wheel..."
    .venv/bin/python -m pip install --upgrade pip setuptools wheel
    
    echo "Installing av package..."
    .venv/bin/python -m pip install --only-binary=av 'av>=14.0.0,<15.0.0'
    
    echo "Installing unitree_webrtc_connect..."
    .venv/bin/python -m pip install git+https://github.com/legion1581/unitree_webrtc_connect.git@v2.0.4
    
    echo "Installing PyQt5, Pillow, PyOpenGL, and PyOpenGL-accelerate..."
    .venv/bin/python -m pip install PyQt5 Pillow PyOpenGL PyOpenGL-accelerate
    
    echo "Environment setup complete!"
else
    echo "Virtual environment already exists."
fi
