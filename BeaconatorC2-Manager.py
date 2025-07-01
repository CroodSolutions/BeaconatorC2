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
from services import CommandProcessor, FileTransferService
from services.receivers import ReceiverManager
from services.receivers.legacy_migration import ensure_legacy_receiver_exists
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
    
    # Create core services directly
    command_processor = CommandProcessor(beacon_repository)
    file_transfer_service = FileTransferService()
    
    # Create receiver manager for new architecture
    receiver_manager = ReceiverManager(
        command_processor=command_processor,
        file_transfer_service=file_transfer_service
    )
    
    # Ensure legacy-compatible receiver exists
    legacy_receiver_id = ensure_legacy_receiver_exists(config)
    if legacy_receiver_id:
        utils.logger.log_message(f"Legacy-compatible receiver created/updated: {legacy_receiver_id}")
    else:
        utils.logger.log_message("Warning: Failed to create legacy-compatible receiver")
    
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

    # Create and show main window with services
    window = MainWindow(
        beacon_repository=beacon_repository,
        command_processor=command_processor,
        file_transfer_service=file_transfer_service,
        receiver_manager=receiver_manager
    )
    window.show()
    
    # Legacy server fully retired - using only ReceiverManager
    
    # Note: Receivers will auto-start through ReceiverManager
    utils.logger.log_message("Application started")
    
    # Add shutdown handling to window close
    original_close_event = window.closeEvent
    def extended_close_event(event):
        original_close_event(event)  # Call original close event
        
        # Try to shutdown gracefully with timeout
        import threading
        def shutdown_with_timeout():
            try:
                receiver_manager.shutdown()
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
        receiver_manager.shutdown()

if __name__ == '__main__':
    main()