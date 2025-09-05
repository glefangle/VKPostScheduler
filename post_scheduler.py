import os
import time
import threading
from queue import Queue, Empty
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from vk_config import VKConfigManager
from vk_api_handler import VKAPIHandler


@dataclass
class PhotoRotationState:
    """Manages photo rotation state for different rotation modes"""
    rotation_key: str
    last_index: int = -1
    total_photos: int = 0
    photo_paths: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.photo_paths is None:
            self.photo_paths = []
        self.total_photos = len(self.photo_paths)
    
    def get_next_photo_index(self) -> Optional[int]:
        """Get the next photo index, returns None if exhausted"""
        next_index = self.last_index + 1
        if next_index >= self.total_photos:
            return None
        return next_index
    
    def advance_to_index(self, index: int) -> bool:
        """Advance rotation to specific index"""
        if 0 <= index < self.total_photos:
            self.last_index = index
            return True
        return False
    
    def reset(self):
        """Reset rotation to beginning"""
        self.last_index = -1


class PhotoRotationManager:
    """Manages photo rotation logic and state persistence"""
    
    def __init__(self, scheduler_instance):
        self.scheduler = scheduler_instance
        self._rotation_states = {}
    
    def get_rotation_state(self, rotation_key: str, photo_paths: Optional[List[str]] = None) -> PhotoRotationState:
        """Get or create rotation state for a specific key"""
        if rotation_key not in self._rotation_states:
            # Load from persistent storage
            rotations = self.scheduler._load_rotations()
            last_index = rotations.get(rotation_key, {}).get('last_index', -1)
            
            self._rotation_states[rotation_key] = PhotoRotationState(
                rotation_key=rotation_key,
                last_index=last_index,
                photo_paths=photo_paths or []
            )
        
        # Update photo paths if provided
        if photo_paths:
            state = self._rotation_states[rotation_key]
            state.photo_paths = photo_paths
            state.total_photos = len(photo_paths)
        
        return self._rotation_states[rotation_key]
    
    def save_rotation_state(self, rotation_key: str):
        """Save rotation state to persistent storage"""
        if rotation_key in self._rotation_states:
            state = self._rotation_states[rotation_key]
            rotations = self.scheduler._load_rotations()
            rotations.setdefault(rotation_key, {})['last_index'] = state.last_index
            self.scheduler._save_rotations(rotations)
    
    def reset_rotation(self, rotation_key: str):
        """Reset rotation state for a new scheduling session"""
        if rotation_key in self._rotation_states:
            self._rotation_states[rotation_key].reset()
        else:
            # Also reset in persistent storage
            rotations = self.scheduler._load_rotations()
            if rotation_key in rotations:
                rotations[rotation_key]['last_index'] = -1
                self.scheduler._save_rotations(rotations)
    
    def get_next_photo_path(self, rotation_key: str, photo_paths: List[str]) -> Optional[str]:
        """Get next photo path for rotation"""
        state = self.get_rotation_state(rotation_key, photo_paths)
        next_index = state.get_next_photo_index()
        
        if next_index is None:
            return None
        
        if state.advance_to_index(next_index):
            return photo_paths[next_index]
        
        return None


class MediaPathResolver:
    """Resolves media paths for different posting scenarios"""
    
    def __init__(self, scheduler_instance):
        self.scheduler = scheduler_instance
        self.rotation_manager = PhotoRotationManager(scheduler_instance)
        self.allowed_exts = {'.jpg', '.jpeg', '.png', '.gif'}
    
    def resolve_media_path_for_job(self, job: dict) -> Optional[str]:
        """Resolve media path for a specific job"""
        post_data = job.get('post_data', {})
        different_posts = post_data.get('different_posts', False)
        
        if different_posts:
            return self._resolve_different_posts_media(job)
        else:
            return self._resolve_standard_media(post_data)
    
    def _resolve_different_posts_media(self, job: dict) -> Optional[str]:
        """Resolve media path for different posts mode"""
        post_data = job.get('post_data', {})
        photo_paths = post_data.get('photo_paths', [])
        
        # Check if job has pre-assigned photo index
        if 'photo_index' in job and photo_paths:
            photo_index = job['photo_index']
            if 0 <= photo_index < len(photo_paths):
                media_path = photo_paths[photo_index]
                self.scheduler._notify_status(
                    f"Using pre-assigned photo {photo_index + 1}/{len(photo_paths)}: {os.path.basename(media_path)}"
                )
                return media_path
            else:
                self.scheduler._notify_status(f"Warning: Invalid photo index {photo_index}")
        
        # Fallback to dynamic rotation
        if photo_paths:
            return self._resolve_dynamic_rotation(photo_paths)
        
        return post_data.get('photo_path')
    
    def _resolve_standard_media(self, post_data: dict) -> Optional[str]:
        """Resolve media path for standard posting mode"""
        return post_data.get('photo_path')
    
    def _resolve_dynamic_rotation(self, photo_paths: List[str]) -> Optional[str]:
        """Handle dynamic photo rotation as fallback"""
        rotation_key = 'user_selected_photos'
        next_path = self.rotation_manager.get_next_photo_path(rotation_key, photo_paths)
        
        if next_path:
            self.rotation_manager.save_rotation_state(rotation_key)
            return next_path
        
        self.scheduler._notify_status("Warning: No next media available for dynamic rotation")
        return None
    
    def resolve_directory_rotation(self, base_path: str) -> Optional[str]:
        """Handle directory-based rotation for backward compatibility"""
        if not base_path or not os.path.isdir(os.path.dirname(base_path)):
            return base_path
        
        base_dir = os.path.dirname(base_path)
        
        # Use cached directory listing
        cache_key = f"dir_listing_{base_dir}"
        if not hasattr(self.scheduler, '_dir_cache'):
            self.scheduler._dir_cache = {}
        
        if cache_key not in self.scheduler._dir_cache:
            files = sorted([
                f for f in os.listdir(base_dir) 
                if os.path.splitext(f)[1].lower() in self.allowed_exts
            ])
            self.scheduler._dir_cache[cache_key] = files
        else:
            files = self.scheduler._dir_cache[cache_key]
        
        if not files:
            return base_path
        
        # Load rotation state
        rotations = self.scheduler._load_rotations()
        last_posted = rotations.get(base_dir, {}).get('last_posted', '')
        
        try:
            current_index = files.index(last_posted)
        except ValueError:
            current_index = -1
        
        next_index = current_index + 1
        if next_index >= len(files):
            self.scheduler._notify_status("Reached end of directory files. No next media to post.")
            return None
        
        next_file = files[next_index]
        
        # Update rotation state
        rotations.setdefault(base_dir, {})['last_posted'] = next_file
        self.scheduler._save_rotations(rotations)
        
        return os.path.join(base_dir, next_file)


