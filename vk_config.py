import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging


@dataclass
class VKGroup:
    """Represents a VK group with ID and name"""
    name: str
    group_id: str
    day_schedule: List[str] = None  # List of times in "HH:MM" format
    default_text: str = ""  # Default text for this group
    
    def __post_init__(self):
        # Validate group_id is numeric
        try:
            int(str(self.group_id).lstrip('-'))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid group ID: {self.group_id}. Must be numeric.")
        
        # Initialize day_schedule if not provided
        if self.day_schedule is None:
            self.day_schedule = []
        
        # Initialize default_text if not provided
        if self.default_text is None:
            self.default_text = ""


@dataclass
class VKToken:
    """Represents a VK token with associated groups"""
    name: str
    token: str
    groups: List[VKGroup]
    
    def __post_init__(self):
        # Convert dict groups to VKGroup objects if needed
        if self.groups and len(self.groups) > 0:
            # Check if any group is a dict and convert all if needed
            if isinstance(self.groups[0], dict):
                self.groups = [VKGroup(**group) for group in self.groups]
        elif self.groups is None:
            self.groups = []
    
    def add_group(self, group: VKGroup) -> None:
        """Add a group to this token"""
        # Check for duplicate names
        if any(g.name == group.name for g in self.groups):
            raise ValueError(f"Group name '{group.name}' already exists for this token")
        self.groups.append(group)
    
    def remove_group(self, group_name: str) -> bool:
        """Remove a group by name. Returns True if removed, False if not found."""
        for i, group in enumerate(self.groups):
            if group.name == group_name:
                del self.groups[i]
                return True
        return False
    
    def get_group(self, group_name: str) -> Optional[VKGroup]:
        """Get a group by name"""
        for group in self.groups:
            if group.name == group_name:
                return group
        return None
    
    def update_group(self, old_group_name: str, new_group: VKGroup) -> bool:
        """Update an existing group. Returns True if updated, False if not found."""
        for i, group in enumerate(self.groups):
            if group.name == old_group_name:
                # Replace the old group with the new one
                self.groups[i] = new_group
                return True
        return False


