#!/usr/bin/env python3
"""
Beaconator C2 Manager - Refactored Version
A universal C2 beacon framework manager supporting beacons in any programming language
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

# Import refactored modules
from config import ServerConfig, ConfigManager
from database import setup_database
from services import ServerManager
from ui import MainWindow
from utils import Logger, setup_taskbar_icon, ensure_directories
import utils

def main():
    # Initialize configuration
    config = ServerConfig()
    
    # Ensure required directories exist
    ensure_directories(config)
    
    # Initialize global logger
    utils.logger = Logger(config)
    
    # Setup taskbar icon
    setup_taskbar_icon(config)
    
    # Set up database
    SessionLocal, beacon_repository = setup_database(config.DB_PATH)
    
    # Create server manager
    server_manager = ServerManager(config, beacon_repository)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set dark theme
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(127, 127, 127))
    app.setPalette(dark_palette)

    # Create and show main window
    window = MainWindow(server_manager)
    window.show()
    
    # Start server
    server_manager.start()
    
    # Add shutdown handling to window close
    original_close_event = window.closeEvent
    def extended_close_event(event):
        original_close_event(event)  # Call original close event
        
        # Try to shutdown gracefully with timeout
        import threading
        def shutdown_with_timeout():
            try:
                server_manager.shutdown()
            except:
                pass  # Ignore shutdown errors
        
        shutdown_thread = threading.Thread(target=shutdown_with_timeout, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=3.0)  # Wait max 3 seconds
        

        
    window.closeEvent = extended_close_event
    
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        utils.logger.log_message("Received shutdown signal")
    finally:
        server_manager.shutdown()

if __name__ == '__main__':
    main()