from .logger import Logger, setup_taskbar_icon
from .documentation_manager import DocumentationManager
from .font_manager import FontManager
from .helpers import literal, literal_presenter, ensure_directories, strip_filename_quotes, safe_filename_path


# Global logger instance - will be set during initialization
logger = None

__all__ = ['Logger', 'setup_taskbar_icon', 'DocumentationManager', 'FontManager', 
           'literal', 'literal_presenter', 'ensure_directories', 'strip_filename_quotes', 'safe_filename_path', 'logger']