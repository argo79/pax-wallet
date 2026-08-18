#!/usr/bin/env python3
"""
PAX Wallet Desktop - Entry Point
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings
from ui.main_window import MainWindow

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("PAX Wallet")
    app.setOrganizationName("HOPE")
    
    settings = QSettings("HOPE", "PAX Wallet")
    
    skin_name = settings.value("skin", "style_dark")
    
    style_path = Path(__file__).parent / "ui" / "resources" / "styles" / f"{skin_name}.qss"
    if style_path.exists():
        with open(style_path, 'r') as f:
            app.setStyleSheet(f.read())
    else:
        fallback_path = Path(__file__).parent / "ui" / "resources" / "styles.qss"
        if fallback_path.exists():
            with open(fallback_path, 'r') as f:
                app.setStyleSheet(f.read())
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()