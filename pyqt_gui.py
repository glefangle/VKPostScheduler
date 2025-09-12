"""
VK Post Scheduler - PyQt GUI
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QProgressBar, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
    QSpinBox, QTimeEdit, QDateEdit, QTabWidget, QSplitter, QFrame,
    QScrollArea, QSizePolicy, QSpacerItem, QMenu
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QDate, QTime, QDateTime,
    QPropertyAnimation, QEasingCurve, QRect
)
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush,
    QLinearGradient, QPen
)

@dataclass
class PostData:
    """Data class for post information"""
    text: str = ""
    photo_path: Optional[str] = None  # Keep for backward compatibility
    photo_paths: List[str] = None  # New field for multiple photos
    gif_name: str = ""
    gif_transform: bool = True  # Enable GIF transformation for VK compliance
    start_date: str = ""
    end_date: str = ""
    times: List[str] = None
    sleep_time: int = 1
    different_posts: bool = True
    
    def __post_init__(self):
        if self.times is None:
            self.times = []
        if self.photo_paths is None:
            self.photo_paths = []


class ModernButton(QPushButton):
    """Custom modern button with gradient background and hover effects"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(35)
        self.setFont(QFont("Segoe UI", 9, QFont.Medium))
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2, stop:1 #357abd);
                border: none;
                border-radius: 5px;
                color: white;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5ba0f2, stop:1 #4a90e2);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #357abd, stop:1 #2d6da3);
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)


class SecondaryButton(QPushButton):
    """Secondary button with different styling"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(30)
        self.setFont(QFont("Segoe UI", 8))
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                color: #495057;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background: #dee2e6;
            }
        """)


class ModernLineEdit(QLineEdit):
    """Modern line edit with better styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(35)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                padding: 8px 12px;
                background: white;
                color: #495057;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
            QLineEdit:disabled {
                background: #f8f9fa;
                color: #6c757d;
            }
        """)


class ModernComboBox(QComboBox):
    """Modern combo box with better styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(35)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("""
            QComboBox {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                padding: 8px 12px;
                background: white;
                color: #495057;
            }
            QComboBox:focus {
                border-color: #4a90e2;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #495057;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #4a90e2;
                border-radius: 5px;
                background: white;
                selection-background-color: #4a90e2;
                selection-color: white;
            }
        """)


class ModernTextEdit(QTextEdit):
    """Modern text edit with better styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                padding: 8px;
                background: white;
                color: #495057;
            }
            QTextEdit:focus {
                border-color: #4a90e2;
            }
        """)


class ModernListWidget(QListWidget):
    """Modern list widget with better styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("""
            QListWidget {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                background: white;
                color: #495057;
                outline: none;
            }
            QListWidget:focus {
                border-color: #4a90e2;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f8f9fa;
            }
            QListWidget::item:selected {
                background: #4a90e2;
                color: white;
            }
            QListWidget::item:hover {
                background: #e9ecef;
            }
        """)


class ModernProgressBar(QProgressBar):
    """Modern progress bar with gradient styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(20)
        self.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e9ecef;
                border-radius: 10px;
                text-align: center;
                background: #f8f9fa;
                color: #495057;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:1 #357abd);
                border-radius: 8px;
            }
        """)


class PyQtTokenDialog(QDialog):
    """PyQt version of the token dialog"""
    
    def __init__(self, parent, config_manager, token=None, callback=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.token = token
        self.callback = callback
        self.result = None
        
        self.setWindowTitle("Edit Token" if token else "Add Token")
        self.setFixedSize(450, 200)
        self.setModal(True)
        
        # Center the dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.create_widgets()
        self.setup_layout()
        
        # Focus on name entry
        self.name_edit.setFocus()
    
    def create_widgets(self):
        """Create dialog widgets"""
        self.name_label = QLabel("Token Name:")
        self.name_edit = ModernLineEdit()
        if self.token:
            self.name_edit.setText(self.token.name)
        
        self.token_label = QLabel("VK Token:")
        self.token_edit = ModernLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        if self.token:
            self.token_edit.setText(self.token.token)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
    
    def setup_layout(self):
        """Setup the dialog layout"""
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        form_layout.addRow(self.name_label, self.name_edit)
        form_layout.addRow(self.token_label, self.token_edit)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)
        
        self.setLayout(layout)
    
    def on_save(self):
        """Handle save button click"""
        name = self.name_edit.text().strip()
        token = self.token_edit.text().strip()
        
        if not name:
            QMessageBox.critical(self, "Error", "Token name cannot be empty")
            return
        
        if not token:
            QMessageBox.critical(self, "Error", "VK token cannot be empty")
            return
        
        try:
            # Import here to avoid circular imports
            from vk_config import VKToken
            
            # Create new token object
            groups = self.token.groups if self.token else []
            new_token = VKToken(name=name, token=token, groups=groups)
            
            if self.token:
                # Update existing token
                self.config_manager.update_token(self.token.name, new_token)
            else:
                # Add new token
                self.config_manager.add_token(new_token)
            
            self.result = new_token
            if self.callback:
                self.callback()
            self.accept()
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save token: {e}")


class PyQtGroupDialog(QDialog):
    """PyQt version of the group dialog"""
    
    def __init__(self, parent, token, group=None, callback=None):
        super().__init__(parent)
        self.token = token
        self.group = group
        self.callback = callback
        self.result = None
        
        self.setWindowTitle("Edit Group" if group else "Add Group")
        self.setFixedSize(450, 200)
        self.setModal(True)
        
        # Center the dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.create_widgets()
        self.setup_layout()
        
        # Focus on name entry
        self.name_edit.setFocus()
    
    def create_widgets(self):
        """Create dialog widgets"""
        self.name_label = QLabel("Group Name:")
        self.name_edit = ModernLineEdit()
        if self.group:
            self.name_edit.setText(self.group.name)
        
        self.id_label = QLabel("Group ID:")
        self.id_edit = ModernLineEdit()
        if self.group:
            self.id_edit.setText(self.group.group_id)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
    
    def setup_layout(self):
        """Setup the dialog layout"""
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        form_layout.addRow(self.name_label, self.name_edit)
        form_layout.addRow(self.id_label, self.id_edit)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)
        
        self.setLayout(layout)
    
    def on_save(self):
        """Handle save button click"""
        name = self.name_edit.text().strip()
        group_id = self.id_edit.text().strip()
        
        if not name:
            QMessageBox.critical(self, "Error", "Group name cannot be empty")
            return
        
        if not group_id:
            QMessageBox.critical(self, "Error", "Group ID cannot be empty")
            return
        
        try:
            # Import here to avoid circular imports
            from vk_config import VKGroup
            
            # Create new group object
            new_group = VKGroup(name=name, group_id=group_id)
            
            if self.group:
                # Update existing group
                self.token.update_group(self.group.name, new_group)
            else:
                # Add new group
                self.token.add_group(new_group)
            
            self.result = new_group
            if self.callback:
                self.callback()
            self.accept()
            
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save group: {e}")


