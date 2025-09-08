# VK Post Scheduler

A desktop application for scheduling posts to VK (VKontakte) groups with advanced photo management and posting automation.


## 📋 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [Advanced Features](#-advanced-features)
- [Building Executable](#-building-executable)
- [Technical Architecture](#-technical-architecture)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### Core Functionality
- **📅 Schedule Posts**: Plan posts across multiple days with custom time slots
- **🖼️ Multi-Media Support**: Upload photos, GIFs, and text posts
- **🔄 Photo Rotation**: Automatic photo cycling with multiple rotation modes
- **👥 Multi-Group Management**: Manage multiple VK tokens and groups
- **⏰ Flexible Scheduling**: Custom schedules per group with default text templates

### Advanced Features
- **🎯 Smart Photo Management**: Different posts mode with pre-assigned photo indexing
- **🔧 Error Recovery**: Automatic retry logic with exponential backoff
- **⏸️ Pause/Resume**: Full control over posting queue with pause/resume functionality
- **📊 Progress Tracking**: Real-time progress monitoring and statistics
- **🔄 Background Processing**: Non-blocking GUI with threaded job processing
- **💾 State Persistence**: Jobs and configuration survive application restarts

### Technical Features
- **🛡️ Crash Detection**: Advanced Qt crash detection and logging system
- **📝 Comprehensive Logging**: Detailed application and API interaction logs
- **🎨 Modern GUI**: Clean PyQt5 interface with responsive design
- **🔒 Secure Configuration**: Safe token storage and management
- **🚀 Performance Optimized**: Efficient memory usage and background processing

## 📸 Screenshots

*Note: Add screenshots of the application interface here*

## 📦 Installation

### System Requirements

- **Python**: 3.7 or higher
- **Operating System**: Windows, macOS, or Linux
- **RAM**: Minimum 512 MB (1 GB recommended)
- **Storage**: 50 MB free space

### Method 1: Automatic Setup (Recommended)

#### Windows
# Run the automatic setup script
run.bat
```

#### Linux/macOS
```bash
# Make the script executable and run
chmod +x run.sh
./run.sh
```

### Method 2: Manual Installation

1. **Create virtual environment**:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. **Run the application**:
```bash
python main.py
```

### Dependencies

The application requires the following Python packages:
- `vk-api`: VK API integration
- `requests>=2.28`: HTTP requests handling
- `Pillow>=8.0.0`: Image processing
- `PyQt5>=5.15.0`: GUI framework
- `pyinstaller>=6.0.0`: For building standalone executables

## 🚀 Quick Start

### 1. First Launch
1. Run the application using one of the installation methods above
2. The application will create necessary configuration files on first launch

### 2. Configure VK Access
1. Click **"Manage Tokens & Groups"** in the main interface
2. Add your VK access token:
   - Click **"Add Token"**
   - Enter a name for your token (e.g., "My VK Token")
   - Paste your VK access token
3. Add VK groups:
   - Select your token
   - Click **"Add Group"**
   - Enter group name and VK group ID

### 3. Create Your First Scheduled Post
1. Select your token and group from the dropdowns
2. Enter your post text
3. (Optional) Select photos or GIF to upload
4. Set start and end dates
5. Configure posting times
6. Click **"Schedule Posts"**

### 4. Monitor Progress
- View real-time posting status in the status area
- Check progress statistics
- Use pause/resume controls as needed

## ⚙️ Configuration

### Getting VK Access Token

1. **Create VK Application**:
   - Visit [VK Developers](https://vk.com/dev)
   - Create a new standalone application
   - Note your Application ID

2. **Get Access Token**:
   - Use VK API authorization URL:
   ```
   https://oauth.vk.com/authorize?client_id=YOUR_APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,photos,docs&response_type=token&v=5.131
   ```
   - Replace `YOUR_APP_ID` with your application ID
   - Authorize the application
   - Copy the access token from the redirected URL

### Finding VK Group ID

1. **For Public Groups**:
   - Visit your VK group page
   - The ID is in the URL: `vk.com/club123456789` → ID is `123456789`

2. **For Private Groups**:
   - Use VK API method `groups.getById` with your group's screen name
   - The ID will be returned in the response

### Configuration Files

The application creates several configuration files:

- **`vk_config.json`**: Stores VK tokens, groups, and settings
- **`jobs_state.json`**: Persistent job queue and rotation state
- **`logs/`**: Application logs directory
- **`error.log`**: Critical error logging
- **`crash.log`**: Application crash information

## 📖 Usage Guide

### Basic Posting

1. **Text Posts**:
   - Enter text in the message field
   - Set dates and times
   - Click "Schedule Posts"

2. **Photo Posts**:
   - Click "Select Photos" to choose image files
   - Supported formats: JPG, JPEG, PNG
   - Enter optional text
   - Schedule as normal

3. **GIF Posts**:
   - Click "Select Photos" and choose GIF files
   - Enter GIF name (optional)
   - Add text if desired
   - Schedule posts

### Advanced Scheduling

#### Different Posts Mode
Enable this for unique content per time slot:
- Each post gets a different photo from your selection
- Photos are assigned in order to time slots
- Prevents duplicate content across posts

#### Group Schedules
Save common posting schedules per group:
1. Select token and group
2. Click "Manage Group Schedule"
3. Add/remove time slots
4. Save for future use

#### Default Text Templates
Set default text per group:
1. Select group
2. Click "Manage Default Text"
3. Enter template text
4. Save for automatic filling

### Queue Management

#### Pause/Resume Operations
- **Pause**: Stops processing new posts (current post completes)
- **Resume**: Continues with next posts in queue
- **Clear Queue**: Removes all pending posts

#### Error Handling
- **Automatic Retries**: Failed posts retry up to 3 times
- **Error Pause**: Queue pauses on errors for user review
- **1-Minute Delays**: Built-in delays after unsuccessful posts

#### Job Persistence
- Jobs survive application restarts
- Rotation state is preserved
- Configuration changes are saved immediately

## 🔧 Advanced Features

### Photo Rotation Systems

#### 1. User Selected Photos (Different Posts Mode)
- Pre-assigns specific photos to each time slot
- Prevents photo exhaustion during scheduling
- Maintains rotation order across app restarts

#### 2. Directory-Based Rotation
- Cycles through photos in a directory
- Maintains last-posted file tracking
- Useful for large photo collections

### Logging and Debugging

#### Qt Crash Detection
- Advanced GUI crash monitoring
- Rate limiting to prevent painter issues
- Comprehensive error context capture

#### Application Logging
```
logs/app_YYYYMMDD_HHMMSS.log  # Main application log
error.log                     # Error-only log
crash.log                     # Application crashes
```

#### Log Levels
- **INFO**: General application flow
- **WARNING**: Potential issues
- **ERROR**: Recoverable errors
- **CRITICAL**: Application crashes

### Performance Features

#### Memory Optimization
- Efficient job queue management
- Cached configuration loading
- Optimized image processing

#### Background Processing
- Non-blocking GUI operations
- Threaded job execution
- Responsive user interface

## 🔨 Building Executable

### Windows Executable

Use the provided build script:

```batch
build_exe.bat
```

This creates a standalone `PostScheduler.exe` in the `dist/` directory that can run without Python installation.

### Manual Build

```bash
# Install PyInstaller if not already installed
pip install pyinstaller>=6.0.0

# Build executable
pyinstaller \
    --onefile \
    --windowed \
    --name=PostScheduler \
    --add-data="vk_config.py;." \
    --hidden-import=vk_api \
    --hidden-import=PyQt5 \
    --hidden-import=requests \
    --hidden-import=Pillow \
    --collect-all=vk_api \
    --collect-all=PyQt5 \
    main.py
```

### Build Options

- `--onefile`: Creates single executable file
- `--windowed`: Hides console window (GUI only)
- `--name`: Sets executable name
- `--add-data`: Includes additional files
- `--hidden-import`: Ensures modules are included
- `--collect-all`: Includes all package files

## 🏗️ Technical Architecture

### Project Structure

```
VkPostScheduler/
├── main.py                 # Application entry point and core logic
├── post_scheduler.py       # Business logic and job processing
├── pyqt_gui.py            # PyQt5 GUI implementation
├── vk_config.py           # Configuration management
├── vk_api_handler.py      # VK API integration
├── requirements.txt       # Python dependencies
├── run.bat               # Windows startup script
├── run.sh                # Unix startup script
├── build_exe.bat         # Windows build script
├── .gitignore            # Git ignore patterns
└── README.md             # This file
```

### Architecture Patterns

#### 1. Observer Pattern
- GUI subscribes to business logic events
- Status, progress, and error notifications
- Decoupled communication between layers

#### 2. Facade Pattern
- `ApplicationCore` provides simplified interface
- Hides complexity of underlying systems
- Clean separation between GUI and business logic

#### 3. State Pattern
- Job queue state management
- Pause/resume functionality
- Persistent state across restarts

#### 4. Factory Pattern
- Job creation with consistent structure
- Media path resolution
- Error handling standardization

### Threading Model

#### Main Thread (GUI)
- PyQt5 event loop
- User interaction handling
- Status updates and progress display

#### Worker Thread
- Job queue processing
- VK API interactions
- Media upload operations
- Error handling and retries

#### Thread Safety
- Thread-safe job queue operations
- Atomic state updates
- Safe GUI callback mechanisms

## 🐛 Troubleshooting

### Common Issues

#### 1. "No VK token selected" Error
**Solution**:
1. Open "Manage Tokens & Groups"
2. Add your VK access token
3. Ensure token has required permissions (wall, photos, docs)

#### 2. "Invalid group ID" Error
**Solution**:
1. Verify VK group ID is correct
2. Ensure token has access to the group
3. For private groups, confirm admin access

#### 3. Photo Upload Failures
**Solution**:
1. Check image file format (JPG, PNG, GIF only)
2. Verify file size (< 50MB recommended)
3. Ensure stable internet connection
4. Check VK API limits

#### 4. Application Won't Start
**Solution**:
1. Verify Python 3.7+ is installed
2. Check all dependencies are installed: `pip install -r requirements.txt`
3. Review error.log for startup errors
4. Try running with: `python main.py`

#### 5. PyQt5 Import Errors
**Solution**:
```bash
# Reinstall PyQt5
pip uninstall PyQt5
pip install PyQt5>=5.15.0

# On Linux, you might need:
sudo apt-get install python3-pyqt5
```

### Debug Mode

Enable verbose logging by editing the log level in `main.py`:

```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

### Log Analysis

Check these log files for issues:
- `error.log`: Critical errors
- `logs/app_*.log`: Detailed application flow
- `crash.log`: Application crashes

## 🤝 Contributing

### Development Setup

1. **Fork and clone the repository**
2. **Create development environment**:
```bash
python -m venv dev_env
source dev_env/bin/activate  # or dev_env\Scripts\activate on Windows
pip install -r requirements.txt
```

3. **Run tests** (if available):
```bash
python -m pytest tests/
```

### Code Style

- Follow PEP 8 Python style guidelines
- Use type hints where appropriate
- Add docstrings for all public methods
- Keep functions focused and modular

### Pull Request Guidelines

1. Create feature branch from main
2. Make focused, atomic commits
3. Update documentation as needed
4. Test thoroughly before submitting
5. Include description of changes

### Reporting Issues

When reporting bugs, include:
- Operating system and Python version
- Complete error messages
- Steps to reproduce
- Relevant log file contents
- Screenshots if GUI-related

## 📞 Support

- **Documentation**: This README and inline code comments
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and community support

## 🔄 Changelog

### Version 0.9.5 (Current)
- ✨ Complete PyQt5 GUI implementation
- 🔄 Advanced photo rotation system
- 🛡️ Qt crash detection and logging
- ⏸️ Pause/resume functionality
- 💾 Persistent job state management
- 🎯 Different posts mode with photo indexing
- 📊 Real-time progress tracking
- 🔧 Enhanced error handling and recovery