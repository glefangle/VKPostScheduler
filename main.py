"""VK Post Scheduler - Main Application Entry Point

This module contains the core application logic and orchestrates the interaction
between GUI and business logic components following proper design patterns.
"""

import logging
import sys
import traceback
from datetime import datetime
import os
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from post_scheduler import PostScheduler
from vk_config import VKConfigManager


@dataclass
class PostData:
    """Data class for post information"""
    text: str = ""
    photo_path: Optional[str] = None  # Keep for backward compatibility
    photo_paths: Optional[List[str]] = None  # New field for multiple photos
    gif_name: str = ""
    start_date: str = ""
    end_date: str = ""
    times: Optional[List[str]] = None
    sleep_time: int = 1
    different_posts: bool = False
    
    def __post_init__(self):
        if self.times is None:
            self.times = []
        if self.photo_paths is None:
            self.photo_paths = []


class ApplicationCore:
    """Core application class that coordinates business logic and GUI"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize business logic components
        self.scheduler = PostScheduler()
        self.vk_config = self.scheduler.get_vk_config()
        
        # GUI callbacks (Observer pattern)
        self._status_observers: List[Callable[[str], None]] = []
        self._progress_observers: List[Callable[[], None]] = []
        self._error_observers: List[Callable[[str, Any], None]] = []
        
        # Set up scheduler callbacks
        self.scheduler.set_callbacks(
            status_callback=self._notify_status,
            progress_callback=self._notify_progress,
            error_callback=self._notify_error
        )
        
        self.logger.info("Application core initialized")
    
    # Observer Pattern Implementation
    def add_status_observer(self, callback: Callable[[str], None]):
        """Add status update observer"""
        self._status_observers.append(callback)
    
    def add_progress_observer(self, callback: Callable[[], None]):
        """Add progress update observer"""
        self._progress_observers.append(callback)
    
    def add_error_observer(self, callback: Callable[[str, Any], None]):
        """Add error observer"""
        self._error_observers.append(callback)
    
    def _notify_status(self, message: str):
        """Notify all status observers"""
        for observer in self._status_observers:
            try:
                observer(message)
                self.logger.info(message)
            except Exception as e:
                self.logger.error(f"Error in status observer: {e}")
    
    def _notify_progress(self):
        """Notify all progress observers"""
        for observer in self._progress_observers:
            try:
                observer()
            except Exception as e:
                self.logger.error(f"Error in progress observer: {e}")
    
    def _notify_error(self, message: str, error_data: Any = None):
        """Notify all error observers"""
        for observer in self._error_observers:
            try:
                observer(message, error_data)
            except Exception as e:
                self.logger.error(f"Error in error observer: {e}")
    
    # Business Logic Facade Methods
    def get_vk_selections(self) -> tuple:
        """Get VK token and group selections"""
        return self.scheduler.refresh_vk_selections()
    
    def set_vk_selection(self, token_name: str, group_name: Optional[str] = None) -> bool:
        """Set VK token and group selection"""
        if group_name:
            return self.scheduler.set_group_selection(token_name, group_name)
        else:
            return self.scheduler.set_token_selection(token_name)
    
    def get_group_schedule(self, token_name: str, group_name: str) -> List[str]:
        """Get schedule for a group"""
        return self.scheduler.get_group_schedule(token_name, group_name)
    
    def save_group_schedule(self, token_name: str, group_name: str, schedule: List[str]) -> bool:
        """Save schedule for a group"""
        return self.scheduler.save_group_schedule(token_name, group_name, schedule)
    
    def get_group_default_text(self, token_name: str, group_name: str) -> str:
        """Get default text for a group"""
        return self.scheduler.get_group_default_text(token_name, group_name)
    
    def save_group_default_text(self, token_name: str, group_name: str, default_text: str) -> bool:
        """Save default text for a group"""
        return self.scheduler.save_group_default_text(token_name, group_name, default_text)
    
    def validate_post_data(self, post_data_or_text, photo_path=None, start_date=None, end_date=None, times=None) -> tuple[bool, str]:
        """Validate post data - handles both PostData object and individual parameters"""
        # Handle both PostData object and individual parameters
        if hasattr(post_data_or_text, 'text'):  # PostData object
            text = post_data_or_text.text
            photo_path = post_data_or_text.photo_path
            start_date = post_data_or_text.start_date
            end_date = post_data_or_text.end_date
            times = post_data_or_text.times or []
        else:  # Individual parameters
            text = post_data_or_text
            photo_path = photo_path or ""
            start_date = start_date or ""
            end_date = end_date or ""
            times = times or []
            
        return self.scheduler.validate_post_data(
            text, photo_path, start_date, end_date, times
        )
    
    def schedule_posts(self, post_data: PostData) -> bool:
        """Schedule posts using business logic"""
        return self.scheduler.schedule_posts(
            text=post_data.text,
            photo_path=post_data.photo_path or "",
            gif_name=post_data.gif_name,
            start_date=post_data.start_date,
            end_date=post_data.end_date,
            times=post_data.times or [],
            sleep_time=post_data.sleep_time,
            different_posts=post_data.different_posts,
            photo_paths=post_data.photo_paths or []  # Pass the list of selected photos
        )
    
    def get_progress_stats(self) -> Dict[str, int]:
        """Get progress statistics"""
        return self.scheduler.get_progress_stats()
    
    def stop_worker(self):
        """Stop the worker thread (preserves jobs by default)"""
        self.scheduler.stop_worker(preserve_jobs=True)
    
    def resume_worker(self):
        """Resume the worker thread"""
        self.scheduler.resume_worker()
    
    def clear_all_jobs(self):
        """Clear all pending jobs"""
        self.scheduler._clear_all_jobs()
    
    def stop_worker_preserve_jobs(self):
        """Stop worker while preserving jobs for next app start"""
        self.scheduler.stop_worker(preserve_jobs=True)
    
    def stop_worker_clear_jobs(self):
        """Stop worker and clear all jobs"""
        self.scheduler.stop_worker(preserve_jobs=False)
    
    def is_queue_paused(self) -> bool:
        """Check if the queue is currently paused"""
        return self.scheduler.pause_flag
    
    def pause_worker(self):
        """Pause the worker thread"""
        self.scheduler.pause_flag = True
        self.scheduler._notify_status("⏸️ Queue paused by user")
    
    def get_current_jobs(self) -> List[Dict]:
        """Get current jobs in the queue"""
        return self.scheduler._get_current_jobs()
    
    def remove_job(self, post_time: str) -> bool:
        """Remove a specific job from the queue by post_time"""
        try:
            # Find the job in the current jobs list
            jobs = self.get_current_jobs()
            job_to_remove = None
            for job in jobs:
                if job.get('post_time') == post_time:
                    job_to_remove = job
                    break
            
            if job_to_remove:
                # Remove from scheduler state
                self.scheduler._remove_job_from_state(job_to_remove)
                self.logger.info(f"Removed job with post_time: {post_time}")
                return True
            else:
                self.logger.warning(f"Job with post_time {post_time} not found")
                return False
        except Exception as e:
            self.logger.error(f"Error removing job {post_time}: {e}")
            return False
    
    # VK Configuration Management Facade
    def get_vk_config(self) -> VKConfigManager:
        """Get VK configuration manager"""
        return self.vk_config
    
    def add_token(self, name: str, token: str) -> bool:
        """Add new VK token"""
        return self.scheduler.add_token(name, token)
    
    def edit_token(self, old_name: str, new_name: str, new_token: str) -> bool:
        """Edit existing VK token"""
        return self.scheduler.edit_token(old_name, new_name, new_token)
    
    def delete_token(self, name: str) -> bool:
        """Delete VK token"""
        return self.scheduler.delete_token(name)
    
    def add_group(self, token_name: str, group_name: str, group_id: str) -> bool:
        """Add new VK group"""
        return self.scheduler.add_group(token_name, group_name, group_id)
    
    def edit_group(self, token_name: str, old_name: str, new_name: str, new_id: str) -> bool:
        """Edit existing VK group"""
        return self.scheduler.edit_group(token_name, old_name, new_name, new_id)
    
    def delete_group(self, token_name: str, group_name: str) -> bool:
        """Delete VK group"""
        return self.scheduler.delete_group(token_name, group_name)
    
    def update_token(self, name: str, token: str) -> bool:
        """Update existing VK token (alias for edit_token)"""
        return self.scheduler.edit_token(name, name, token)
    
    def update_group(self, token_name: str, group_name: str, group_id: str) -> bool:
        """Update existing VK group (alias for edit_group)"""
        return self.scheduler.edit_group(token_name, group_name, group_name, group_id)
    
    def start_worker_if_needed(self):
        """Start worker thread if not already running (for pending jobs)"""
        self.scheduler._start_worker_if_needed()
    
    def get_pending_jobs_count(self) -> int:
        """Get count of pending jobs"""
        return self.scheduler._pending_jobs_count()
    
    def get_crash_detection_status(self) -> dict:
        """Get Qt crash detection status for debugging"""
        return self.scheduler.get_crash_detection_status()
    
    def enable_crash_detection(self, enabled: bool = True):
        """Enable or disable Qt crash detection logging"""
        self.scheduler.enable_crash_detection(enabled)
        if enabled:
            self.logger.info("Qt crash detection enabled")
        else:
            self.logger.info("Qt crash detection disabled")
    
    def shutdown(self):
        """Clean shutdown of the application"""
        self.logger.info("Shutting down application core...")
        # Use preserve_jobs=True to keep jobs for next app start
        self.scheduler.stop_worker(preserve_jobs=True)
        self.logger.info("Application core shutdown complete")


# Application Infrastructure
def setup_logging():
    """Set up comprehensive logging for the application"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create log filename with timestamp
    log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Also create a simple error.log for easy access
    error_handler = logging.FileHandler('error.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Add error handler to root logger
    logging.getLogger().addHandler(error_handler)
    
    # Set up Qt crash detection logger with enhanced visibility
    qt_crash_logger = logging.getLogger('qt_crash_detection')
    qt_crash_logger.setLevel(logging.DEBUG)  # Capture all crash detection events
    
    # Create a dedicated Qt crash handler for the main log
    qt_crash_handler = logging.FileHandler(log_filename, encoding='utf-8')
    qt_crash_handler.setFormatter(logging.Formatter(
        '%(asctime)s - QT_CRASH - %(levelname)s - %(message)s'
    ))
    qt_crash_logger.addHandler(qt_crash_handler)
    
    # Also log Qt crashes to console for immediate visibility
    qt_console_handler = logging.StreamHandler(sys.stdout)
    qt_console_handler.setFormatter(logging.Formatter(
        '🔍 QT_CRASH - %(levelname)s - %(message)s'
    ))
    qt_crash_logger.addHandler(qt_console_handler)
    
    # Prevent double logging by not propagating to root logger
    qt_crash_logger.propagate = False
    
    return logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger = logging.getLogger(__name__)
    logger.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    
    # Also write to a simple crash log
    with open('crash.log', 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"Crash at: {datetime.now()}\n")
        f.write(f"Exception: {exc_type.__name__}: {exc_value}\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        f.write(f"{'='*50}\n")

def run_pyqt_gui(app_core):
    """Run the application with the PyQt GUI"""
    logger = logging.getLogger(__name__)
    try:
        logger.info("Importing PyQt and PostSchedulerPyQtGUI")
        from PyQt5.QtWidgets import QApplication
        from pyqt_gui import PostSchedulerPyQtGUI

        logger.info("Creating QApplication")
        app = QApplication.instance() or QApplication(sys.argv)

        logger.info("Creating main window")
        window = PostSchedulerPyQtGUI(app_core)
        window.show()

        logger.info("Starting PyQt event loop")
        app.exec_()
        return True
    except Exception as e:
        logger.error(f"Error in PyQt GUI: {e}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Set up logging
    logger = setup_logging()
    
    # Set up global exception handler
    sys.excepthook = handle_exception
    
    logger.info("Starting VK Post Scheduler application")
    
    app_core = None
    try:        
        logger.info("Initializing application core")
        app_core = ApplicationCore()
        
        # Always run the PyQt GUI by default
        logger.info("Starting PyQt GUI")
        run_pyqt_gui(app_core)
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Missing dependency. Please install requirements: pip install -r requirements.txt")
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Show error dialog using PyQt if available, else fallback to console
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Import Error",
                f"Missing dependency: {e}\n\nPlease install requirements:\npip install -r requirements.txt"
            )
        except Exception:
            print(f"Import error: {e}")
            print("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error during startup: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Show error dialog using PyQt if available, else fallback to console
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Startup Error",
                f"An error occurred during startup:\n{e}\n\nCheck error.log for details."
            )
        except Exception:
            print(f"Startup error: {e}")
            print("Check error.log for details.")
        sys.exit(1)
    
    finally:
        # Clean shutdown
        if app_core:
            app_core.shutdown()
    
    logger.info("Application closed normally")