class VKErrorDialog(QDialog):
    """Error dialog for displaying VK API errors and exceptions with full details"""
    
    def __init__(self, parent, error_title, error_message, vk_error_data=None):
        super().__init__(parent)
        self.setWindowTitle(error_title)
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        
        # Set up the layout
        layout = QVBoxLayout(self)
        
        # Error icon and main message
        header_layout = QHBoxLayout()
        
        # Error icon
        icon_label = QLabel()
        icon_label.setPixmap(self.style().standardIcon(self.style().SP_MessageBoxCritical).pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignTop)
        header_layout.addWidget(icon_label)
        
        # Main error message
        main_message = QLabel(error_message)
        main_message.setWordWrap(True)
        main_message.setStyleSheet("font-size: 24px; font-weight: bold; color: #d32f2f; padding: 10px;")
        header_layout.addWidget(main_message, 1)
        
        layout.addLayout(header_layout)
        
        # Detailed information section
        if vk_error_data:
            details_group = QGroupBox("Error Details")
            details_layout = QVBoxLayout(details_group)
            
            # Basic error info
            basic_info = QTextEdit()
            basic_info.setMaximumHeight(150)
            basic_info.setFont(QFont("Consolas", 10))
            
            basic_text = f"Error Message: {vk_error_data.get('error_message', 'No details')}\n"
            basic_text += f"Error Type: {vk_error_data.get('error_type', 'Unknown')}\n"
            basic_text += f"Post Time: {vk_error_data.get('post_time', 'Unknown')}\n"
            basic_text += f"Target Group: {vk_error_data.get('group_name', 'Unknown')}\n"
            basic_text += f"Attempt Number: {vk_error_data.get('attempt', 0) + 1}\n"
            
            basic_info.setPlainText(basic_text)
            basic_info.setReadOnly(True)
            details_layout.addWidget(basic_info)
            
            # Full traceback section
            traceback_text = vk_error_data.get('traceback', 'No traceback available')
            if traceback_text and traceback_text.strip():
                traceback_group = QGroupBox("Full Exception Traceback")
                traceback_layout = QVBoxLayout(traceback_group)
                
                traceback_edit = QTextEdit()
                traceback_edit.setFont(QFont("Consolas", 9))
                traceback_edit.setPlainText(traceback_text)
                traceback_edit.setReadOnly(True)
                traceback_edit.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
                traceback_layout.addWidget(traceback_edit)
                
                details_layout.addWidget(traceback_group)
            
            layout.addWidget(details_group)
        
        # Instructions
        #instructions = QLabel(
        #    "⚠️ The posting queue has been paused due to this error.\n"
        #    "Please review the error details above and choose how to proceed:"
        #)
        #instructions.setStyleSheet("font-size: 12px; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;")
        #instructions.setWordWrap(True)
        #layout.addWidget(instructions)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Copy to clipboard button
        copy_btn = QPushButton("📋 Copy Error Details")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        button_layout.addWidget(copy_btn)
        
        button_layout.addStretch()
        
        # Action buttons
        resume_btn = QPushButton("▶️ Resume Queue")
        resume_btn.clicked.connect(self.accept)
        resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        pause_btn = QPushButton("⏸️ Keep Paused")
        pause_btn.clicked.connect(self.reject)
        pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        
        button_layout.addWidget(pause_btn)
        button_layout.addWidget(resume_btn)
        
        layout.addLayout(button_layout)
        
        # Store data for copying
        self.error_data = {
            'title': error_title,
            'message': error_message,
            'vk_error_data': vk_error_data
        }
        
        # Set default button
        resume_btn.setDefault(True)
        resume_btn.setFocus()
    
    def copy_to_clipboard(self):
        """Copy all error details to clipboard"""
        try:
            from PyQt5.QtWidgets import QApplication
            
            clipboard_text = f"VK Post Scheduler Error Report\n"
            clipboard_text += f"{'='*50}\n\n"
            clipboard_text += f"Title: {self.error_data['title']}\n"
            clipboard_text += f"Message: {self.error_data['message']}\n\n"
            
            if self.error_data['vk_error_data']:
                vk_data = self.error_data['vk_error_data']
                clipboard_text += f"Error Details:\n"
                clipboard_text += f"- Error Type: {vk_data.get('error_type', 'Unknown')}\n"
                clipboard_text += f"- Error Message: {vk_data.get('error_message', 'No details')}\n"
                clipboard_text += f"- Post Time: {vk_data.get('post_time', 'Unknown')}\n"
                clipboard_text += f"- Target Group: {vk_data.get('group_name', 'Unknown')}\n"
                clipboard_text += f"- Attempt Number: {vk_data.get('attempt', 0) + 1}\n\n"
                
                traceback_text = vk_data.get('traceback', '')
                if traceback_text and traceback_text.strip():
                    clipboard_text += f"Full Traceback:\n{traceback_text}\n"
            
            clipboard_text += f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            QApplication.clipboard().setText(clipboard_text)
            
            # Show brief confirmation
            QTimer.singleShot(0, lambda: QMessageBox.information(
                self, "Copied", "Error details copied to clipboard!"
            ))
            
        except Exception as e:
            QMessageBox.warning(self, "Copy Failed", f"Failed to copy to clipboard: {e}")


