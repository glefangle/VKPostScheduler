"""
GIF Transformation Utility for VK Compliance
Handles GIF aspect ratio adjustment to meet VK requirements (0.66:1 to 2.5:1)
"""

import os
import tempfile
import logging
from typing import Optional, Tuple
from PIL import Image, ImageSequence

class GIFTransformer:
    """
    Handles GIF transformation to meet VK's aspect ratio requirements.
    VK requirement: aspect ratio between 0.66:1 and 2.5:1 for proper display.
    """
    
    def __init__(self):
        self.min_aspect_ratio = 0.66  # Minimum width:height ratio
        self.max_aspect_ratio = 2.5   # Maximum width:height ratio
        self.logger = logging.getLogger(__name__)
        
    def check_aspect_ratio(self, width: int, height: int) -> bool:
        """
        Check if the given dimensions meet VK's aspect ratio requirements.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            bool: True if aspect ratio is within VK requirements, False otherwise
        """
        if height == 0:
            return False
            
        aspect_ratio = width / height
        return self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio
    
    def calculate_target_dimensions(self, original_width: int, original_height: int) -> Tuple[int, int]:
        """
        Calculate target dimensions that will meet VK requirements while preserving
        as much of the original image as possible.
        
        Args:
            original_width: Original image width
            original_height: Original image height
            
        Returns:
            Tuple[int, int]: Target (width, height) dimensions
        """
        aspect_ratio = original_width / original_height
        
        if self.check_aspect_ratio(original_width, original_height):
            # Already compliant
            return original_width, original_height
        
        if aspect_ratio < self.min_aspect_ratio:
            # Too tall/narrow - need to add width to reach minimum ratio (0.66:1)
            target_width = int(original_height * self.min_aspect_ratio)
            target_height = original_height
        else:  # aspect_ratio > self.max_aspect_ratio
            # Too wide - need to add height to reach maximum ratio (2.5:1)
            target_width = original_width
            target_height = int(original_width / self.max_aspect_ratio)
        
        # Verify the result is actually compliant and fix rounding issues
        result_ratio = target_width / target_height
        
        # If still not compliant due to rounding, adjust to ensure compliance
        if result_ratio > self.max_aspect_ratio:
            # Ratio too high - increase height to bring ratio down
            target_height = int(target_width / self.max_aspect_ratio) + 1
        elif result_ratio < self.min_aspect_ratio:
            # Ratio too low - increase width to bring ratio up
            target_width = int(target_height * self.min_aspect_ratio) + 1
        
        # Final verification - if still not compliant, force it
        final_ratio = target_width / target_height
        if not (self.min_aspect_ratio <= final_ratio <= self.max_aspect_ratio):
            if aspect_ratio < self.min_aspect_ratio:
                # Force minimum ratio by adding more width
                target_width = int(target_height * self.min_aspect_ratio) + 1
            else:
                # Force maximum ratio by adding more height  
                target_height = int(target_width / self.max_aspect_ratio) + 1
        
        return target_width, target_height
    
    def transform_gif(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Transform a GIF to meet VK's aspect ratio requirements.
        
        Args:
            input_path: Path to the input GIF file
            output_path: Optional path for output file. If None, creates temp file.
            
        Returns:
            str: Path to the transformed GIF file
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If file is not a valid GIF
            Exception: For other processing errors
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input GIF file not found: {input_path}")
        
        try:
            with Image.open(input_path) as img:
                if img.format != 'GIF':
                    raise ValueError(f"File is not a GIF: {input_path}")
                
                original_width, original_height = img.size
                self.logger.info(f"Processing GIF: {original_width}x{original_height}, "
                               f"aspect ratio: {original_width/original_height:.2f}")
                
                # Check if transformation is needed
                if self.check_aspect_ratio(original_width, original_height):
                    self.logger.info("GIF already meets VK requirements, no transformation needed")
                    return input_path
                
                # Calculate target dimensions
                target_width, target_height = self.calculate_target_dimensions(
                    original_width, original_height
                )
                
                self.logger.info(f"Target dimensions: {target_width}x{target_height}, "
                               f"aspect ratio: {target_width/target_height:.2f}")
                
                # Create output path if not provided
                if output_path is None:
                    temp_dir = tempfile.mkdtemp()
                    base_name = os.path.splitext(os.path.basename(input_path))[0]
                    output_path = os.path.join(temp_dir, f"{base_name}_vk_transformed.gif")
                
                # Process all frames
                frames = []
                durations = []
                
                # Get background color from the original GIF
                background_color = None
                if img.mode == 'P':
                    # For palette mode, try to get background color
                    if 'transparency' in img.info:
                        # Use transparent background
                        background_color = (0, 0, 0, 0)  # Transparent
                    else:
                        # Try to get background color from palette
                        background_index = img.info.get('background', 0)
                        try:
                            palette = img.getpalette()
                            if palette and background_index < len(palette) // 3:
                                r = palette[background_index * 3]
                                g = palette[background_index * 3 + 1]
                                b = palette[background_index * 3 + 2]
                                background_color = (r, g, b, 255)
                            else:
                                background_color = (255, 255, 255, 0)  # Transparent white
                        except:
                            background_color = (255, 255, 255, 0)  # Transparent white as fallback
                else:
                    # For other modes, use transparent background
                    background_color = (0, 0, 0, 0)  # Transparent
                
                for frame in ImageSequence.Iterator(img):
                    try:
                        # Preserve original frame without unnecessary conversion
                        original_frame = frame.copy()
                        
                        # Determine if we need cropping or padding
                        need_crop_x = target_width < original_width
                        need_crop_y = target_height < original_height
                        
                        # Apply cropping if needed
                        if need_crop_x:
                            # Need to crop horizontally
                            crop_x = (original_width - target_width) // 2
                            original_frame = original_frame.crop((crop_x, 0, crop_x + target_width, original_height))
                        
                        if need_crop_y:
                            # Need to crop vertically  
                            crop_y = (original_height - target_height) // 2
                            original_frame = original_frame.crop((0, crop_y, original_width, crop_y + target_height))
                        
                        # If no padding needed (only cropping), use the cropped frame directly
                        if original_frame.size == (target_width, target_height):
                            frames.append(original_frame)
                        else:
                            # Need padding - create new canvas with proper background
                            if img.mode == 'P':
                                # For palette mode, create a new palette image
                                new_frame = Image.new('P', (target_width, target_height), 0)
                                if img.getpalette():
                                    new_frame.putpalette(img.getpalette())
                                # Set transparency if original had it
                                if 'transparency' in img.info:
                                    new_frame.info['transparency'] = img.info['transparency']
                            else:
                                # For other modes, use the original mode
                                new_frame = Image.new(img.mode, (target_width, target_height), 
                                                    background_color[:len(img.getbands())] if background_color else 0)
                            
                            # Calculate position to center the original frame
                            x_offset = (target_width - original_frame.width) // 2
                            y_offset = (target_height - original_frame.height) // 2
                            
                            # Paste the original frame onto the new canvas
                            if img.mode == 'P' and 'transparency' in img.info:
                                # For transparent palette images, use transparency mask
                                new_frame.paste(original_frame, (x_offset, y_offset))
                            else:
                                new_frame.paste(original_frame, (x_offset, y_offset))
                            
                            frames.append(new_frame)
                        
                        # Try to preserve frame duration
                        try:
                            duration = frame.info.get('duration', 100)
                            durations.append(duration)
                        except:
                            durations.append(100)  # Default 100ms
                    
                    except Exception as frame_error:
                        self.logger.error(f"Error processing frame, skipping: {frame_error}")
                        # Skip problematic frames rather than failing completely
                        continue
                
                # Validate that we have frames to save
                if not frames:
                    raise Exception("No frames could be processed successfully")
                
                # Ensure durations list matches frames count
                while len(durations) < len(frames):
                    durations.append(100)  # Add default duration for missing entries
                durations = durations[:len(frames)]  # Trim excess durations
                
                # Save the transformed GIF
                save_kwargs = {
                    'format': 'GIF',
                    'save_all': True,
                    'append_images': frames[1:],
                    'duration': durations,
                    'loop': img.info.get('loop', 0),  # Preserve loop setting
                    'disposal': img.info.get('disposal', 2),  # Preserve disposal method
                    'optimize': False  # Don't optimize to preserve colors exactly
                }
                
                # Handle transparency and other properties based on original image mode
                if img.mode == 'P':
                    # For palette mode, preserve all palette-related info
                    if 'transparency' in img.info:
                        save_kwargs['transparency'] = img.info['transparency']
                    if 'background' in img.info:
                        save_kwargs['background'] = img.info['background']
                elif frames[0].mode == 'P':
                    # If frames are palette mode, try to preserve transparency
                    if hasattr(frames[0], 'info') and 'transparency' in frames[0].info:
                        save_kwargs['transparency'] = frames[0].info['transparency']
                
                try:
                    frames[0].save(output_path, **save_kwargs)
                except Exception as save_error:
                    self.logger.warning(f"Save with full options failed: {save_error}, trying simplified save")
                    # Fallback to simpler save options
                    simple_kwargs = {
                        'format': 'GIF',
                        'save_all': True,
                        'append_images': frames[1:],
                        'duration': durations,
                        'loop': img.info.get('loop', 0)
                    }
                    frames[0].save(output_path, **simple_kwargs)
                
                self.logger.info(f"GIF transformed successfully: {output_path}")
                return output_path
                
        except Exception as e:
            self.logger.error(f"Error transforming GIF {input_path}: {e}")
            raise Exception(f"GIF transformation failed: {e}")
    
    def get_gif_info(self, gif_path: str) -> dict:
        """
        Get information about a GIF file including dimensions and compliance.
        
        Args:
            gif_path: Path to the GIF file
            
        Returns:
            dict: Information about the GIF including dimensions and VK compliance
        """
        try:
            with Image.open(gif_path) as img:
                if img.format != 'GIF':
                    return {'error': 'File is not a GIF'}
                
                width, height = img.size
                aspect_ratio = width / height
                is_compliant = self.check_aspect_ratio(width, height)
                
                return {
                    'width': width,
                    'height': height,
                    'aspect_ratio': round(aspect_ratio, 2),
                    'vk_compliant': is_compliant,
                    'frame_count': getattr(img, 'n_frames', 1),
                    'format': img.format,
                    'file_size_mb': round(os.path.getsize(gif_path) / (1024 * 1024), 2)
                }
        except Exception as e:
            return {'error': str(e)}
    
    def cleanup_temp_files(self, file_path: str):
        """
        Clean up temporary files created during transformation.
        
        Args:
            file_path: Path to the file to clean up
        """
        try:
            if os.path.exists(file_path) and tempfile.gettempdir() in file_path:
                os.remove(file_path)
                # Try to remove the temp directory if it's empty
                temp_dir = os.path.dirname(file_path)
                try:
                    os.rmdir(temp_dir)
                except OSError:
                    pass  # Directory not empty or other error
        except Exception as e:
            self.logger.warning(f"Could not clean up temp file {file_path}: {e}")
