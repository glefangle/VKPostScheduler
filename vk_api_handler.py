"""
VK API Handler - Dedicated module for all VK API interactions

This module handles all VK API operations including:
- Authentication and session management
- Photo and GIF uploads
- Wall posting operations
- Error handling and logging
- API response processing

All VK API methods are centralized here following the project's architecture patterns
and logging standards using the qt_crash_detection logger system.
"""

import vk_api
import requests
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import json

from vk_config import VKConfigManager


class VKAPIHandler:
    """
    Centralized handler for all VK API interactions with logging
    
    Features:
    - Complete VK API method encapsulation
    - Detailed request/response logging using qt_crash_detection pattern
    - Error handling with context preservation
    - Photo and GIF upload management
    - Wall post operations with attachment support
    """
    
    def __init__(self, vk_config: VKConfigManager, crash_logger=None):
        """
        Initialize VK API handler
        
        Args:
            vk_config: VKConfigManager instance for token/group management
            crash_logger: Logger instance for debug logging (qt_crash_detection)
        """
        self.vk_config = vk_config
        self.crash_logger = crash_logger or logging.getLogger('qt_crash_detection')
        self._api_session = None
        
    def _crash_log(self, category: str, message: str, extra_data: Optional[dict] = None):
        """Write VK API debug info to crash detection log"""
        try:
            log_entry = f"VK_API|{category}|{message}"
            if extra_data:
                log_entry += f" | DATA: {extra_data}"
            
            # Use appropriate log level based on category
            if category in ['VK_API_ERROR', 'CRITICAL']:
                self.crash_logger.error(log_entry)
            elif category in ['VK_API_WARNING']:
                self.crash_logger.warning(log_entry)
            else:
                self.crash_logger.info(log_entry)
                
        except Exception as e:
            # Emergency fallback to standard logging
            logging.error(f"VK API logging error: {e} | Original: {category}: {message}")
    
    def initialize_api_session(self) -> Any:
        """
        Initialize and return VK API session
        
        Returns:
            VK API object: Authenticated VK API session
            
        Raises:
            ValueError: If no token is configured
            Exception: If API initialization fails
        """
        try:
            token = self.vk_config.get_selected_token_value()
            if not token:
                raise ValueError("No VK token selected. Please configure tokens.")
            
            self._crash_log("VK_API_REQUEST", "Initializing VK API session", {
                'method': 'vk_api_initialization',
                'token_length': len(token) if token else 0,
                'has_token': bool(token)
            })
            
            # Initialize VK API session
            session = vk_api.VkApi(token=token)
            api = session.get_api()
            
            self._crash_log("VK_API_RESPONSE", "VK API session initialized successfully", {
                'method': 'vk_api_initialization',
                'success': True,
                'session_type': type(session).__name__
            })
            
            self._api_session = api
            return api
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "VK API session initialization failed", {
                'method': 'vk_api_initialization',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise
    
    def upload_photo_to_group(self, api: Any, photo_path: str, group_id: int) -> str:
        """
        Upload photo to VK group and return attachment string
        
        Args:
            api: VK API session
            photo_path: Path to photo file
            group_id: VK group ID (will be converted to positive)
            
        Returns:
            str: Photo attachment string (format: photo{owner_id}_{id})
            
        Raises:
            FileNotFoundError: If photo file doesn't exist
            ValueError: If VK API returns an error
            Exception: For other upload failures
        """
        if not os.path.exists(photo_path):
            raise FileNotFoundError(f"Photo file not found: {photo_path}")
        
        # Ensure positive group_id for VK API calls
        positive_group_id = abs(group_id)
        
        # Log photo upload start
        self._crash_log("VK_API_REQUEST", "Starting photo upload process", {
            'method': 'photo_upload_workflow',
            'photo_file': os.path.basename(photo_path),
            'photo_path': photo_path,
            'group_id': positive_group_id,
            'file_size_bytes': os.path.getsize(photo_path),
            'file_size_mb': round(os.path.getsize(photo_path) / (1024*1024), 2)
        })
        
        try:
            # Step 1: Get upload server
            upload_server_response = self._get_photo_upload_server(api, positive_group_id)
            upload_url = upload_server_response['upload_url']
            
            # Step 2: Upload photo file to VK servers
            photo_data = self._upload_photo_file(photo_path, upload_url)
            
            # Step 3: Save photo to VK
            saved_photo = self._save_photo_to_vk(api, photo_data, positive_group_id)
            
            # Step 4: Create attachment string
            attachment = f"photo{saved_photo['owner_id']}_{saved_photo['id']}"
            
            self._crash_log("VK_API_RESPONSE", "Photo upload workflow completed", {
                'method': 'photo_upload_workflow',
                'success': True,
                'attachment_created': attachment,
                'photo_id': saved_photo['id'],
                'owner_id': saved_photo['owner_id'],
                'original_file': os.path.basename(photo_path)
            })
            
            print(f'debug print owner_id: {saved_photo['owner_id']}')
            print(f'debug print attachment: {attachment}')
            return attachment
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "Photo upload workflow failed", {
                'method': 'photo_upload_workflow',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'photo_file': os.path.basename(photo_path),
                'group_id': positive_group_id
            })
            raise
    
    def upload_gif_to_group(self, api: Any, gif_path: str, group_id: int, 
                           gif_name: Optional[str] = None) -> str:
        """
        Upload GIF to VK group as document and return attachment string
        
        Args:
            api: VK API session
            gif_path: Path to GIF file
            group_id: VK group ID (will be converted to positive)
            gif_name: Optional name for the GIF (defaults to filename)
            
        Returns:
            str: Document attachment string (format: doc{owner_id}_{id})
            
        Raises:
            FileNotFoundError: If GIF file doesn't exist
            ValueError: If VK API returns an error
            Exception: For other upload failures
        """
        if not os.path.exists(gif_path):
            raise FileNotFoundError(f"GIF file not found: {gif_path}")
        
        # Ensure positive group_id for VK API calls
        positive_group_id = abs(group_id)
        gif_name = gif_name or os.path.basename(gif_path)
        
        # Log GIF upload start
        self._crash_log("VK_API_REQUEST", "Starting GIF upload process", {
            'method': 'gif_upload_workflow',
            'gif_file': os.path.basename(gif_path),
            'gif_path': gif_path,
            'gif_name': gif_name,
            'group_id': positive_group_id,
            'file_size_bytes': os.path.getsize(gif_path),
            'file_size_mb': round(os.path.getsize(gif_path) / (1024*1024), 2)
        })
        
        try:
            # Step 1: Get document upload server
            upload_server_response = self._get_doc_upload_server(api, positive_group_id)
            upload_url = upload_server_response['upload_url']
            
            # Step 2: Upload GIF file to VK servers
            doc_data = self._upload_gif_file(gif_path, upload_url)
            
            # Step 3: Save document to VK
            saved_doc = self._save_doc_to_vk(api, doc_data, gif_name, positive_group_id)
            
            # Step 4: Create attachment string
            doc_info = saved_doc['doc']
            attachment = f"doc{doc_info['owner_id']}_{doc_info['id']}"
            
            self._crash_log("VK_API_RESPONSE", "GIF upload workflow completed", {
                'method': 'gif_upload_workflow',
                'success': True,
                'attachment_created': attachment,
                'doc_id': doc_info['id'],
                'owner_id': doc_info['owner_id'],
                'original_file': os.path.basename(gif_path),
                'saved_title': doc_info.get('title', 'unknown')
            })
            
            return attachment
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "GIF upload workflow failed", {
                'method': 'gif_upload_workflow',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'gif_file': os.path.basename(gif_path),
                'group_id': positive_group_id
            })
            raise
    
    def post_to_wall(self, api: Any, owner_id: int, message: Optional[str] = None, 
                    attachment: Optional[str] = None, post_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Post content to VK wall with optional message and attachments
        
        Args:
            api: VK API session
            owner_id: Wall owner ID (negative for groups)
            message: Optional text message (can be None for media-only posts)
            attachment: Optional attachment string
            post_timestamp: Optional future timestamp for scheduled posts
            
        Returns:
            dict: VK API response with post information
            
        Raises:
            ValueError: If neither message nor attachment is provided
            Exception: For VK API errors
        """
        # Validate post has content
        if not message and not attachment:
            raise ValueError("VK API requires either text content or media attachment for posting")
        
        # Prepare post parameters
        post_params: Dict[str, Union[str, int]] = {
            'owner_id': owner_id
        }
        
        # Add timestamp if provided
        if post_timestamp:
            post_params['publish_date'] = post_timestamp
        
        # Only add message if it's not empty (VK doesn't accept empty message param)
        if message and message.strip():
            post_params['message'] = message.strip()
        
        # Only add attachments if they exist
        if attachment and attachment.strip():
            post_params['attachments'] = attachment.strip()
        
        # Enhanced request logging with complete post content
        message_text = post_params.get('message', '')
        request_data = {
            'method': 'wall.post',
            'owner_id': owner_id,
            'publish_date': post_timestamp or 'immediate',
            'has_message': 'message' in post_params,
            'has_attachments': 'attachments' in post_params,
            'message_length': len(message_text) if isinstance(message_text, str) else 0,
            'attachments': post_params.get('attachments', 'none'),
            # Include actual post content for debugging
            'full_message_text': message_text if isinstance(message_text, str) else '[no message]',
            'attachment_details': post_params.get('attachments', '[no attachments]'),
            'post_timestamp_readable': datetime.fromtimestamp(int(post_timestamp)).strftime('%Y-%m-%d %H:%M:%S') if post_timestamp else 'immediate',
            'all_post_params': dict(post_params)
        }
        
        self._crash_log("VK_API_REQUEST", "wall.post API call with content", request_data)
        
        try:
            result = api.wall.post(**post_params)
            
            # Enhanced response logging with complete response details
            response_data = {
                'method': 'wall.post',
                'success': True,
                'post_id': result.get('post_id') if result else None,
                'response_keys': list(result.keys()) if result else [],
                'response_size': len(str(result)) if result else 0,
                'full_response': dict(result) if result else {},
                'post_url': f"https://vk.com/wall{owner_id}_{result.get('post_id', '')}" if result and result.get('post_id') else 'unknown'
            }
            
            print('result:   ')
            print(result)
            self._crash_log("VK_API_RESPONSE", "wall.post API response with details", response_data)
            
            return result
            
        except Exception as vk_error:
            # Enhanced error logging with request context
            error_data = {
                'method': 'wall.post',
                'success': False,
                'error_type': type(vk_error).__name__,
                'error_message': str(vk_error),
                'owner_id': owner_id,
                'publish_date': post_timestamp or 'immediate',
                'failed_message': post_params.get('message', '[no message]'),
                'failed_attachments': post_params.get('attachments', '[no attachments]'),
                'failed_post_params': dict(post_params)
            }
            self._crash_log("VK_API_ERROR", "wall.post API error with content context", error_data)
            raise
    
    def _get_photo_upload_server(self, api: Any, group_id: int) -> Dict[str, Any]:
        """Get photo upload server URL from VK API"""
        self._crash_log("VK_API_REQUEST", "photos.getWallUploadServer API call", {
            'method': 'photos.getWallUploadServer',
            'group_id': group_id
        })
        
        try:
            result = api.photos.getWallUploadServer(group_id=group_id)
            
            self._crash_log("VK_API_RESPONSE", "photos.getWallUploadServer API response", {
                'method': 'photos.getWallUploadServer',
                'success': True,
                'upload_url_length': len(result.get('upload_url', '')) if result else 0,
                'response_keys': list(result.keys()) if result else []
            })
            
            return result
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "photos.getWallUploadServer API error", {
                'method': 'photos.getWallUploadServer',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'group_id': group_id
            })
            raise
    
    def _upload_photo_file(self, photo_path: str, upload_url: str) -> Dict[str, Any]:
        """Upload photo file to VK upload server"""
        self._crash_log("VK_API_REQUEST", "Photo file upload to VK servers", {
            'method': 'photo_upload_to_vk_server',
            'upload_url_domain': upload_url.split('//')[1].split('/')[0] if '//' in upload_url else 'unknown',
            'photo_file': os.path.basename(photo_path),
            'photo_size_bytes': os.path.getsize(photo_path),
            'upload_url_full': upload_url
        })
        
        try:
            with open(photo_path, 'rb') as fh:
                response = requests.post(upload_url, files={'photo': fh})
            response.raise_for_status()
            photo_data = response.json()
            
            self._crash_log("VK_API_RESPONSE", "Photo file upload to VK servers", {
                'method': 'photo_upload_to_vk_server',
                'success': True,
                'response_keys': list(photo_data.keys()) if photo_data else [],
                'has_error': 'error' in photo_data,
                'response_size': len(str(photo_data)) if photo_data else 0
            })
            
            if 'error' in photo_data:
                self._crash_log("VK_API_ERROR", "VK photo upload server error", {
                    'method': 'photo_upload_to_vk_server',
                    'success': False,
                    'error_from_vk': photo_data['error']
                })
                raise ValueError(f"VK photo upload error: {photo_data['error']}")
            
            return photo_data
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "Photo upload network/general error", {
                'method': 'photo_upload_to_vk_server',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise
    
    def _save_photo_to_vk(self, api: Any, photo_data: Dict[str, Any], 
                         group_id: int) -> Dict[str, Any]:
        """Save uploaded photo to VK using photos.saveWallPhoto"""
        self._crash_log("VK_API_REQUEST", "photos.saveWallPhoto API call", {
            'method': 'photos.saveWallPhoto',
            'group_id': group_id,
            'server': photo_data.get('server'),
            'has_photo_data': 'photo' in photo_data,
            'has_hash': 'hash' in photo_data,
            'photo_upload_server_response': dict(photo_data)
        })
        
        try:
            saved_photo = api.photos.saveWallPhoto(
                server=photo_data['server'],
                photo=photo_data['photo'],
                hash=photo_data['hash'],
                group_id=group_id
            )[0]
            
            self._crash_log("VK_API_RESPONSE", "photos.saveWallPhoto API response", {
                'method': 'photos.saveWallPhoto',
                'success': True,
                'owner_id': saved_photo.get('owner_id'),
                'photo_id': saved_photo.get('id'),
                'response_keys': list(saved_photo.keys()) if saved_photo else [],
                'full_saved_photo_response': dict(saved_photo) if saved_photo else {}
            })
            print(f"owned_id: {saved_photo.get('owner_id')}")
            print('saved_photo: ')
            print(saved_photo)
            return saved_photo
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "photos.saveWallPhoto API error", {
                'method': 'photos.saveWallPhoto',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'group_id': group_id
            })
            raise
    
    def _get_doc_upload_server(self, api: Any, group_id: int) -> Dict[str, Any]:
        """Get document upload server URL from VK API"""
        self._crash_log("VK_API_REQUEST", "docs.getWallUploadServer API call", {
            'method': 'docs.getWallUploadServer',
            'group_id': group_id
        })
        
        try:
            result = api.docs.getWallUploadServer(group_id=group_id)
            
            self._crash_log("VK_API_RESPONSE", "docs.getWallUploadServer API response", {
                'method': 'docs.getWallUploadServer',
                'success': True,
                'upload_url_length': len(result.get('upload_url', '')) if result else 0,
                'response_keys': list(result.keys()) if result else []
            })
            
            return result
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "docs.getWallUploadServer API error", {
                'method': 'docs.getWallUploadServer',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'group_id': group_id
            })
            raise
    
    def _upload_gif_file(self, gif_path: str, upload_url: str) -> Dict[str, Any]:
        """Upload GIF file to VK upload server"""
        self._crash_log("VK_API_REQUEST", "GIF file upload to VK servers", {
            'method': 'gif_upload_to_vk_server',
            'upload_url_domain': upload_url.split('//')[1].split('/')[0] if '//' in upload_url else 'unknown',
            'gif_file': os.path.basename(gif_path),
            'gif_size_bytes': os.path.getsize(gif_path),
            'upload_url_full': upload_url
        })
        
        try:
            with open(gif_path, 'rb') as fh:
                response = requests.post(upload_url, files={'file': fh})
            response.raise_for_status()
            doc_data = response.json()
            
            self._crash_log("VK_API_RESPONSE", "GIF file upload to VK servers", {
                'method': 'gif_upload_to_vk_server',
                'success': True,
                'response_keys': list(doc_data.keys()) if doc_data else [],
                'has_error': 'error' in doc_data,
                'response_size': len(str(doc_data)) if doc_data else 0
            })
            
            if 'error' in doc_data:
                self._crash_log("VK_API_ERROR", "VK GIF upload server error", {
                    'method': 'gif_upload_to_vk_server',
                    'success': False,
                    'error_from_vk': doc_data['error']
                })
                raise ValueError(f"VK document upload error: {doc_data['error']}")
            
            return doc_data
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "GIF upload network/general error", {
                'method': 'gif_upload_to_vk_server',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise
    
    def _save_doc_to_vk(self, api: Any, doc_data: Dict[str, Any], 
                       title: str, group_id: int) -> Dict[str, Any]:
        """Save uploaded document to VK using docs.save"""
        self._crash_log("VK_API_REQUEST", "docs.save API call", {
            'method': 'docs.save',
            'group_id': group_id,
            'file_param': doc_data.get('file', 'unknown'),
            'title': title,
            'gif_upload_server_response': dict(doc_data)
        })
        
        try:
            saved_doc = api.docs.save(
                file=doc_data['file'], 
                title=title, 
                group_id=group_id
            )
            
            self._crash_log("VK_API_RESPONSE", "docs.save API response", {
                'method': 'docs.save',
                'success': True,
                'has_doc': 'doc' in saved_doc if saved_doc else False,
                'response_keys': list(saved_doc.keys()) if saved_doc else [],
                'full_saved_doc_response': dict(saved_doc) if saved_doc else {}
            })
            
            if not saved_doc or 'doc' not in saved_doc:
                raise ValueError("Failed to save GIF document to VK")
            
            return saved_doc
            
        except Exception as e:
            self._crash_log("VK_API_ERROR", "docs.save API error", {
                'method': 'docs.save',
                'success': False,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'group_id': group_id
            })
            raise
    
    def get_current_group_id(self) -> int:
        """Get currently selected group ID as integer"""
        group_id_str = self.vk_config.get_selected_group_id()
        if not group_id_str:
            raise ValueError("No VK group selected. Please configure groups.")
        
        try:
            return int(str(group_id_str).lstrip('-'))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid group ID format: {group_id_str}")