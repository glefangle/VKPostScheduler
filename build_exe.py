"""Generate the PyInstaller spec and build dist/PostScheduler.exe."""

import os
import subprocess
import sys

APP_NAME = "PostScheduler"
ENTRY_POINT = "main.py"
ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(ROOT, APP_NAME + ".spec")

# PyQt modules the app never imports
EXCLUDED_MODULES = [
    "tkinter", "curses", "pydoc_data",
    "PyQt5.QtBluetooth", "PyQt5.QtDBus", "PyQt5.QtDesigner",
    "PyQt5.QtHelp", "PyQt5.QtLocation", "PyQt5.QtMacExtras",
    "PyQt5.QtMultimedia", "PyQt5.QtMultimediaWidgets",
    "PyQt5.QtNetwork", "PyQt5.QtNetworkAuth", "PyQt5.QtNfc",
    "PyQt5.QtOpenGL", "PyQt5.QtPositioning", "PyQt5.QtPrintSupport",
    "PyQt5.QtPurchasing", "PyQt5.QtQml", "PyQt5.QtQuick",
    "PyQt5.QtQuickWidgets", "PyQt5.QtRemoteObjects", "PyQt5.QtSensors",
    "PyQt5.QtSerialPort", "PyQt5.QtSql", "PyQt5.QtSvg", "PyQt5.QtTest",
    "PyQt5.QtTextToSpeech", "PyQt5.QtWebChannel", "PyQt5.QtWebSockets",
    "PyQt5.QtWinExtras", "PyQt5.QtXml", "PyQt5.uic",
]

# unused Qt GL/QML/network dlls and imageformat/platform plugins
DROP_BINARIES = [
    "qt5qml", "qt5quick", "qt5websockets", "qt5network", "qt5svg",
    "opengl32sw", "d3dcompiler_47", "libegl", "libglesv2",
    "qwebgl", "qminimal", "qoffscreen", "qsvg", "qicns", "qtga",
    "qwbmp", "qtiff", "qtuiotouchplugin", "qxdgdesktopportal",
]