class PostSchedulerPyQtGUI(QMainWindow):
    """Modern PyQt GUI for VK Post Scheduler"""
    
    # Qt signals for thread-safe GUI updates
    status_update_signal = pyqtSignal(str)
    progress_update_signal = pyqtSignal()
    error_update_signal = pyqtSignal(str, object)
    
    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core
        
        # Check if we're in testing mode (to avoid blocking dialogs)
        self._testing_mode = hasattr(app_core, 'tokens') or getattr(app_core, '_is_mock', False)
        
        # Register as observer for application core events
        self.app_core.add_status_observer(self._thread_safe_append_status)
        self.app_core.add_progress_observer(self._thread_safe_update_progress)
        self.app_core.add_error_observer(self._thread_safe_handle_error)
        
        # Connect all signals to their slots for thread-safe GUI updates
        self.status_update_signal.connect(self._append_status_safe)
        self.progress_update_signal.connect(self._update_progress_safe)
        self.error_update_signal.connect(self._handle_error_safe)
        
        # Note: Captcha handling is done through the application core
        # No direct captcha handler needed in GUI
        
        # Initialize variables
        self.photo_paths = []  # Changed to list for multiple files
        self.file_path = None
        self.post_text = ""
        self.start_date = datetime.now().strftime("%Y-%m-%d")
        self.end_date = datetime.now().strftime("%Y-%m-%d")
        self.times = []
        self.sleep_time = 1
        self.different_posts = True
        self.gif_transform = True
        
        self.setup_ui()
        self.setup_connections()
        self.refresh_vk_selections()
        
        # Check for pending jobs and auto-start worker if needed
        pending_count = self.app_core.get_pending_jobs_count()
        if pending_count > 0:
            self._append_status(f"Loaded {pending_count} pending jobs from previous session.")
            # Auto-start worker for pending jobs
            self.app_core.start_worker_if_needed()
            self._update_progress()
        else:
            # Still update progress to show initial state
            self._update_progress()
    
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("VK Post Scheduler")
        self.setMinimumSize(1000, 700)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #495057;
            }
            QLabel {
                color: #495057;
                font-weight: 500;
            }
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #e9ecef;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_post_tab()
        self.create_schedule_tab()
        self.create_status_tab()
        
        # Create bottom controls
        self.create_bottom_controls(main_layout)
    
    def create_post_tab(self):
        """Create the post configuration tab"""
        post_widget = QWidget()
        post_layout = QVBoxLayout(post_widget)
        post_layout.setSpacing(15)
        
        # VK Configuration Group
        vk_group = QGroupBox("VK Configuration")
        vk_layout = QGridLayout(vk_group)
        
        # Token selection
        vk_layout.addWidget(QLabel("Token:"), 0, 0)
        self.token_combo = ModernComboBox()
        self.token_combo.setMinimumWidth(200)  
        vk_layout.addWidget(self.token_combo, 0, 1)
        
        token_buttons_layout = QHBoxLayout()
        self.add_token_btn = SecondaryButton("Add")
        self.edit_token_btn = SecondaryButton("Edit")
        self.delete_token_btn = SecondaryButton("Delete")
        token_buttons_layout.addWidget(self.add_token_btn)
        token_buttons_layout.addWidget(self.edit_token_btn)
        token_buttons_layout.addWidget(self.delete_token_btn)
        token_buttons_layout.addStretch()
        vk_layout.addLayout(token_buttons_layout, 0, 2)
        
        # Group selection
        vk_layout.addWidget(QLabel("Group:"), 1, 0)
        self.group_combo = ModernComboBox()
        self.group_combo.setMinimumWidth(200) 
        vk_layout.addWidget(self.group_combo, 1, 1)
        
        group_buttons_layout = QHBoxLayout()
        self.add_group_btn = SecondaryButton("Add")
        self.edit_group_btn = SecondaryButton("Edit")
        self.delete_group_btn = SecondaryButton("Delete")
        group_buttons_layout.addWidget(self.add_group_btn)
        group_buttons_layout.addWidget(self.edit_group_btn)
        group_buttons_layout.addWidget(self.delete_group_btn)
        group_buttons_layout.addStretch()
        vk_layout.addLayout(group_buttons_layout, 1, 2)
        
        post_layout.addWidget(vk_group)
        
        # Post Content Group
        content_group = QGroupBox("Post Content")
        content_layout = QVBoxLayout(content_group)
        
        # Image selection
        image_layout = QHBoxLayout()
        image_layout.addWidget(QLabel("Images:"))
        self.photo_path_label = QLabel("No files selected")
        self.photo_path_label.setStyleSheet("color: #6c757d; font-style: italic;")
        image_layout.addWidget(self.photo_path_label)
        image_layout.addStretch()
        self.browse_photo_btn = SecondaryButton("Browse")
        image_layout.addWidget(self.browse_photo_btn)
        content_layout.addLayout(image_layout)
        
        # GIF Name and Transform options
        gif_layout = QHBoxLayout()
        gif_layout.addWidget(QLabel("GIF Name:"))
        self.gif_name_edit = ModernLineEdit()
        gif_layout.addWidget(self.gif_name_edit)
        gif_layout.addStretch()
        content_layout.addLayout(gif_layout)
        
        # GIF Transform checkbox
        gif_transform_layout = QHBoxLayout()
        self.gif_transform_checkbox = QCheckBox("Transform GIF for VK compliance (0.66:1 to 2.5:1 aspect ratio)")
        self.gif_transform_checkbox.setFont(QFont("Segoe UI", 9))
        self.gif_transform_checkbox.setChecked(True)  # Enable by default
        self.gif_transform_checkbox.setToolTip(
            "Automatically adjust GIF dimensions to meet VK's aspect ratio requirements.\n"
            "VK requires aspect ratios between 0.66:1 and 2.5:1 for proper display."
        )
        gif_transform_layout.addWidget(self.gif_transform_checkbox)
        gif_transform_layout.addStretch()
        content_layout.addLayout(gif_transform_layout)
        
        # Different posts checkbox
        self.different_posts_checkbox = QCheckBox("Enable different posts")
        self.different_posts_checkbox.setFont(QFont("Segoe UI", 9))
        self.different_posts_checkbox.setChecked(True)  # Enable by default
        content_layout.addWidget(self.different_posts_checkbox)
        
        # Post text
        content_layout.addWidget(QLabel("Post Text:"))
        self.text_edit = ModernTextEdit()
        self.text_edit.setMaximumHeight(100)
        content_layout.addWidget(self.text_edit)
        
        post_layout.addWidget(content_group)
        post_layout.addStretch()
        
        self.tab_widget.addTab(post_widget, "Post Configuration")
    
    def create_schedule_tab(self):
        """Create the scheduling tab"""
        schedule_widget = QWidget()
        schedule_layout = QVBoxLayout(schedule_widget)
        schedule_layout.setSpacing(15)
        
        # Date Selection Group
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout(date_group)
        
        date_layout.addWidget(QLabel("Start Date:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setMinimumHeight(35)
        self.start_date_edit.setMinimumWidth(150)  
        date_layout.addWidget(self.start_date_edit)
        
        date_layout.addWidget(QLabel("End Date:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setMinimumHeight(35)
        self.end_date_edit.setMinimumWidth(150)  
        date_layout.addWidget(self.end_date_edit)
        
        date_layout.addStretch()
        schedule_layout.addWidget(date_group)
        
        # Time Selection Group
        time_group = QGroupBox("Time Schedule")
        time_layout = QVBoxLayout(time_group)
        
        # Time input
        time_input_layout = QHBoxLayout()
        time_input_layout.addWidget(QLabel("Time:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setMinimumHeight(35)
        time_input_layout.addWidget(self.time_edit)
        
        self.add_time_btn = SecondaryButton("+")
        self.add_time_btn.setMaximumWidth(50)
        time_input_layout.addWidget(self.add_time_btn)
        
        self.remove_time_btn = SecondaryButton("-")
        self.remove_time_btn.setMaximumWidth(50)
        time_input_layout.addWidget(self.remove_time_btn)
        
        time_input_layout.addStretch()
        time_layout.addLayout(time_input_layout)
        
        # Schedule list
        time_layout.addWidget(QLabel("Day Schedule:"))
        self.schedule_list = ModernListWidget()
        self.schedule_list.setContextMenuPolicy(Qt.CustomContextMenu)
        time_layout.addWidget(self.schedule_list)
        
        schedule_layout.addWidget(time_group)
        
        # Sleep Time Group
        sleep_group = QGroupBox("Posting Settings")
        sleep_layout = QHBoxLayout(sleep_group)
        
        sleep_layout.addWidget(QLabel("Delay between posts (seconds):"))
        self.sleep_spinbox = QSpinBox()
        self.sleep_spinbox.setRange(0, 3600)
        self.sleep_spinbox.setValue(self.sleep_time)
        self.sleep_spinbox.setMinimumHeight(35)
        sleep_layout.addWidget(self.sleep_spinbox)
        
        self.apply_sleep_btn = SecondaryButton("Apply")
        sleep_layout.addWidget(self.apply_sleep_btn)
        sleep_layout.addStretch()
        
        schedule_layout.addWidget(sleep_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.schedule_btn = ModernButton("Schedule Posts")
        self.stop_btn = ModernButton("Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc3545, stop:1 #c82333);
                border: none;
                border-radius: 5px;
                color: white;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e74c3c, stop:1 #dc3545);
            }
        """)
        
        control_layout.addWidget(self.schedule_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        schedule_layout.addLayout(control_layout)
        schedule_layout.addStretch()
        
        self.tab_widget.addTab(schedule_widget, "Schedule")
    
    def create_status_tab(self):
        """Create the status and progress tab"""
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setSpacing(15)
        
        # Progress Group
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = ModernProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.counters_label = QLabel("Queued: 0 | Success: 0 | Failed: 0 | Pending: 0")
        self.counters_label.setFont(QFont("Segoe UI", 9, QFont.Medium))
        progress_layout.addWidget(self.counters_label)
        
        # Add Clear Jobs button
        clear_jobs_layout = QHBoxLayout()
        self.clear_jobs_btn = SecondaryButton("Clear All Jobs")
        self.clear_jobs_btn.clicked.connect(self.clear_all_jobs)
        clear_jobs_layout.addWidget(self.clear_jobs_btn)
        
        # Add Pause/Resume Queue button
        self.pause_resume_btn = SecondaryButton("Pause Queue")
        self.pause_resume_btn.clicked.connect(self.toggle_pause_resume)
        clear_jobs_layout.addWidget(self.pause_resume_btn)
        
        clear_jobs_layout.addStretch()
        progress_layout.addLayout(clear_jobs_layout)
        
        status_layout.addWidget(progress_group)
        
        # Jobs List Group - Show current jobs in queue
        jobs_group = QGroupBox("Current Jobs in Queue")
        jobs_layout = QVBoxLayout(jobs_group)
        
        self.jobs_list = ModernListWidget()
        self.jobs_list.setMaximumHeight(150)  # Limit height for jobs list
        self.jobs_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.jobs_list.customContextMenuRequested.connect(self.show_jobs_context_menu)
        jobs_layout.addWidget(self.jobs_list)
        
        # Add refresh jobs button
        refresh_jobs_layout = QHBoxLayout()
        self.refresh_jobs_btn = SecondaryButton("Refresh Jobs List")
        self.refresh_jobs_btn.clicked.connect(self.refresh_jobs_list)
        refresh_jobs_layout.addWidget(self.refresh_jobs_btn)
        refresh_jobs_layout.addStretch()
        jobs_layout.addLayout(refresh_jobs_layout)
        
        status_layout.addWidget(jobs_group)
        
        # Status Group - Made smaller in height
        status_group = QGroupBox("Status Log")
        status_layout_group = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont("Consolas", 9))
        self.status_text.setMaximumHeight(200)  # Limit height to make it smaller
        self.status_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e9ecef;
                border-radius: 5px;
                padding: 8px;
                background: #f8f9fa;
                color: #495057;
            }
        """)
        status_layout_group.addWidget(self.status_text)
        
        status_layout.addWidget(status_group)
        status_layout.addStretch()  # Push status to bottom
        
        self.tab_widget.addTab(status_widget, "Status")
    
    def create_bottom_controls(self, main_layout):
        """Create bottom control buttons"""
        bottom_layout = QHBoxLayout()
        
        # Add some spacing
        bottom_layout.addStretch()
        
        # Version info
        version_label = QLabel("VK Post Scheduler v0.9.5")
        version_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        bottom_layout.addWidget(version_label)
        
        main_layout.addLayout(bottom_layout)
    
    def setup_connections(self):
        """Setup signal connections"""
        # Token management
        self.add_token_btn.clicked.connect(self.add_token)
        self.edit_token_btn.clicked.connect(self.edit_token)
        self.delete_token_btn.clicked.connect(self.delete_token)
        
        # Group management
        self.add_group_btn.clicked.connect(self.add_group)
        self.edit_group_btn.clicked.connect(self.edit_group)
        self.delete_group_btn.clicked.connect(self.delete_group)
        
        # Token/Group selection
        self.token_combo.currentTextChanged.connect(self.on_token_selected)
        self.group_combo.currentTextChanged.connect(self.on_group_selected)
        
        # File operations
        self.browse_photo_btn.clicked.connect(self.browse_photo)
        
        # Time management
        self.add_time_btn.clicked.connect(self.add_time)
        self.remove_time_btn.clicked.connect(self.remove_time)
        self.schedule_list.customContextMenuRequested.connect(self.show_schedule_context_menu)
        
        # Sleep time
        self.apply_sleep_btn.clicked.connect(self.apply_sleep_time)
        
        # Main controls
        self.schedule_btn.clicked.connect(self.schedule_all_posts)
        self.stop_btn.clicked.connect(self.stop_worker)
        
        # Different posts checkbox
        self.different_posts_checkbox.toggled.connect(self.toggle_different_posts)
        
        # GIF transform checkbox
        self.gif_transform_checkbox.toggled.connect(self.toggle_gif_transform)
    
    def refresh_vk_selections(self):
        """Refresh the token and group comboboxes"""
        token_names, group_names, current_token, current_group = self.app_core.get_vk_selections()
        
        # Update token dropdown
        self.token_combo.clear()
        self.token_combo.addItems(token_names)
        
        # Set current selection or select the first token if none is selected
        if not current_token and token_names:
            current_token = token_names[0]
            self.app_core.set_vk_selection(current_token)
        
        if current_token and current_token in token_names:
            self.token_combo.setCurrentText(current_token)
            self.refresh_group_selection(current_token)
            
            # Get groups for this specific token
            token_group_names = self.app_core.get_vk_config().get_group_names(current_token)
            
            # Auto-select first group if no group is selected and groups exist
            if token_group_names and not current_group:
                current_group = token_group_names[0]
                self.app_core.set_vk_selection(current_token, current_group)
                self._append_status(f"Auto-selected first available group: {current_group}")
            
            # Set group selection if valid
            if current_group and current_group in token_group_names:
                self.group_combo.setCurrentText(current_group)
                # Load schedule for the selected group
                self._load_group_schedule()
            elif token_group_names:
                # If current group is invalid but groups exist, select first group
                self.group_combo.setCurrentText(token_group_names[0])
                self.app_core.set_vk_selection(current_token, token_group_names[0])
                self._load_group_schedule()
        else:
            self.token_combo.setCurrentText('')
            self.group_combo.clear()
            
        # Show status message if no valid selection
        if not self.app_core.get_vk_config().has_valid_selection():
            if not token_names:
                self._append_status("No VK tokens configured. Use 'Add' buttons to add tokens.")
            else:
                self._append_status("Please select a token and group to proceed with posting.")
    
    def refresh_group_selection(self, token_name: str):
        """Refresh group dropdown for the selected token"""
        self.group_combo.clear()
        if token_name:
            group_names = self.app_core.get_vk_config().get_group_names(token_name)
            self.group_combo.addItems(group_names)
    
    def on_token_selected(self, token_name: str):
        """Handle token selection change"""
        self.refresh_group_selection(token_name)
        self.group_combo.setCurrentText('')  # Clear group selection
        
        # Clear the schedule display when switching tokens
        self._clear_schedule_display()
        
        # Update VK config selection using business logic
        self.app_core.set_vk_selection(token_name)
    
    def on_group_selected(self, group_name: str):
        """Handle group selection change"""
        token_name = self.token_combo.currentText()
        
        if token_name and group_name:
            # Get previous selection to check if we need to save
            _, previous_group = self.app_core.get_vk_config().get_selection()
            
            # Save current schedule to previously selected group only if there was a valid previous selection
            # and it's different from the new selection
            if previous_group and previous_group != group_name:
                # Save with the previous token and group, not the current UI values
                previous_schedule = list(self.times)
                if previous_schedule:  # Only save if there's something to save
                    self.app_core.save_group_schedule(token_name, previous_group, previous_schedule)
                    self._append_status(f"Saved schedule for previous group '{previous_group}': {len(previous_schedule)} times")
            
            # Set new selection using business logic
            self.app_core.set_vk_selection(token_name, group_name)
            
            # Load schedule for the newly selected group
            self._load_group_schedule()
    
    def add_token(self):
        """Add new token"""
        def refresh_callback():
            self.app_core.get_vk_config().save_config()
            self.refresh_vk_selections()
            self._append_status("Token added successfully")
        
        dialog = PyQtTokenDialog(self, self.app_core.get_vk_config(), callback=refresh_callback)
        dialog.exec_()
    
    def edit_token(self):
        """Edit selected token"""
        token_name = self.token_combo.currentText()
        if not token_name:
            QMessageBox.warning(self, "Warning", "Please select a token to edit")
            return
        
        token = self.app_core.get_vk_config().get_token(token_name)
        if not token:
            QMessageBox.critical(self, "Error", f"Token '{token_name}' not found")
            return
        
        def refresh_callback():
            self.app_core.get_vk_config().save_config()
            self.refresh_vk_selections()
            self._append_status(f"Token '{token_name}' updated successfully")
        
        dialog = PyQtTokenDialog(self, self.app_core.get_vk_config(), token, callback=refresh_callback)
        dialog.exec_()
    
    def delete_token(self):
        """Delete selected token"""
        token_name = self.token_combo.currentText()
        if not token_name:
            QMessageBox.warning(self, "Warning", "Please select a token to delete")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete token '{token_name}' and all its groups?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.app_core.delete_token(token_name)
            if success:
                self.refresh_vk_selections()
                QMessageBox.information(self, "Success", "Token deleted successfully")
    
    def add_group(self):
        """Add new group to selected token"""
        token_name = self.token_combo.currentText()
        if not token_name:
            QMessageBox.warning(self, "Warning", "Please select a token first")
            return
        
        token = self.app_core.get_vk_config().get_token(token_name)
        if not token:
            QMessageBox.critical(self, "Error", f"Token '{token_name}' not found")
            return
        
        def refresh_callback():
            self.app_core.get_vk_config().save_config()
            self.refresh_vk_selections()
            self._append_status("Group added successfully")
        
        dialog = PyQtGroupDialog(self, token, callback=refresh_callback)
        dialog.exec_()
    
    def edit_group(self):
        """Edit selected group"""
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        
        if not token_name:
            QMessageBox.warning(self, "Warning", "Please select a token first")
            return
        
        if not group_name:
            QMessageBox.warning(self, "Warning", "Please select a group to edit")
            return
        
        token = self.app_core.get_vk_config().get_token(token_name)
        if not token:
            QMessageBox.critical(self, "Error", f"Token '{token_name}' not found")
            return
        
        group = token.get_group(group_name)
        if not group:
            QMessageBox.critical(self, "Error", f"Group '{group_name}' not found")
            return
        
        def refresh_callback():
            self.app_core.get_vk_config().save_config()
            self.refresh_vk_selections()
            self._append_status(f"Group '{group_name}' updated successfully")
        
        dialog = PyQtGroupDialog(self, token, group, callback=refresh_callback)
        dialog.exec_()
    
    def delete_group(self):
        """Delete selected group"""
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        
        if not token_name:
            QMessageBox.warning(self, "Warning", "Please select a token first")
            return
        
        if not group_name:
            QMessageBox.warning(self, "Warning", "Please select a group to delete")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete group '{group_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.app_core.delete_group(token_name, group_name)
            if success:
                self.refresh_vk_selections()
                QMessageBox.information(self, "Success", "Group deleted successfully")
    
    def browse_photo(self):
        """Browse for image files"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", "Image Files (*.jpg *.jpeg *.png *.gif)"
        )
        if file_paths:
            self.photo_paths = file_paths
            # Show filenames in label
            filenames = [os.path.basename(path) for path in file_paths]
            if len(filenames) == 1:
                display_text = filenames[0]
            else:
                display_text = f"{len(filenames)} files selected: {', '.join(filenames[:3])}"
                if len(filenames) > 3:
                    display_text += f" and {len(filenames) - 3} more"
            
            self.photo_path_label.setText(display_text)
            self.photo_path_label.setStyleSheet("color: #28a745; font-weight: bold;")
            QMessageBox.information(self, "Images Selected", f"Selected {len(filenames)} image(s)")
    
    def toggle_different_posts(self, checked: bool):
        """Handle different posts checkbox toggle"""
        # Update internal state
        self.different_posts = checked
        
        # Ensure checkbox state is synchronized (important for tests)
        # Use blockSignals to prevent recursive signal emission
        self.different_posts_checkbox.blockSignals(True)
        self.different_posts_checkbox.setChecked(checked)
        self.different_posts_checkbox.blockSignals(False)
        
        # Show dialogs only if we're not in test mode (avoid blocking in tests)
        if not hasattr(self, '_testing_mode') or not self._testing_mode:
            if checked:
                QMessageBox.information(self, "Different posts enabled", "Different posts feature is now enabled")
            else:
                QMessageBox.information(self, "Different posts disabled", "Different posts feature is now disabled")
    
    def toggle_gif_transform(self, checked: bool):
        """Handle GIF transform checkbox toggle"""
        # Update internal state
        self.gif_transform = checked
        
        # Ensure checkbox state is synchronized (important for tests)
        # Use blockSignals to prevent recursive signal emission
        self.gif_transform_checkbox.blockSignals(True)
        self.gif_transform_checkbox.setChecked(checked)
        self.gif_transform_checkbox.blockSignals(False)
        
        # Show dialogs only if we're not in test mode (avoid blocking in tests)
        if not hasattr(self, '_testing_mode') or not self._testing_mode:
            if checked:
                QMessageBox.information(
                    self, "GIF transform enabled", 
                    "GIFs will be automatically transformed to meet VK's aspect ratio requirements (0.66:1 to 2.5:1)."
                )
            else:
                QMessageBox.information(
                    self, "GIF transform disabled", 
                    "GIFs will be uploaded without transformation. Note: VK may not display them properly if they don't meet aspect ratio requirements."
                )
    
    def add_time(self):
        """Add time to schedule"""
        current_time = self.time_edit.time().toString("HH:mm")
        if current_time:
            self.times.append(current_time)
            self.schedule_list.addItem(current_time)
            # Auto-save the schedule to the currently selected group
            self._save_current_schedule_to_group()
    
    def remove_time(self):
        """Remove time from schedule"""
        current_item = self.schedule_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No selection", "Please select a time to remove.")
            return
        
        selected_time = current_item.text()
        if selected_time in self.times:
            self.times.remove(selected_time)
        
        # Remove from list widget
        row = self.schedule_list.row(current_item)
        self.schedule_list.takeItem(row)
        
        # Auto-save the schedule to the currently selected group
        self._save_current_schedule_to_group()
    
    def apply_sleep_time(self):
        """Apply sleep time setting"""
        try:
            sleep_time = self.sleep_spinbox.value()
            if sleep_time >= 0:
                self.sleep_time = sleep_time
                self._append_status(f"Sleep time set to {self.sleep_time} seconds.")
            else:
                QMessageBox.critical(self, "Error", "Sleep time must be a non-negative integer.")
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid sleep time. Please enter a non-negative integer.")
    
    def schedule_all_posts(self):
        """Schedule all posts"""
        # Get current values from GUI and create PostData
        text = self.text_edit.toPlainText().strip()
        gif_name = self.gif_name_edit.text().strip()
        different_posts = self.different_posts_checkbox.isChecked()
        
        # Get dates from date editors
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
        
        # Save the current text as default for the selected group
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        
        # Ensure token and group are selected before proceeding
        if not token_name:
            QMessageBox.critical(self, "Error", "Please select a VK token before scheduling posts.")
            return
            
        if not group_name:
            QMessageBox.critical(self, "Error", "Please select a VK group before scheduling posts.")
            return
            
        # Ensure the selection is properly set in the VK config
        self.app_core.set_vk_selection(token_name, group_name)
        
        if token_name and group_name and text:
            self.app_core.save_group_default_text(token_name, group_name, text)
        
        post_data = PostData(
            text=text,
            photo_path=None if (different_posts and len(self.photo_paths) > 1) else (self.photo_paths[0] if self.photo_paths else None),
            photo_paths=self.photo_paths.copy(),  # Pass all selected photos
            gif_name=gif_name,
            gif_transform=self.gif_transform_checkbox.isChecked(),
            start_date=start_date,
            end_date=end_date,
            times=self.times.copy(),
            sleep_time=self.sleep_time,
            different_posts=different_posts
        )
        
        # Use application core to schedule posts
        success = self.app_core.schedule_posts(post_data)
        
        if success:
            QMessageBox.information(self, "Scheduled", "All posts have been enqueued. They will be posted in the background.")
    
    def stop_worker(self):
        """Stop the worker thread"""
        self.app_core.stop_worker()
    
    def clear_all_jobs(self):
        """Clear all pending jobs"""
        reply = QMessageBox.question(
            self, "Confirm Clear Jobs", 
            "Are you sure you want to clear all pending jobs? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear jobs from the scheduler
            self.app_core.clear_all_jobs()
            self._append_status("All pending jobs have been cleared")
            self._update_progress()
    
    def toggle_pause_resume(self):
        """Toggle pause/resume of the queue"""
        if self.app_core.is_queue_paused():
            self.app_core.resume_worker()
            self.pause_resume_btn.setText("Pause Queue")
            self._append_status("Queue resumed by user")
        else:
            self.app_core.pause_worker()
            self.pause_resume_btn.setText("Resume Queue")
            self._append_status("Queue paused by user")
    
    def refresh_jobs_list(self, show_status=True):
        """Refresh the list of current jobs in the queue"""
        self.jobs_list.clear()
        jobs = self.app_core.get_current_jobs()
        if jobs:
            for job in jobs:
                post_time = job.get('post_time', 'Unknown')
                attempt = job.get('attempt', 0)
                status = job.get('status', 'pending')
                
                # Build display text with photo information
                display_text = f"{post_time} (Attempt: {attempt}, Status: {status})"
                
                # Add photo information if available
                if 'photo_filename' in job:
                    photo_filename = job['photo_filename']
                    if 'photo_index' in job and 'total_photos' in job:
                        photo_index = job['photo_index']
                        total_photos = job['total_photos']
                        display_text += f" - 📸 {photo_filename} ({photo_index + 1}/{total_photos})"
                    else:
                        display_text += f" - 📸 {photo_filename}"
                elif 'post_data' in job or not any(key.startswith('photo') for key in job.keys()):
                    # Check if this is a text-only post
                    display_text += " - 📝 Text only"
                
                # Store the post_time as data for context menu access
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, post_time)
                self.jobs_list.addItem(item)
            if show_status:
                self._append_status(f"Refreshed jobs list. {len(jobs)} jobs in queue.")
        else:
            if show_status:
                self._append_status("No jobs currently in the queue.")
    
    def show_jobs_context_menu(self, position):
        """Show context menu for jobs list"""
        item = self.jobs_list.itemAt(position)
        if item is None:
            return
        
        # Create context menu
        context_menu = QMenu(self)
        
        # Add remove job action
        remove_action = context_menu.addAction("Remove Job")
        remove_action.triggered.connect(lambda: self.remove_selected_job(item))
        
        # Show context menu
        context_menu.exec_(self.jobs_list.mapToGlobal(position))
    
    def remove_selected_job(self, item):
        """Remove the selected job from the queue"""
        if item is None:
            return
        
        # Get post_time from item data
        post_time = item.data(Qt.UserRole)
        if not post_time:
            QMessageBox.warning(self, "Error", "Could not identify job to remove")
            return
        
        # Confirm removal
        reply = QMessageBox.question(
            self, "Confirm Remove Job", 
            f"Are you sure you want to remove this job?\n\nPost Time: {post_time}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove the job
            success = self.app_core.remove_job(post_time)
            if success:
                self._append_status(f"Removed job: {post_time}")
                # Refresh the jobs list to reflect the change
                self.refresh_jobs_list(show_status=False)
                # Update progress display
                self._update_progress()
            else:
                QMessageBox.warning(self, "Error", f"Failed to remove job: {post_time}")
    
    def show_schedule_context_menu(self, position):
        """Show context menu for schedule list"""
        item = self.schedule_list.itemAt(position)
        
        # Create context menu
        context_menu = QMenu(self)
        
        # Remove time action (only if item is selected)
        if item is not None:
            context_menu.addSeparator()
            selected_time = item.text()
            remove_action = context_menu.addAction(f"Remove Time ({selected_time})")
            remove_action.triggered.connect(lambda: self.remove_time_from_context(item))
        
        # Show context menu
        context_menu.exec_(self.schedule_list.mapToGlobal(position))
        
    def remove_time_from_context(self, item):
        """Remove time from context menu"""
        if item is None:
            return
        
        selected_time = item.text()
        if selected_time in self.times:
            self.times.remove(selected_time)
        
        # Remove from list widget
        row = self.schedule_list.row(item)
        self.schedule_list.takeItem(row)
        
        # Auto-save the schedule to the currently selected group
        self._save_current_schedule_to_group()
        
        self._append_status(f"Removed time: {selected_time}")
    
    def _save_current_schedule_to_group(self):
        """Save the current schedule times to the currently selected group"""
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        
        if not token_name or not group_name:
            return
        
        # Get current times from the UI
        current_schedule = list(self.times)
        self.app_core.save_group_schedule(token_name, group_name, current_schedule)
    
    def _clear_schedule_display(self):
        """Clear the schedule display (times list and listbox)"""
        try:
            self.times.clear()
            self.schedule_list.clear()
            self._append_status("Cleared schedule display")
        except Exception as e:
            self._append_status(f"Error clearing schedule display: {e}")
    
    def _load_group_schedule(self):
        """Load the schedule and default text for the currently selected group into the UI"""
        try:
            token_name = self.token_combo.currentText()
            group_name = self.group_combo.currentText()
            
            if not token_name or not group_name:
                return
            
            # Load group's schedule
            group_schedule = self.app_core.get_group_schedule(token_name, group_name)
            
            # Clear current schedule UI
            self._clear_schedule_display()
            
            # Load group's schedule
            for time_str in group_schedule:
                self.times.append(time_str)
                self.schedule_list.addItem(time_str)
            
            # Load group's default text
            default_text = self.app_core.get_group_default_text(token_name, group_name)
            if default_text:
                self.text_edit.setPlainText(default_text)
                self._append_status(f"Loaded default text for group '{group_name}'")
            else:
                self.text_edit.setPlainText("")  # Clear text if no default
            
            if group_schedule:
                self._append_status(f"Loaded {len(group_schedule)} scheduled times for group '{group_name}'")
            else:
                self._append_status(f"No scheduled times for group '{group_name}'")
        except Exception as e:
            self._append_status(f"Error loading group data: {e}")
    
    def _thread_safe_append_status(self, text: str):
        """Thread-safe wrapper for status updates - emits signal to main thread"""
        self.status_update_signal.emit(text)
    
    def _thread_safe_update_progress(self):
        """Thread-safe wrapper for progress updates - emits signal to main thread"""
        self.progress_update_signal.emit()
    
    def _thread_safe_handle_error(self, message: str, vk_error_data=None):
        """Thread-safe wrapper for error handling - emits signal to main thread"""
        self.error_update_signal.emit(message, vk_error_data)
    
    def _append_status_safe(self, text: str):
        """Append text to status display - runs in main thread"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.status_text.append(f"[{timestamp}] {text}")
            # Auto-scroll to bottom
            scrollbar = self.status_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception:
            pass
    
    def _append_status(self, text: str):
        """Direct status append for internal GUI use (main thread only)"""
        self._append_status_safe(text)
    
    def _update_progress_safe(self):
        """Update progress display using business logic stats - runs in main thread"""
        try:
            stats = self.app_core.get_progress_stats()
            self.progress_bar.setMaximum(max(1, stats['total']))
            self.progress_bar.setValue(stats['completed'])
            self.counters_label.setText(
                f"Queued: {stats['total']} | Success: {stats['success']} | Failed: {stats['failed']} | Pending: {stats['pending']}"
            )
            
            # Update pause/resume button state
            if self.app_core.is_queue_paused():
                self.pause_resume_btn.setText("Resume Queue")
            else:
                self.pause_resume_btn.setText("Pause Queue")
            
            # Refresh jobs list without status updates to avoid spam
            self.refresh_jobs_list(show_status=False)
        except Exception:
            pass  # Ignore errors in progress updates to avoid crashes
    
    def _update_progress(self):
        """Direct progress update for internal GUI use (main thread only)"""
        self._update_progress_safe()
    
    def _handle_error_safe(self, message: str, vk_error_data=None):
        """Handle errors from business logic with comprehensive error display - runs in main thread"""
        try:
            # Log to status immediately
            self._append_status(f"🚨 POSTING ERROR OCCURRED: {message}")
            
            # Show comprehensive error dialog
            def show_error_dialog():
                try:
                    # Make sure the main window is visible and brought to front
                    self.show()
                    self.raise_()
                    self.activateWindow()
                    
                    # Create and show the comprehensive error dialog
                    error_dialog = VKErrorDialog(
                        self,
                        "VK Posting Error - Queue Paused",
                        f"A posting error occurred and the queue has been paused.\n\n",
                        vk_error_data
                    )
                    
                    # Center the dialog on the main window
                    try:
                        parent_geometry = self.geometry()
                        dialog_geometry = error_dialog.geometry()
                        
                        x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
                        y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2
                        
                        error_dialog.move(x, y)
                    except Exception:
                        pass  # Use default position if centering fails
                    
                    # Show the dialog and handle the result
                    result = error_dialog.exec_()
                    
                    if result == QDialog.Accepted:  # Resume button clicked
                        self.app_core.resume_worker()
                        self._append_status("▶️ Queue resumed by user after error")
                    else:  # Keep Paused button clicked or dialog closed
                        self._append_status("⏸️ Queue remains paused by user choice")
                    
                    # Update UI to reflect queue state
                    self._update_progress()
                    
                except Exception as dialog_error:
                    logging.error(f"Error showing error dialog: {dialog_error}")
                    # Fallback to simple message box
                    try:
                        self.show()
                        self.raise_()
                        self.activateWindow()
                        
                        fallback_message = f"A posting error occurred:\n{message}\n\n"
                        if vk_error_data:
                            fallback_message += f"Error Type: {vk_error_data.get('error_type', 'Unknown')}\n"
                            fallback_message += f"Details: {vk_error_data.get('error_message', 'No details')}\n\n"
                        fallback_message += "The queue has been paused. Resume manually from the Status tab."
                        
                        QMessageBox.critical(self, "VK Post Error", fallback_message)
                        self._append_status("Error dialog shown (fallback mode)")
                    except Exception:
                        # Last resort - just log and resume
                        logging.critical(f"Complete dialog failure: {dialog_error}")
                        self.app_core.resume_worker()
                        self._append_status("Queue resumed after dialog failure")
            
            # Run dialog in main thread
            QTimer.singleShot(0, show_error_dialog)
        except Exception:
            pass  # Ignore errors in error handling to avoid recursive crashes
    
    def _handle_error(self, message: str, vk_error_data=None):
        """Direct error handling for internal GUI use (main thread only)"""
        self._handle_error_safe(message, vk_error_data)
    
    def closeEvent(self, event):
        """Handle application close event to ensure proper shutdown"""
        try:
            # Log the close event
            self._append_status("Application closing - ensuring proper shutdown...")
            
            # Properly shutdown the application core to save job states
            if self.app_core:
                self.app_core.shutdown()
                self._append_status("Application core shutdown complete")
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            # Log any shutdown errors but still allow close
            logging.error(f"Error during application shutdown: {e}")
            try:
                self._append_status(f"Shutdown error (proceeding anyway): {e}")
            except:
                pass  # Status display might not be available
            
            # Still accept the close event to prevent app hanging
            event.accept()


def main():
    """Main entry point for PyQt GUI"""
    # Import here to avoid circular imports
    from main import ApplicationCore
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("VK Post Scheduler")
    app.setApplicationVersion("6.0.0")
    app.setOrganizationName("VK Post Scheduler")
    
    # Create application core
    app_core = ApplicationCore()
    
    # Create and show main window
    window = PostSchedulerPyQtGUI(app_core)
    window.show()
    
    # Start the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