class VKConfigManager:
    """Manages VK tokens and groups configuration"""
    
    def __init__(self, config_file: str = "vk_config.json"):
        self.config_file = config_file
        self.tokens: Dict[str, VKToken] = {}
        self.selected_token: Optional[str] = None
        self.selected_group: Optional[str] = None
        self.load_config()
    
    def add_token(self, token: VKToken) -> None:
        """Add a new VK token"""
        if token.name in self.tokens:
            raise ValueError(f"Token name '{token.name}' already exists")
        self.tokens[token.name] = token
        self.save_config()
    
    def remove_token(self, token_name: str) -> bool:
        """Remove a VK token. Returns True if removed, False if not found."""
        if token_name in self.tokens:
            del self.tokens[token_name]
            # Clear selection if the selected token was removed
            if self.selected_token == token_name:
                self.selected_token = None
                self.selected_group = None
            self.save_config()
            return True
        return False
    
    def get_token(self, token_name: str) -> Optional[VKToken]:
        """Get a token by name"""
        return self.tokens.get(token_name)
    
    def get_token_names(self) -> List[str]:
        """Get all token names"""
        return list(self.tokens.keys())
    
    def get_group_names(self, token_name: str) -> List[str]:
        """Get all group names for a specific token"""
        token = self.get_token(token_name)
        return [group.name for group in token.groups] if token else []
    
    def set_selection(self, token_name: Optional[str], group_name: Optional[str] = None) -> None:
        """Set the currently selected token and group"""
        if token_name and token_name not in self.tokens:
            raise ValueError(f"Token '{token_name}' not found")
        
        if token_name and group_name:
            token = self.get_token(token_name)
            if not token or not token.get_group(group_name):
                raise ValueError(f"Group '{group_name}' not found in token '{token_name}'")
        
        self.selected_token = token_name
        self.selected_group = group_name
        self.save_config()
    
    def get_selected_token_value(self) -> Optional[str]:
        """Get the actual VK token value for the selected token"""
        if not self.selected_token:
            return None
        token = self.get_token(self.selected_token)
        return token.token if token else None
    
    def get_selected_group_id(self) -> Optional[str]:
        """Get the group ID for the selected group"""
        if not self.selected_token or not self.selected_group:
            return None
        token = self.get_token(self.selected_token)
        if not token:
            return None
        group = token.get_group(self.selected_group)
        return group.group_id if group else None
    
    def get_selection(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current selection as (token_name, group_name)"""
        return self.selected_token, self.selected_group
    
    def load_config(self) -> None:
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            self.create_default_config()
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load tokens
            tokens_data = data.get('tokens', {})
            self.tokens = {}
            for token_name, token_data in tokens_data.items():
                self.tokens[token_name] = VKToken(**token_data)
            
            # Load selection
            self.selected_token = data.get('selected_token')
            self.selected_group = data.get('selected_group')
            
            # If no tokens exist, create default config
            if not self.tokens:
                self.create_default_config()
            
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logging.error(f"Failed to load VK config: {e}")
            # Create default config as fallback
            self.create_default_config()
    
    def save_config(self) -> None:
        """Save configuration to file"""
        try:
            data = {
                'tokens': {name: asdict(token) for name, token in self.tokens.items()},
                'selected_token': self.selected_token,
                'selected_group': self.selected_group
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logging.error(f"Failed to save VK config: {e}")
    
    def create_default_config(self) -> None:
        """Create an empty default configuration"""
        try:
            # Start with empty configuration - no sample tokens
            self.tokens = {}
            self.selected_token = None
            self.selected_group = None
            
            self.save_config()
            logging.info("Created empty vk_config.json. Use 'Manage Tokens & Groups' to add your VK configuration.")
                    
        except Exception as e:
            logging.error(f"Failed to create default VK config: {e}")
    
    def update_token(self, old_name: str, new_token: VKToken) -> None:
        """Update an existing token"""
        if old_name not in self.tokens:
            raise ValueError(f"Token '{old_name}' not found")
        
        # If name changed, handle the rename
        if old_name != new_token.name:
            if new_token.name in self.tokens:
                raise ValueError(f"Token name '{new_token.name}' already exists")
            del self.tokens[old_name]
            # Update selection if needed
            if self.selected_token == old_name:
                self.selected_token = new_token.name
        
        self.tokens[new_token.name] = new_token
        self.save_config()
    
    def has_valid_selection(self) -> bool:
        """Check if current selection is valid and complete"""
        return (self.selected_token is not None and 
                self.selected_group is not None and
                self.get_selected_token_value() is not None and
                self.get_selected_group_id() is not None)
    
    def get_selected_group_schedule(self) -> List[str]:
        """Get the day schedule for the selected group"""
        if not self.selected_token or not self.selected_group:
            return []
        
        token = self.get_token(self.selected_token)
        if not token:
            return []
        
        group = token.get_group(self.selected_group)
        return group.day_schedule if group else []
    
    def get_group_schedule(self, token_name: str, group_name: str) -> List[str]:
        """Get the day schedule for a specific group"""
        token = self.get_token(token_name)
        if not token:
            return []
        
        group = token.get_group(group_name)
        return group.day_schedule if group else []
    
    def set_group_schedule(self, token_name: str, group_name: str, schedule: List[str]) -> None:
        """Set the day schedule for a specific group"""
        token = self.get_token(token_name)
        if not token:
            raise ValueError(f"Token '{token_name}' not found")
        
        group = token.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found in token '{token_name}'")
        
        # Validate schedule times
        for time_str in schedule:
            try:
                hour, minute = time_str.split(":")
                if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                    raise ValueError(f"Invalid time format: {time_str}")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM format.")
        
        group.day_schedule = schedule
        self.save_config()
    
    def get_group_default_text(self, token_name: str, group_name: str) -> str:
        """Get the default text for a specific group"""
        token = self.get_token(token_name)
        if not token:
            return ""
        
        group = token.get_group(group_name)
        return group.default_text if group else ""
    
    def set_group_default_text(self, token_name: str, group_name: str, default_text: str) -> None:
        """Set the default text for a specific group"""
        token = self.get_token(token_name)
        if not token:
            raise ValueError(f"Token '{token_name}' not found")
        
        group = token.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found in token '{token_name}'")
        
        group.default_text = default_text
        self.save_config()