class PostScheduler:
    """Business logic for VK Post Scheduler - handles all non-GUI operations"""
    
    def __init__(self):
        # Worker/threading state
        self.job_queue: Queue = Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_flag = False
        self.pause_flag = False
        self.max_retries = 3
        self.jobs_file = "jobs_state.json"
        self.allowed_exts = {'.jpg', '.jpeg', '.png', '.gif'}
        self.state_lock = threading.Lock()

        # Progress counters
        self.total_jobs = 0
        self.success_count = 0
        self.failed_count = 0
        
        # Initialize post data (will be set during scheduling)
        self.current_post_data = {}
        self.sleep_time = 1
        
        # Initialize VK configuration manager
        self.vk_config = VKConfigManager()
        
        # Callbacks for GUI updates
        self.status_callback = None
        self.progress_callback = None
        self.error_callback = None
        
        # Performance optimizations: In-memory caching
        self._rotation_cache = {}
        self._rotation_cache_dirty = False
        self._jobs_cache = None
        self._jobs_cache_dirty = False
        self._job_lookup = {}  # Fast lookup by post_time
        
        # Qt crash detection and tracing - integrated with main logging
        self._gui_update_count = 0
        self._last_gui_update_time = time.time()
        self._crash_detection_enabled = True
        self._gui_callback_stack = []
        self._max_gui_updates_per_second = 5  # Reduced from 20 to prevent painter issues
        self._last_status_update = 0
        self._status_update_throttle = 0.1  # Minimum 100ms between status updates
        self._last_progress_update = 0
        self._progress_update_throttle = 0.5  # Minimum 500ms between progress updates
        
        # Batched updates to reduce GUI frequency
        self._pending_status_updates = []
        self._last_batch_update = 0
        self._batch_update_interval = 0.2  # Batch updates every 200ms
        
        # Use main application logger instead of separate files
        self.crash_logger = logging.getLogger('qt_crash_detection')
        
        # Initialize crash detection
        self._init_crash_detection()
        
        # Initialize VK API handler with crash logger
        self.vk_api = VKAPIHandler(self.vk_config, self.crash_logger)
        
        # Helper classes for better organization
        self.rotation_manager = PhotoRotationManager(self)
        # MediaUploader functionality moved to VKAPIHandler
        self.media_resolver = MediaPathResolver(self)
        
        # Load any pending jobs from disk
        self._load_jobs_into_queue()
    
    def set_callbacks(self, status_callback=None, progress_callback=None, error_callback=None):
        """Set callbacks for GUI updates"""
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.error_callback = error_callback
    
    def _init_crash_detection(self):
        """Initialize crash detection mechanisms with main application logging"""
        try:
            # Log initialization to main logger
            self.crash_logger.info("Qt crash detection system initialized")
            self._crash_log("INIT", "PostScheduler crash detection initialized")
            
        except Exception as e:
            logging.error(f"Failed to initialize crash detection: {e}")
    
    def _update_heartbeat(self, action: str):
        """Update worker activity tracking via main application logger"""
        if not self._crash_detection_enabled:
            return
        try:
            timestamp = datetime.now().isoformat()
            thread_name = threading.current_thread().name
            # Log heartbeat to main logger with structured format
            self.crash_logger.debug(f"HEARTBEAT|{thread_name}|{action}")
        except Exception as e:
            # Don't let heartbeat errors crash the app, but log them
            logging.warning(f"Heartbeat logging error: {e}")
    
    def _crash_log(self, category: str, message: str, extra_data: Optional[dict] = None):
        """Write crash detection info to main application log"""
        if not self._crash_detection_enabled:
            return
        try:
            thread_name = threading.current_thread().name
            
            log_entry = f"QT_CRASH_DETECT|{category}|{thread_name}|{message}"
            if extra_data:
                log_entry += f" | DATA: {extra_data}"
            
            # Use appropriate log level based on category
            if category in ['CRITICAL', 'PAINTER_ERROR', 'EMERGENCY_DELAY']:
                self.crash_logger.error(log_entry)
            elif category in ['GUI_ERROR', 'HIGH_RATE', 'RATE_LIMIT']:
                self.crash_logger.warning(log_entry)
            else:
                self.crash_logger.info(log_entry)
                
        except Exception as e:
            # Emergency fallback to standard logging
            logging.error(f"Crash logging error: {e} | Original: {category}: {message}")
    
    def _add_to_batch_update(self, message: str):
        """Add status message to batch for later update"""
        try:
            current_time = time.time()
            self._pending_status_updates.append((current_time, message))
            
            # Process batch if enough time has passed
            if current_time - self._last_batch_update >= self._batch_update_interval:
                self._process_batch_updates()
        except Exception as e:
            # Fallback to immediate update if batching fails
            self._crash_log("BATCH_ERROR", f"Batch update error: {e}")
            self._immediate_status_update(message)
    
    def _process_batch_updates(self):
        """Process all pending status updates in a batch"""
        try:
            if not self._pending_status_updates:
                return
            
            # Get the most recent status updates (limit to last 3)
            recent_updates = self._pending_status_updates[-3:]
            self._pending_status_updates.clear()
            self._last_batch_update = time.time()
            
            # Combine messages if there are multiple
            if len(recent_updates) == 1:
                combined_message = recent_updates[0][1]
            else:
                messages = [update[1] for update in recent_updates]
                combined_message = f"[Batch] {' | '.join(messages[-2:])}"
            
            # Send single combined update
            self._immediate_status_update(combined_message)
            
        except Exception as e:
            self._crash_log("BATCH_ERROR", f"Batch processing error: {e}")
    
    def _immediate_status_update(self, message: str):
        """Send immediate status update with all safety checks"""
        try:
            if self.status_callback:
                self.status_callback(message)
                time.sleep(0.001)  # Small delay after GUI update
        except Exception as e:
            self._crash_log("GUI_ERROR", f"Immediate status update failed: {e}")
    
    def _notify_status(self, message: str):
        """Notify GUI of status update - thread-safe with crash detection and throttling"""
        if not self._crash_detection_enabled:
            # Fallback to original behavior if crash detection disabled
            if self.status_callback:
                try:
                    self.status_callback(message)
                except Exception as e:
                    logging.error(f"Status callback error: {e}")
            return
        
        try:
            # Throttle status updates to prevent GUI overload
            current_time = time.time()
            if current_time - self._last_status_update < self._status_update_throttle:
                self._crash_log("THROTTLE", f"Status update throttled: {message[:50]}...")
                return
            
            self._last_status_update = current_time
            
            # Update heartbeat before GUI operation
            self._update_heartbeat(f"notify_status: {message[:50]}...")
            
            # Check GUI update rate
            if not self._check_gui_update_rate("status"):
                self._crash_log("RATE_LIMIT", f"Status update rate limited: {message[:100]}")
                return
            
            # Track callback stack
            self._gui_callback_stack.append(f"status: {message[:30]}")
            self._crash_log("GUI_CALL", f"Calling status callback: {message[:100]}")
            
            if self.status_callback:
                try:
                    self.status_callback(message)
                    self._crash_log("GUI_SUCCESS", "Status callback completed successfully")
                    # Add small delay after GUI update
                    time.sleep(0.001)  # 1ms delay to let Qt process
                except Exception as e:
                    self._crash_log("GUI_ERROR", f"Status callback failed: {type(e).__name__}: {e}")
                    # Check if this is a Qt painter error
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['painter', 'backing', 'endpaint', 'qpainter']):
                        self._crash_log("PAINTER_ERROR", f"Qt Painter error detected: {e}")
                    logging.error(f"Status callback error: {e}")
            
            # Remove from callback stack
            if self._gui_callback_stack:
                self._gui_callback_stack.pop()
                
        except Exception as e:
            self._crash_log("CRITICAL", f"Critical error in _notify_status: {e}")
            # Emergency logging to main logger
            logging.critical(f"CRITICAL _notify_status error: {e}")
    
    def _notify_progress(self):
        """Notify GUI to update progress - thread-safe with crash detection and throttling"""
        if not self._crash_detection_enabled:
            # Fallback to original behavior
            if self.progress_callback:
                try:
                    self.progress_callback()
                except Exception as e:
                    logging.error(f"Progress callback error: {e}")
            return
        
        try:
            # Throttle progress updates more (they're most frequent)
            current_time = time.time()
            if current_time - self._last_progress_update < self._progress_update_throttle:
                self._crash_log("THROTTLE", "Progress update throttled")
                return
            
            self._last_progress_update = current_time
            
            # Update heartbeat before GUI operation
            self._update_heartbeat("notify_progress")
            
            # Check GUI update rate (progress updates are most frequent)
            if not self._check_gui_update_rate("progress"):
                self._crash_log("RATE_LIMIT", "Progress update rate limited")
                return
            
            # Track callback stack
            self._gui_callback_stack.append("progress")
            self._crash_log("GUI_CALL", "Calling progress callback")
            
            if self.progress_callback:
                try:
                    self.progress_callback()
                    self._crash_log("GUI_SUCCESS", "Progress callback completed successfully")
                    # Add small delay after GUI update
                    time.sleep(0.002)  # 2ms delay for progress updates
                except Exception as e:
                    self._crash_log("GUI_ERROR", f"Progress callback failed: {type(e).__name__}: {e}")
                    # Check if this is a Qt painter error
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['painter', 'backing', 'endpaint', 'qpainter']):
                        self._crash_log("PAINTER_ERROR", f"Qt Painter error in progress: {e}")
                    logging.error(f"Progress callback error: {e}")
            
            # Remove from callback stack
            if self._gui_callback_stack:
                self._gui_callback_stack.pop()
                
        except Exception as e:
            self._crash_log("CRITICAL", f"Critical error in _notify_progress: {e}")
    
    def _notify_error(self, message: str, vk_error_data=None):
        """Notify GUI of error - thread-safe with crash detection"""
        if not self._crash_detection_enabled:
            # Fallback to original behavior
            if self.error_callback:
                try:
                    self.error_callback(message, vk_error_data)
                except Exception as e:
                    logging.error(f"Error callback error: {e}")
            return
        
        try:
            # Update heartbeat before GUI operation
            self._update_heartbeat(f"notify_error: {message[:50]}...")
            
            # Error notifications are less frequent, don't rate limit as aggressively
            self._crash_log("GUI_CALL", f"Calling error callback: {message[:100]}")
            
            # Track callback stack
            self._gui_callback_stack.append(f"error: {message[:30]}")
            
            if self.error_callback:
                try:
                    self.error_callback(message, vk_error_data)
                    self._crash_log("GUI_SUCCESS", "Error callback completed successfully")
                except Exception as e:
                    self._crash_log("GUI_ERROR", f"Error callback failed: {type(e).__name__}: {e}")
                    # Check if this is a Qt painter error
                    error_str = str(e).lower()
                    if any(keyword in error_str for keyword in ['painter', 'backing', 'endpaint', 'qpainter']):
                        self._crash_log("PAINTER_ERROR", f"Qt Painter error in error callback: {e}")
                    logging.error(f"Error callback error: {e}")
            
            # Remove from callback stack
            if self._gui_callback_stack:
                self._gui_callback_stack.pop()
                
        except Exception as e:
            self._crash_log("CRITICAL", f"Critical error in _notify_error: {e}")
    
    def _check_gui_update_rate(self, update_type: str) -> bool:
        """Check if GUI update rate is safe, return False if should skip update"""
        try:
            current_time = time.time()
            self._gui_update_count += 1
            
            # Check rate every second
            time_diff = current_time - self._last_gui_update_time
            if time_diff >= 1.0:
                updates_per_second = self._gui_update_count / time_diff
                
                self._crash_log("RATE_CHECK", f"GUI update rate: {updates_per_second:.1f} {update_type}/sec")
                
                # Log warning if updates are too frequent
                if updates_per_second > self._max_gui_updates_per_second:
                    self._crash_log("HIGH_RATE", f"HIGH GUI UPDATE RATE: {updates_per_second:.1f} {update_type}/sec - POTENTIAL CRASH RISK")
                    
                    # Add delay for extremely high rates
                    if updates_per_second > 10:
                        self._crash_log("EMERGENCY_DELAY", "Adding emergency delay to prevent crash")
                        time.sleep(0.1)  # 100ms emergency delay
                
                # Reset counters
                self._gui_update_count = 0
                self._last_gui_update_time = current_time
                return True
            
            # Allow updates within reasonable limits (more conservative)
            return self._gui_update_count <= (self._max_gui_updates_per_second * time_diff)
            
        except Exception as e:
            self._crash_log("CRITICAL", f"Error in rate check: {e}")
            return True  # Allow update if rate check fails
    
    def get_vk_config(self) -> VKConfigManager:
        """Get VK configuration manager"""
        return self.vk_config
    
    def refresh_vk_selections(self) -> tuple:
        """Refresh VK selections and return current state"""
        try:
            token_names = self.vk_config.get_token_names()
            current_token, current_group = self.vk_config.get_selection()
            
            # Auto-select first token if available
            if token_names and not current_token:
                current_token = token_names[0]
                self.vk_config.set_selection(current_token, None)
                self._notify_status(f"Auto-selected first available token: {current_token}")
            
            # Get group names for current token
            group_names = []
            if current_token and current_token in token_names:
                group_names = self.vk_config.get_group_names(current_token)
                
                # Auto-select first group if available
                if group_names and not current_group:
                    current_group = group_names[0]
                    self.vk_config.set_selection(current_token, current_group)
                    self._notify_status(f"Auto-selected first available group: {current_group}")
            
            return token_names, group_names, current_token, current_group
            
        except Exception as e:
            self._notify_status(f"Error refreshing VK selections: {e}")
            logging.error(f"Error in refresh_vk_selections: {e}")
            return [], [], None, None
    
    def set_token_selection(self, token_name: str):
        """Set token selection"""
        try:
            self.vk_config.set_selection(token_name, None)
            self._notify_status(f"Selected token: {token_name}")
            return True
        except Exception as e:
            self._notify_status(f"Error selecting token: {e}")
            return False
    
    def set_group_selection(self, token_name: str, group_name: str):
        """Set group selection"""
        try:
            self.vk_config.set_selection(token_name, group_name)
            group_id = self.vk_config.get_selected_group_id()
            self._notify_status(f"Selected group: {group_name} (ID: {group_id})")
            return True
        except Exception as e:
            self._notify_status(f"Error selecting group: {e}")
            return False
    
    def get_group_schedule(self, token_name: str, group_name: str) -> List[str]:
        """Get schedule for a specific group"""
        try:
            return self.vk_config.get_group_schedule(token_name, group_name)
        except Exception as e:
            self._notify_status(f"Error getting group schedule: {e}")
            return []
    
    def save_group_schedule(self, token_name: str, group_name: str, schedule: List[str]):
        """Save schedule for a specific group"""
        try:
            self.vk_config.set_group_schedule(token_name, group_name, schedule)
            self._notify_status(f"Saved schedule for {group_name}: {len(schedule)} times")
            return True
        except Exception as e:
            self._notify_status(f"Error saving group schedule: {e}")
            return False
    
    def get_group_default_text(self, token_name: str, group_name: str) -> str:
        """Get default text for a specific group"""
        try:
            return self.vk_config.get_group_default_text(token_name, group_name)
        except Exception as e:
            self._notify_status(f"Error getting group default text: {e}")
            return ""
    
    def save_group_default_text(self, token_name: str, group_name: str, default_text: str):
        """Save default text for a specific group"""
        try:
            self.vk_config.set_group_default_text(token_name, group_name, default_text)
            self._notify_status(f"Saved default text for {group_name}")
            return True
        except Exception as e:
            self._notify_status(f"Error saving group default text: {e}")
            return False
    
    def add_token(self, token_name: str, token_value: str) -> bool:
        """Add new token"""
        try:
            from vk_config import VKToken
            new_token = VKToken(name=token_name, token=token_value, groups=[])
            self.vk_config.add_token(new_token)
            self._notify_status("Token added successfully")
            return True
        except Exception as e:
            self._notify_status(f"Error adding token: {e}")
            return False
    
    def edit_token(self, token_name: str, new_name: str, new_value: str) -> bool:
        """Edit existing token"""
        try:
            old_token = self.vk_config.get_token(token_name)
            if old_token:
                # Create new token with updated values
                from vk_config import VKToken
                new_token = VKToken(name=new_name, token=new_value, groups=old_token.groups)
                # Use the config manager's update method
                self.vk_config.update_token(token_name, new_token)
                self._notify_status(f"Token '{token_name}' updated successfully")
                return True
            return False
        except Exception as e:
            self._notify_status(f"Error editing token: {e}")
            return False
    
    def delete_token(self, token_name: str) -> bool:
        """Delete token"""
        try:
            self.vk_config.remove_token(token_name)
            self._notify_status(f"Token '{token_name}' deleted successfully")
            return True
        except Exception as e:
            self._notify_status(f"Error deleting token: {e}")
            return False
    
    def add_group(self, token_name: str, group_name: str, group_id: str) -> bool:
        """Add new group to token"""
        try:
            token = self.vk_config.get_token(token_name)
            if token:
                from vk_config import VKGroup
                new_group = VKGroup(name=group_name, group_id=group_id)
                token.add_group(new_group)
                self.vk_config.save_config()
                self._notify_status("Group added successfully")
                return True
            return False
        except Exception as e:
            self._notify_status(f"Error adding group: {e}")
            return False
    
    def edit_group(self, token_name: str, group_name: str, new_name: str, new_id: str) -> bool:
        """Edit existing group"""
        try:
            token = self.vk_config.get_token(token_name)
            if token:
                group = token.get_group(group_name)
                if group:
                    group.name = new_name
                    group.group_id = new_id
                    self.vk_config.save_config()
                    self._notify_status(f"Group '{group_name}' updated successfully")
                    return True
            return False
        except Exception as e:
            self._notify_status(f"Error editing group: {e}")
            return False
    
    def delete_group(self, token_name: str, group_name: str) -> bool:
        """Delete group"""
        try:
            token = self.vk_config.get_token(token_name)
            if token:
                token.remove_group(group_name)
                self.vk_config.save_config()
                self._notify_status(f"Group '{group_name}' deleted successfully")
                return True
            return False
        except Exception as e:
            self._notify_status(f"Error deleting group: {e}")
            return False
    
    def validate_post_data(self, text: str, photo_path: str, start_date: str, end_date: str, times: List[str]) -> tuple[bool, str]:
        """Validate post data before scheduling"""
        # Get current selection to check validity
        current_token, current_group = self.vk_config.get_selection()
        
        # Check if we have valid token and group selected
        if not current_token:
            return False, "Please select a VK token before scheduling posts."
        
        if not current_group:
            return False, "Please select a VK group before scheduling posts."
        
        # Validate that the token still exists and has the selected group
        token = self.vk_config.get_token(current_token)
        if not token:
            return False, f"Selected token '{current_token}' no longer exists. Please reselect a token."
        
        group = token.get_group(current_group)
        if not group:
            return False, f"Selected group '{current_group}' no longer exists in token '{current_token}'. Please reselect a group."
        
        # Check token value
        if not token.token or not token.token.strip():
            return False, f"Token '{current_token}' has no valid token value. Please edit the token."
        
        # Check group ID
        if not group.group_id or not str(group.group_id).strip():
            return False, f"Group '{current_group}' has no valid group ID. Please edit the group."
        
        if not start_date or not end_date:
            return False, "Please select both start and end dates"
        
        if not times:
            return False, "Please select at least one time"
        
        # VK allows posts with either text, photo, or both (but not neither)
        if not text.strip() and not photo_path:
            return False, "Please provide either post text or select a photo/GIF to post"
        
        return True, ""
    
    def schedule_posts(self, text: str, photo_path: str, gif_name: str, start_date: str, 
                      end_date: str, times: List[str], sleep_time: int, different_posts: bool, 
                      photo_paths: Optional[List[str]] = None) -> bool:
        """Schedule all posts for the given date range with organized rotation logic"""
        try:
            # Clear existing jobs before scheduling new ones
            self._clear_all_jobs()
            self._notify_status("Cleared existing jobs before scheduling new ones")
            
            # Reset rotation state for fresh photo rotation when different_posts is enabled
            self._reset_rotation_state_for_new_session(different_posts, photo_paths)
            
            # Store post data for worker
            self._prepare_post_data(text, photo_path, gif_name, different_posts, photo_paths)
            self.sleep_time = sleep_time
            
            # Generate posts for date range
            success = self._schedule_posts_for_date_range(start_date, end_date, times)
            
            if success:
                self._start_worker_if_needed()
                self._notify_status("All posts have been enqueued. They will be posted in the background.")
                self._notify_progress()
            
            return success
            
        except Exception as e:
            self._notify_error(f"Error scheduling posts: {e}")
            return False
    
    def _reset_rotation_state_for_new_session(self, different_posts: bool, photo_paths: Optional[List[str]]):
        """Reset rotation state for a fresh scheduling session"""
        if different_posts and photo_paths:
            rotation_key = 'user_selected_photos'
            self.rotation_manager.reset_rotation(rotation_key)
            self._notify_status(f"Reset photo rotation state for {len(photo_paths)} selected photos")
    
    def _prepare_post_data(self, text: str, photo_path: str, gif_name: str, 
                          different_posts: bool, photo_paths: Optional[List[str]]):
        """Prepare post data with clean structure"""
        self.current_post_data = {
            'text': text,
            'photo_path': photo_path,
            'photo_paths': photo_paths or [],
            'gif_name': gif_name,
            'different_posts': different_posts
        }
    
    def _schedule_posts_for_date_range(self, start_date: str, end_date: str, times: List[str]) -> bool:
        """Schedule posts across the entire date range"""
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        scheduled_dates = 0
        total_dates = (end_dt - start_dt).days + 1
        
        current_dt = start_dt
        while current_dt <= end_dt:
            current_date = current_dt.strftime("%Y-%m-%d")
            
            # Schedule posts for this date
            continue_scheduling = self._schedule_posts_for_single_date(current_date, times)
            scheduled_dates += 1
            
            if not continue_scheduling:
                # Photos exhausted, stop scheduling
                remaining_dates = total_dates - scheduled_dates
                self._notify_status(f"Photo exhaustion: Stopped scheduling. {remaining_dates} dates not processed.")
                if scheduled_dates > 0:
                    self._notify_status(f"Successfully scheduled posts for {scheduled_dates}/{total_dates} dates")
                break
            
            current_dt += timedelta(days=1)
        
        return True
    
    def _schedule_posts_for_single_date(self, date: str, times: List[str]) -> bool:
        """Schedule posts for a specific date with rotation logic
        Returns True if scheduling completed successfully, False if stopped due to photo exhaustion
        """
        # Get current VK selection
        current_token, current_group = self.vk_config.get_selection()
        
        # Validate that we have required selections
        if not current_token or not current_group:
            self._notify_status("Error: Missing token or group selection")
            return False
        
        # Check if we're using different posts mode
        different_posts = self.current_post_data.get('different_posts', False)
        photo_paths = self.current_post_data.get('photo_paths', [])
        
        if different_posts and photo_paths:
            return self._schedule_different_posts_for_date(date, times, current_token, current_group, photo_paths)
        else:
            return self._schedule_standard_posts_for_date(date, times, current_token, current_group)
    
    def _schedule_different_posts_for_date(self, date: str, times: List[str], 
                                          current_token: str, current_group: str, 
                                          photo_paths: List[str]) -> bool:
        """Schedule posts with different photos for each time slot"""
        rotation_key = 'user_selected_photos'
        rotation_state = self.rotation_manager.get_rotation_state(rotation_key, photo_paths)
        
        self._notify_status(f"Scheduling {len(times)} posts for {date} with photo rotation")
        
        jobs_to_schedule = []
        
        for i, time_str in enumerate(times):
            full_time = f"{date} {time_str}"
            
            # Calculate photo index for this job
            job_photo_index = rotation_state.last_index + 1 + i
            
            # Check if we've run out of photos
            if job_photo_index >= len(photo_paths):
                self._notify_status(f"Stopping at {full_time}: No more photos available ({job_photo_index + 1} > {len(photo_paths)})")
                self._notify_status(f"Scheduled {i} posts for {date} before running out of photos")
                
                # Save any jobs we've created so far
                if jobs_to_schedule:
                    self._save_jobs_batch_and_update_rotation(jobs_to_schedule, rotation_key, rotation_state.last_index + i)
                
                return False  # Signal that we should stop scheduling
            
            # Create job with pre-assigned photo index
            job = self._create_job(full_time, current_token, current_group, photo_index=job_photo_index)
            jobs_to_schedule.append(job)
        
        # Save all jobs and update rotation state
        if jobs_to_schedule:
            final_rotation_index = rotation_state.last_index + len(jobs_to_schedule)
            self._save_jobs_batch_and_update_rotation(jobs_to_schedule, rotation_key, final_rotation_index)
            self._notify_status(f"Batch scheduled {len(jobs_to_schedule)} posts for {date}")
        
        return True
    
    def _schedule_standard_posts_for_date(self, date: str, times: List[str], 
                                         current_token: str, current_group: str) -> bool:
        """Schedule posts with standard (non-rotating) photos"""
        jobs_to_schedule = []
        
        for time_str in times:
            full_time = f"{date} {time_str}"
            job = self._create_job(full_time, current_token, current_group)
            jobs_to_schedule.append(job)
            self._notify_status(f"Prepared post at {full_time} for group {current_group}")
        
        # Save all jobs in batch
        if jobs_to_schedule:
            self._persist_jobs_batch(jobs_to_schedule)
            self._add_jobs_to_queue(jobs_to_schedule)
            self._notify_status(f"Batch scheduled {len(jobs_to_schedule)} jobs for {date}")
        
        return True
    
    def _create_job(self, post_time: str, token_name: str, group_name: str, photo_index: Optional[int] = None) -> dict:
        """Create a job dictionary with consistent structure"""
        job = {
            "post_time": post_time,
            "attempt": 0,
            "token_name": token_name,
            "group_name": group_name,
            "post_data": self.current_post_data.copy(),
            "sleep_time": self.sleep_time
        }
        
        if photo_index is not None:
            job["photo_index"] = photo_index
        
        return job
    
    def _save_jobs_batch_and_update_rotation(self, jobs: List[dict], rotation_key: str, final_index: int):
        """Save jobs and update rotation state efficiently"""
        # Save jobs
        self._persist_jobs_batch(jobs)
        self._add_jobs_to_queue(jobs)
        
        # Update rotation state
        rotation_state = self.rotation_manager.get_rotation_state(rotation_key)
        rotation_state.advance_to_index(final_index)
        self.rotation_manager.save_rotation_state(rotation_key)
    
    def _add_jobs_to_queue(self, jobs: List[dict]):
        """Add multiple jobs to the processing queue"""
        for job in jobs:
            self.job_queue.put(job)
            self.total_jobs += 1
        self._notify_progress()
    
    def perform_post(self, post_time: str) -> bool:
        self._log_posting_debug_info(post_time)
        
        # Initialize VK API
        api = self._initialize_vk_api()
        group_id = self._get_group_id_as_int()
        owner_id = -group_id
        
        # Resolve media path for this job
        media_path = self._resolve_media_path_for_current_job()
        
        # Upload media if present
        attachment = self._upload_media_if_present(api, media_path, group_id)
        
        # Prepare and validate post content
        message = self._prepare_post_message()
        self._validate_post_content(message, attachment)
        
        # Execute the post
        post_timestamp = self._get_post_timestamp(post_time)
        self._execute_vk_post(api, owner_id, message, attachment, post_timestamp)
        
        return True
    
    def _log_posting_debug_info(self, post_time: str):
        """Log debug information for posting - reduced verbosity"""
        different_posts_enabled = self.current_post_data.get('different_posts', False)
        photo_paths = self.current_post_data.get('photo_paths', [])
        
        self._notify_status(f"Posting at {post_time}...")
        
        if different_posts_enabled and photo_paths:
            self._notify_status(f"Different posts mode: {len(photo_paths)} photos available")
            
            if hasattr(self, '_current_job'):
                job_photo_index = self._current_job.get('photo_index')
                if job_photo_index is not None:
                    self._notify_status(f"Using photo {job_photo_index + 1}/{len(photo_paths)}")
    
    def _initialize_vk_api(self):
        """Initialize VK API session using VK API handler"""
        return self.vk_api.initialize_api_session()
    
    def _get_group_id_as_int(self) -> int:
        """Get group ID as integer for VK operations using VK API handler"""
        return self.vk_api.get_current_group_id()
    
    def _resolve_media_path_for_current_job(self) -> Optional[str]:
        """Resolve media path using the current job context"""
        if hasattr(self, '_current_job'):
            self._notify_status(f"Resolving media path for job: {self._current_job.get('post_time', 'unknown')}")
            media_path = self.media_resolver.resolve_media_path_for_job(self._current_job)
        else:
            # Fallback to standard resolution
            self._notify_status("No current job context - using standard media resolution")
            media_path = self.media_resolver._resolve_standard_media(self.current_post_data)
        
        if media_path:
            self._notify_status(f"Using media: {os.path.basename(media_path)}")
        else:
            self._notify_status("No media path resolved - will be text-only post")
        
        return media_path
    
    def _upload_media_if_present(self, api, media_path: Optional[str], group_id: int) -> str:
        """Upload media if present and return attachment string"""
        if not media_path:
            self._notify_status("DEBUG: No media path provided")
            return ""
        
        self._notify_status(f"DEBUG: Starting media upload for: {media_path}")
        
        # Check if file exists
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")
        
        _, ext = os.path.splitext(media_path)
        ext = ext.lower()
        
        attachment = ""
        
        if ext in ('.jpg', '.jpeg', '.png'):
            self._notify_status(f"DEBUG: Uploading photo via VK API handler")
            attachment = self.vk_api.upload_photo_to_group(api, media_path, group_id)
        elif ext == '.gif':
            gif_name = self.current_post_data.get('gif_name') or os.path.basename(media_path)
            self._notify_status(f"DEBUG: Uploading GIF via VK API handler")
            attachment = self.vk_api.upload_gif_to_group(api, media_path, group_id, gif_name)
        else:
            raise ValueError("Invalid file extension. Only JPG, JPEG, PNG, and GIF files are allowed.")
        
        self._notify_status(f"DEBUG: VK API handler returned attachment: '{attachment}'")
        self._notify_status(f"DEBUG: Attachment type: {type(attachment)}, length: {len(attachment) if attachment else 0}")
        
        return attachment
    
    def _prepare_post_message(self) -> str:
        """Prepare and clean post message text"""
        text = self.current_post_data.get('text', '') or ''
        return text.strip() if text else ''
    
    def _validate_post_content(self, message: str, attachment: str):
        """Validate that post has required content"""
        if not message and not attachment:
            raise ValueError("VK API requires either text content or media attachment for posting")
    
    def _get_post_timestamp(self, post_time: str) -> str:
        """Get and validate post timestamp"""
        dt = datetime.strptime(post_time, "%Y-%m-%d %H:%M")
        if dt <= datetime.now():
            raise ValueError("Publish time must be in the future.")
        return str(int(dt.timestamp()))
    
    def _execute_vk_post(self, api, owner_id: int, message: str, attachment: str, post_timestamp: str):
        """Execute the actual VK post using VK API handler"""
        group_id = abs(owner_id)
        self._notify_status(f"Posting to VK group {group_id}...")
        
        # Enhanced debugging for attachment string
        self._notify_status(f"DEBUG: Attachment string received: '{attachment}'")
        self._notify_status(f"DEBUG: Attachment type: {type(attachment)}")
        self._notify_status(f"DEBUG: Attachment length: {len(attachment) if attachment else 0}")
        
        # Use VK API handler for posting
        result = self.vk_api.post_to_wall(
            api=api,
            owner_id=owner_id,
            message=message if message else None,
            attachment=attachment if attachment else None,
            post_timestamp=post_timestamp
        )
        
        if result and 'post_id' in result:
            self._notify_status(f"Post created successfully: post_id={result['post_id']}")
        else:
            self._notify_status("Post created successfully (no post_id returned)")
    
    def _get_vk_token(self) -> str:
        """Get the currently selected VK token value"""
        token = self.vk_config.get_selected_token_value()
        if not token:
            raise ValueError("No VK token selected. Please configure tokens.")
        return token

    def _get_group_id(self) -> str:
        """Get the currently selected group ID"""
        group_id = self.vk_config.get_selected_group_id()
        if not group_id:
            raise ValueError("No VK group selected. Please configure groups.")
        return group_id
    
    def _get_next_media_path(self) -> Optional[str]:
        """Get next media path for rotation - simplified to use MediaPathResolver"""
        # Check for user-selected photos first
        photo_paths = self.current_post_data.get('photo_paths', [])
        if photo_paths:
            rotation_key = 'user_selected_photos'
            return self.rotation_manager.get_next_photo_path(rotation_key, photo_paths)
        
        # Fallback to directory-based rotation
        photo_path = self.current_post_data.get('photo_path')
        if photo_path:
            return self.media_resolver.resolve_directory_rotation(photo_path)
        
        return None
    
    def _load_rotations(self) -> dict:
        """Load rotation state with caching for performance"""
        # Return cached data if available and not dirty
        if self._rotation_cache and not self._rotation_cache_dirty:
            return self._rotation_cache.copy()
            
        if not os.path.exists(self.jobs_file):
            self._rotation_cache = {}
            self._rotation_cache_dirty = False
            return {}
            
        try:
            with open(self.jobs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rotations = data.get('rotations', {})
            
            # Cache the loaded data
            self._rotation_cache = rotations.copy()
            self._rotation_cache_dirty = False
            
            return rotations
        except Exception:
            self._rotation_cache = {}
            self._rotation_cache_dirty = False
            return {}

    def _save_rotations(self, rotations: dict):
        """Save rotation state with optimized caching"""
        try:
            # Update cache first for immediate access
            self._rotation_cache = rotations.copy()
            self._rotation_cache_dirty = False
            
            # Use cached jobs if available, otherwise load from disk
            if self._jobs_cache is not None and not self._jobs_cache_dirty:
                jobs = self._jobs_cache
            else:
                jobs = self._load_jobs_direct()
            
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump({'jobs': jobs, 'rotations': rotations}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._notify_status(f"Failed to save rotations: {e}")
            # Mark cache as dirty on save failure
            self._rotation_cache_dirty = True
    
    def _restore_job_context(self, job: dict):
        """Restore context for a specific job (token, group, post data)"""
        try:
            # Set the VK selection to match the job
            token_name = job.get('token_name')
            group_name = job.get('group_name')
            
            if token_name and group_name:
                self.vk_config.set_selection(token_name, group_name)
                self._notify_status(f"Restored context: {token_name} -> {group_name}")
            
            # Restore post data
            if 'post_data' in job:
                self.current_post_data = job['post_data'].copy()
            
            # Restore sleep time
            if 'sleep_time' in job:
                self.sleep_time = job['sleep_time']
                
        except Exception as e:
            self._notify_status(f"Warning: Failed to restore job context: {e}")
    
    def _worker_loop(self):
        """Main worker loop for processing posts with crash detection"""
        self._crash_log("WORKER", "Worker loop started")
        self._update_heartbeat("Worker loop started")
        
        job_count = 0
        consecutive_errors = 0
        
        try:
            while not self.stop_flag:
                if self.pause_flag:
                    self._update_heartbeat("Worker paused")
                    time.sleep(0.5)
                    continue
                    
                try:
                    self._update_heartbeat("Getting job from queue")
                    job = self.job_queue.get(timeout=0.5)
                except Empty:
                    self._update_heartbeat("Queue empty, continuing")
                    continue
                    
                if job is None:
                    self._crash_log("WORKER", "Received None job, breaking")
                    break
                    
                job_count += 1
                post_time = job["post_time"]
                attempt = int(job.get("attempt", 0))
                task_done_called = False
                
                self._crash_log("JOB_START", f"Processing job #{job_count}: {post_time}", {
                    'job_count': job_count,
                    'post_time': post_time,
                    'attempt': attempt,
                    'consecutive_errors': consecutive_errors
                })
                self._update_heartbeat(f"Processing job {job_count}: {post_time}")
                
                try:
                    if self.stop_flag:
                        self._crash_log("WORKER", "Stop flag detected, putting job back")
                        self.job_queue.put(job)
                        self.job_queue.task_done()
                        task_done_called = True
                        continue
                        
                    if self.pause_flag:
                        self._crash_log("WORKER", "Pause flag detected, putting job back")
                        self.job_queue.put(job)
                        self.job_queue.task_done()
                        task_done_called = True
                        continue
                    
                    # Restore job-specific context
                    self._crash_log("JOB_CONTEXT", "Restoring job context")
                    self._restore_job_context(job)
                    
                    # Store current job for access by perform_post
                    self._current_job = job
                    
                    self._crash_log("JOB_PERFORM", f"About to perform_post for {post_time}")
                    self._update_heartbeat(f"Performing post {post_time}")
                        
                    self.perform_post(post_time)
                    
                    self._crash_log("JOB_SUCCESS", f"Successfully performed post for {post_time}")
                    
                    self._remove_job_from_state(job)
                    self.success_count += 1
                    consecutive_errors = 0  # Reset error counter on success
                    
                    self._crash_log("GUI_NOTIFY_START", f"About to notify GUI of success for {post_time}")
                    self._update_heartbeat(f"Notifying GUI success {post_time}")
                    
                    # Use batched updates during heavy posting to reduce GUI frequency
                    success_message = f"Posted successfully for {post_time} to group {job.get('group_name', 'Unknown')}"
                    self._add_to_batch_update(success_message)
                    
                    # Only update progress every few jobs to reduce GUI load
                    if job_count % 3 == 0:  # Update progress every 3rd job
                        self._notify_progress()
                    
                    self._crash_log("GUI_NOTIFY_END", f"GUI notifications completed for {post_time}")
                    
                except Exception as e:
                    consecutive_errors += 1
                    import traceback
                    
                    self._crash_log("JOB_ERROR", f"Exception in job processing for {post_time}: {type(e).__name__}: {e}", {
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'consecutive_errors': consecutive_errors,
                        'traceback': traceback.format_exc()[:1000]  # Limit traceback length
                    })
                    
                    # Get detailed error information
                    error_type = type(e).__name__
                    error_message = str(e)
                    error_traceback = traceback.format_exc()
                    
                    # Create detailed error message
                    formatted_msg = f"{error_type}: {error_message}"
                    detailed_msg = f"Exception Type: {error_type}\nError: {error_message}\nPost Time: {post_time}\nGroup: {job.get('group_name', 'Unknown')}"
    
                    # Log full traceback for debugging
                    logging.error(f"Post error for {post_time}: {formatted_msg}")
                    logging.error(f"Full traceback: {error_traceback}")
                    
                    # If too many consecutive errors, enable more aggressive logging
                    if consecutive_errors > 3:
                        self._crash_log("HIGH_ERROR_RATE", f"High error rate detected: {consecutive_errors} consecutive errors")
                        # Add delay to prevent error spam, but check for resume
                        if not self.pause_flag:
                            time.sleep(1)
                    
                    self._crash_log("ERROR_NOTIFY_START", f"About to send error notifications for {post_time}")
                    
                    # Log detailed error to status
                    self._notify_status(f"❌ Error occurred: {formatted_msg}")
                    self._notify_status(f"📝 Error details: {detailed_msg}")
                    
                    # Wait 1 minute after unsuccessful post as requested
                    self._notify_status("⏱️ Waiting 1 minute after unsuccessful post...")
                    
                    # Wait 1 minute (60 seconds) but check for stop/pause flags every second
                    for i in range(60):
                        if self.stop_flag:
                            self._crash_log("WORKER", "Stop requested during error wait period")
                            self._notify_status("Stop requested during error wait period")
                            # Put the job back for next app start if we're stopping gracefully
                            self.job_queue.put(job)
                            self.job_queue.task_done()
                            task_done_called = True
                            return
                        
                        # Check if queue was resumed during error wait
                        if not self.pause_flag:
                            self._crash_log("WORKER", "Queue resumed during error wait period")
                            self._notify_status("Queue resumed - cancelling error wait")
                            break
                            
                        time.sleep(1)
                    
                    self._notify_status("✅ 1-minute wait completed")
                    
                    # Pause the queue
                    self.pause_flag = True
                    self._notify_status("⏸️ Queue paused due to error - waiting for user acknowledgment")
                    
                    # Create comprehensive error message for dialog
                    full_error_msg = f"Posting Error Details:\n\n{detailed_msg}\n\n"
                    #Full Error: {formatted_msg}\n\nFull Exception Traceback:\n{error_traceback}"
                    
                    # Prepare VK error data with complete information
                    vk_error_data = {
                        'error_type': error_type,
                        'error_message': error_message,
                        'post_time': post_time,
                        'group_name': job.get('group_name', 'Unknown'),
                        'attempt': attempt,
                        'traceback': error_traceback,
                        'full_error': formatted_msg
                    }
                    
                    self._crash_log("ERROR_DIALOG_START", f"About to show error dialog for {post_time}")
                    
                    # Notify error for GUI and any additional observers
                    self._notify_error(full_error_msg, vk_error_data)
                    
                    self._crash_log("ERROR_DIALOG_END", f"Error dialog processing completed for {post_time}")
                    
                    if attempt < self.max_retries and not self.stop_flag:
                        # Retry wait times: 1st attempt -> 1min, 2nd attempt -> 2min, 3rd attempt -> 3min
                        backoff = (attempt + 1) * 60  # Convert minutes to seconds
                        retry_msg = f"Retrying {post_time} in {backoff//60}min (attempt {attempt+1}/{self.max_retries})"
                        self._notify_status(retry_msg)
                        
                        # Wait for pause to be lifted
                        while self.pause_flag and not self.stop_flag:
                            time.sleep(0.1)
                        
                        if not self.stop_flag:
                            # Wait for backoff period but check for pause/resume every second
                            for i in range(backoff):
                                if self.stop_flag:
                                    self._crash_log("WORKER", "Stop requested during retry wait period")
                                    self._notify_status("Stop requested during retry wait period")
                                    # Put the job back for next app start if we're stopping gracefully
                                    self.job_queue.put(job)
                                    self.job_queue.task_done()
                                    task_done_called = True
                                    return
                                if not self.pause_flag:
                                    time.sleep(1)
                                else:
                                    # Queue is paused, wait for resume
                                    while self.pause_flag and not self.stop_flag:
                                        time.sleep(0.1)
                            
                            if not self.stop_flag:
                                job["attempt"] = attempt + 1
                                self.job_queue.put(job)
                    else:
                        # Exhausted retries - wait 1 minute before marking as failed
                        if not self.stop_flag:
                            self._notify_status("⏱️ Waiting 1 minute before marking post as failed...")
                            
                            # Wait 1 minute but check for stop flag
                            for i in range(60):
                                if self.stop_flag:
                                    self._notify_status("Stop requested during failure wait period")
                                    # Put the job back for next app start
                                    self.job_queue.put(job)
                                    self.job_queue.task_done()
                                    task_done_called = True
                                    return
                                time.sleep(1)
                            
                            self._notify_status("✅ 1-minute wait before failure completed")
                        
                        # Now mark as failed
                        fail_msg = f"Failed to post {post_time} after {self.max_retries} attempts"
                        self._notify_status(fail_msg)
                        self._notify_error(fail_msg, vk_error_data)
                        self._remove_job_from_state(job)
                        self.failed_count += 1
                        self._notify_progress()
                        
                        # Wait for pause to be lifted
                        while self.pause_flag and not self.stop_flag:
                            time.sleep(0.1)
                finally:
                    self._crash_log("JOB_CLEANUP", f"Job cleanup for {post_time}")
                    self._update_heartbeat(f"Job cleanup {post_time}")
                    
                    if not self.pause_flag and not self.stop_flag:
                        time.sleep(max(0, self.sleep_time))
                    # Only call task_done() if it hasn't been called already
                    if not task_done_called:
                        self.job_queue.task_done()
                        
                self._crash_log("JOB_COMPLETE", f"Job {job_count} processing complete")
                
        except Exception as critical_error:
            import traceback
            self._crash_log("CRITICAL_WORKER_ERROR", f"Critical worker loop error: {critical_error}", {
                'error_type': type(critical_error).__name__,
                'traceback': traceback.format_exc()
            })
            # Log to main logger as well
            logging.critical(f"CRITICAL WORKER CRASH: {critical_error}")
            logging.critical(f"Traceback: {traceback.format_exc()}")
        finally:
            self._crash_log("WORKER", "Worker loop ending")
            self._update_heartbeat("Worker loop ended")
    
    def get_progress_stats(self) -> Dict[str, int]:
        """Get current progress statistics"""
        pending = self._pending_jobs_count()
        completed = self.success_count + self.failed_count
        total = max(self.total_jobs, completed + pending)
        
        return {
            'total': total,
            'completed': completed,
            'success': self.success_count,
            'failed': self.failed_count,
            'pending': pending
        }
    
    def resume_worker(self):
        """Resume worker after error"""
        self.pause_flag = False
        self._notify_status("▶️ Queue resumed - continuing with next posts")
    
    # Job persistence methods
    def _load_jobs(self) -> list:
        """Load jobs with caching for performance"""
        # Return cached data if available and not dirty
        if self._jobs_cache is not None and not self._jobs_cache_dirty:
            return self._jobs_cache.copy()
            
        return self._load_jobs_direct()
    
    def _load_jobs_direct(self) -> list:
        """Load jobs directly from disk without caching"""
        if not os.path.exists(self.jobs_file):
            jobs = []
        else:
            try:
                with open(self.jobs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                jobs = data.get('jobs', [])
            except Exception:
                jobs = []
        
        # Update cache
        self._jobs_cache = jobs.copy()
        self._jobs_cache_dirty = False
        
        # Update lookup index for fast access
        self._job_lookup = {job.get('post_time'): i for i, job in enumerate(jobs)}
        
        return jobs

    def _save_jobs(self, jobs: list):
        """Save jobs with caching optimization"""
        try:
            # Update cache immediately
            self._jobs_cache = jobs.copy()
            self._jobs_cache_dirty = False
            
            # Update lookup index
            self._job_lookup = {job.get('post_time'): i for i, job in enumerate(jobs)}
            
            # Save to disk with current rotation data
            rotations = self._rotation_cache if self._rotation_cache else {}
            
            with open(self.jobs_file, 'w', encoding='utf-8') as f:
                json.dump({'jobs': jobs, 'rotations': rotations}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._notify_status(f"Failed to save jobs: {e}")
            # Mark cache as dirty on save failure
            self._jobs_cache_dirty = True

    def _persist_job(self, job: dict):
        """Persist single job - optimized for individual operations"""
        with self.state_lock:
            jobs = self._load_jobs()
            jobs.append(job)
            
            # Update cache without full disk write for better performance
            if self._jobs_cache is not None:
                self._jobs_cache.append(job)
                post_time = job.get('post_time')
                if post_time:
                    self._job_lookup[post_time] = len(self._jobs_cache) - 1
            
            self._save_jobs(jobs)
    
    def _persist_jobs_batch(self, jobs_to_add: List[dict]):
        """Persist multiple jobs in a single operation for better performance"""
        if not jobs_to_add:
            return
            
        with self.state_lock:
            jobs = self._load_jobs()
            jobs.extend(jobs_to_add)
            
            # Update cache efficiently
            if self._jobs_cache is not None:
                start_index = len(self._jobs_cache)
                self._jobs_cache.extend(jobs_to_add)
                
                # Update lookup index for new jobs
                for i, job in enumerate(jobs_to_add):
                    post_time = job.get('post_time')
                    if post_time:
                        self._job_lookup[post_time] = start_index + i
            
            self._save_jobs(jobs)

    def _remove_job_from_state(self, job: dict):
        """Remove job from state"""
        with self.state_lock:
            post_time = job.get('post_time')
            if not post_time:
                return
                
            # Use fast lookup if available
            if post_time in self._job_lookup and self._jobs_cache is not None:
                index = self._job_lookup[post_time]
                if 0 <= index < len(self._jobs_cache):
                    # Remove from cache
                    self._jobs_cache.pop(index)
                    
                    # Update lookup indices (shift down indices after removed item)
                    new_lookup = {}
                    for job_time, idx in self._job_lookup.items():
                        if job_time == post_time:
                            continue  # Skip the removed job
                        elif idx > index:
                            new_lookup[job_time] = idx - 1  # Shift down
                        else:
                            new_lookup[job_time] = idx  # Keep same index
                    
                    self._job_lookup = new_lookup
                    
                    # Save the updated jobs
                    self._save_jobs(self._jobs_cache)
                    return
            
            # Fallback to original method if cache lookup fails
            jobs = self._load_jobs_direct()  # Load fresh from disk
            for i, j in enumerate(jobs):
                if j.get('post_time') == post_time:
                    jobs.pop(i)
                    break
            self._save_jobs(jobs)

    def _load_jobs_into_queue(self):
        """Load jobs into queue with cache optimization"""
        with self.state_lock:
            jobs = self._load_jobs()
        for job in jobs:
            job.setdefault('attempt', 0)
            self.job_queue.put(job)
        if jobs:
            self.total_jobs += len(jobs)
    
    def invalidate_cache(self):
        """Invalidate all caches - useful for debugging or external file changes"""
        with self.state_lock:
            self._rotation_cache = {}
            self._rotation_cache_dirty = True
            self._jobs_cache = None
            self._jobs_cache_dirty = True
            self._job_lookup = {}
            
            # Clear directory cache if it exists
            if hasattr(self, '_dir_cache'):
                self._dir_cache = {}
        
        self._notify_status("All caches invalidated - will reload from disk on next access")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for debugging and optimization"""
        stats = {
            'rotation_cache_size': len(self._rotation_cache) if self._rotation_cache else 0,
            'rotation_cache_dirty': self._rotation_cache_dirty,
            'jobs_cache_size': len(self._jobs_cache) if self._jobs_cache else 0,
            'jobs_cache_dirty': self._jobs_cache_dirty,
            'job_lookup_size': len(self._job_lookup),
            'directory_cache_size': len(getattr(self, '_dir_cache', {})),
            'queue_size': self.job_queue.qsize(),
        }
        
        # Add progress stats
        progress_stats = self.get_progress_stats()
        stats.update(progress_stats)
        
        return stats

    def _pending_jobs_count(self) -> int:
        with self.state_lock:
            jobs = self._load_jobs()
        return len(jobs)
    
    def _start_worker_if_needed(self):
        """Start worker thread if not already running"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self._crash_log("WORKER", "Starting new worker thread")
        self.stop_flag = False
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self._notify_status("Worker thread started.")
        self._update_heartbeat("Worker thread started")
    
    def stop_worker(self, preserve_jobs=True):
        """Stop the worker thread"""
        self._crash_log("STOP", f"Stop worker requested, preserve_jobs={preserve_jobs}")
        
        worker_was_running = self.worker_thread and self.worker_thread.is_alive()
        
        if not worker_was_running and not preserve_jobs:
            # Special case: Force clear jobs even when no worker is running
            with self.state_lock:
                # Clear both cache and persistent state
                self._jobs_cache = []
                self._jobs_cache_dirty = False
                self._job_lookup = {}
                self._save_jobs([])  # Clear persistent jobs completely
            
            # Also clear in-memory queue
            self.job_queue.queue.clear()
            
            self._notify_status("Force clear: All jobs removed from persistent state with cache optimization.")
            self._notify_progress()
            return
        
        if not worker_was_running:
            self._notify_status("No active worker.")
            return
        
        # Signal the worker to stop
        self.stop_flag = True
        self.pause_flag = False
        
        if preserve_jobs:
            # Graceful shutdown - preserve jobs for next app start
            # Just signal the worker to stop, don't drain the queue
            # The persistent jobs will remain in jobs_state.json
            self._notify_status("Stop requested. Jobs preserved for next app start.")
        else:
            # Force stop - drain the queue and remove all jobs with optimized cache handling
            drained = 0
            jobs_to_remove = []
            
            try:
                while True:
                    job = self.job_queue.get_nowait()
                    jobs_to_remove.append(job)
                    self.job_queue.task_done()
                    drained += 1
            except Empty:
                pass
            
            # Remove all drained jobs from persistent state efficiently
            with self.state_lock:
                # Clear cache and persistent state completely
                self._jobs_cache = []
                self._jobs_cache_dirty = False
                self._job_lookup = {}
                self._save_jobs([])  # Clear persistent jobs completely
            
            self._notify_status(f"Stop requested. Drained {drained} pending job(s) with optimized cache clearing. Worker will exit shortly.")
        
        # Wait for worker thread to finish (with timeout)
        if self.worker_thread:
            self._notify_status("Waiting for worker thread to finish...")
            self.worker_thread.join(timeout=5.0)  # Wait up to 5 seconds
            if self.worker_thread.is_alive():
                self._notify_status("Worker thread did not finish within timeout.")
                self._crash_log("STOP", "Worker thread timeout - may indicate crash")
            else:
                self._notify_status("Worker thread finished successfully.")
                self._crash_log("STOP", "Worker thread stopped successfully")
        
        self._notify_progress()
        self._update_heartbeat("Worker stopped")
    
    def resume_worker(self):
        """Resume the worker thread and cancel any ongoing sleeps"""
        self._crash_log("RESUME", "Resume worker requested")
        
        # Clear pause flag to resume processing
        self.pause_flag = False
        
        # Start worker if not already running
        self._start_worker_if_needed()
        
        self._notify_status("Queue resumed - all sleeps cancelled")
        self._update_heartbeat("Worker resumed")
    
    def enable_crash_detection(self, enabled: bool = True):
        """Enable or disable crash detection logging"""
        self._crash_detection_enabled = enabled
        if enabled:
            self._crash_log("CONFIG", "Crash detection enabled")
        else:
            logging.info("Crash detection disabled")
    
    def get_crash_detection_status(self) -> dict:
        """Get current crash detection status and recent activity"""
        status = {
            'enabled': self._crash_detection_enabled,
            'gui_callback_stack': self._gui_callback_stack.copy(),
            'worker_running': self.worker_thread and self.worker_thread.is_alive() if self.worker_thread else False,
            'logging_to': 'main application log (qt_crash_detection logger)'
        }
        
        return status
    
    def _clear_all_jobs(self):
        """Clear all jobs from the queue and persistent state with cache optimization."""
        self._crash_log("CLEAR", "Clearing all jobs")
        
        with self.state_lock:
            # Clear persistent jobs and update cache
            self._jobs_cache = []
            self._jobs_cache_dirty = False
            self._job_lookup = {}
            self._save_jobs([])  # This will also save with current rotation data
            
        # Clear in-memory queue
        self.job_queue.queue.clear()
        
        # Reset counters
        self.total_jobs = 0
        self.success_count = 0
        self.failed_count = 0
        
        self._notify_status("All jobs cleared with optimized cache reset.")
        self._notify_progress()
        
        self._crash_log("CLEAR", "All jobs cleared successfully")

    def _get_current_jobs(self) -> List[Dict]:
        """Get current jobs in the queue"""
        jobs = []
        with self.state_lock:
            # Get jobs from persistent storage
            persistent_jobs = self._load_jobs()
            for job in persistent_jobs:
                job_info = {
                    'post_time': job.get('post_time', ''),
                    'attempt': job.get('attempt', 0),
                    'status': 'pending'
                }
                
                # Add photo information if available
                if 'photo_index' in job:
                    # Job has pre-assigned photo index
                    photo_index = job['photo_index']
                    post_data = job.get('post_data', {})
                    photo_paths = post_data.get('photo_paths', [])
                    
                    if photo_paths and 0 <= photo_index < len(photo_paths):
                        photo_path = photo_paths[photo_index]
                        job_info['photo_path'] = photo_path
                        job_info['photo_filename'] = os.path.basename(photo_path)
                        job_info['photo_index'] = photo_index
                        job_info['total_photos'] = len(photo_paths)
                elif 'post_data' in job:
                    # Job uses single photo or no photo
                    post_data = job['post_data']
                    photo_path = post_data.get('photo_path')
                    if photo_path:
                        job_info['photo_path'] = photo_path
                        job_info['photo_filename'] = os.path.basename(photo_path)
                        job_info['photo_index'] = 0
                        job_info['total_photos'] = 1
                
                jobs.append(job_info)
        return jobs
