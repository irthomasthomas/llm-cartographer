"""Utility functions for llm-cartographer."""

import os
import io
import time
import logging
import concurrent.futures
import threading
import mimetypes
from pathlib import Path
from typing import List, Any, Callable, TypeVar, Generic, Iterable, Dict, Optional, Union, Tuple

# Configure default logger
logger = logging.getLogger("llm_cartographer")

# Type variables for generic functions
T = TypeVar('T')
R = TypeVar('R')

class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str = None, verbose: bool = True):
        """
        Initialize Timer context manager.
        
        Args:
            name: Name of the operation being timed
            verbose: Whether to print timing information
        """
        self.name = name
        self.verbose = verbose
        self.start_time = None
        self.end_time = None
        
    def __enter__(self) -> 'Timer':
        """Start the timer when entering the context."""
        self.start_time = time.time()
        return self
        
    def __exit__(self, *args):
        """Stop the timer and optionally print timing information."""
        self.end_time = time.time()
        if self.verbose:
            duration = self.end_time - self.start_time
            operation = f"'{self.name}'" if self.name else "Operation"
            logger.info(f"{operation} completed in {duration:.2f} seconds")
    
    @property
    def duration(self) -> float:
        """Return the duration of the timed operation."""
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time


def safe_read_file(file_path: Union[str, Path], max_size: int = None) -> str:
    """
    Read a file safely with memory constraints.
    
    Args:
        file_path: Path to the file
        max_size: Maximum size in bytes to read
        
    Returns:
        String contents of the file, possibly truncated
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    if max_size is not None and path.stat().st_size > max_size:
        # For large files, read only the beginning portion to save memory
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(max_size)
    else:
        # For small files, read the whole file
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try with errors='ignore'
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Error reading file {path}: {e}")
            return f"[Error reading file: {str(e)}]"


def count_lines_in_file(file_path: Union[str, Path]) -> int:
    """
    Count the number of lines in a file efficiently without loading the entire file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Number of lines in the file
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    try:
        # Use binary mode and count newlines for efficiency
        with open(path, 'rb') as f:
            # Count newlines in chunks to avoid loading the entire file
            line_count = sum(chunk.count(b'\n') for chunk in iter(lambda: f.read(1024 * 1024), b''))
            
        # Check if file ends with a newline - if not and file isn't empty, the last line isn't counted
        with open(path, 'rb') as f:
            try:
                # Check if file is empty
                if path.stat().st_size == 0:
                    return 0
                    
                # Get the last character
                f.seek(-1, os.SEEK_END)
                last_char = f.read(1)
                
                # If file doesn't end with newline, add 1 to count the last line
                if last_char != b'\n':
                    line_count += 1
            except OSError:
                # Handle case where seek might fail (e.g., empty file)
                pass
                
        return line_count
    except Exception as e:
        logger.warning(f"Error counting lines in {path}: {e}")
        return 0


def is_text_file(file_path: Union[str, Path]) -> bool:
    """
    Determine if a file is a text file using multiple heuristics.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file is likely a text file, False otherwise
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    # Check file extension first
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type:
        return mime_type.startswith('text/') or mime_type in (
            'application/json', 'application/xml', 'application/javascript',
            'application/x-python', 'application/x-ruby', 'application/x-sh'
        )
    
    # Common text file extensions
    text_extensions = {
        '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.xml',
        '.yml', '.yaml', '.ini', '.conf', '.cfg', '.sh', '.bash', '.c', '.cpp', 
        '.h', '.hpp', '.java', '.rb', '.pl', '.php', '.rs', '.go', '.swift',
        '.kt', '.kts', '.dart', '.lua', '.ex', '.exs', '.clj', '.scala', '.sql'
    }
    
    if path.suffix.lower() in text_extensions:
        return True
    
    # Try reading the first few KB as UTF-8 as a last resort
    try:
        with open(path, 'rb') as f:
            content = f.read(4096)
            
        # Check for null bytes which are uncommon in text files
        if b'\x00' in content:
            return False
            
        # Try decoding as UTF-8
        try:
            content.decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
    except Exception:
        return False


def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get information about a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with file information
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    try:
        stats = path.stat()
        is_text = is_text_file(path)
        
        info = {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "size_bytes": stats.st_size,
            "is_text": is_text,
            "last_modified": stats.st_mtime,
        }
        
        if is_text:
            info["line_count"] = count_lines_in_file(path)
            
        return info
    except Exception as e:
        logger.warning(f"Error getting file info for {path}: {e}")
        return {"path": str(path), "error": str(e)}


def parallel_process(items: Iterable[T], 
                    process_func: Callable[[T], R], 
                    max_workers: int = None, 
                    show_progress: bool = False) -> List[R]:
    """
    Process items in parallel using a thread pool.
    
    Args:
        items: Items to process
        process_func: Function to apply to each item
        max_workers: Maximum number of worker threads
        show_progress: Whether to show a progress bar
        
    Returns:
        List of results
    """
    items_list = list(items)
    results = []
    
    # Default to a reasonable number of workers if not specified
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 4) + 4)
        
    # Set up progress tracking if requested
    if show_progress:
        from tqdm import tqdm
        pbar = tqdm(total=len(items_list), desc="Processing")
        completed = 0
        lock = threading.Lock()
        
        def update_progress(_):
            nonlocal completed
            with lock:
                completed += 1
                pbar.update(1)
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        if show_progress:
            # Submit all tasks and set up callbacks for progress tracking
            future_to_item = {executor.submit(process_func, item): item for item in items_list}
            
            for future in concurrent.futures.as_completed(future_to_item):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing item: {e}")
                finally:
                    update_progress(future)
            
            pbar.close()
        else:
            # Modified implementation to handle errors individually without stopping the whole process
            futures = []
            for item in items_list:
                futures.append(executor.submit(process_func, item))
                
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in parallel processing: {e}")
    
    return results


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration.
    
    Args:
        verbose: Whether to enable debug logging
        log_file: Path to log file (optional)
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add console handler to root logger
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Unable to create log file at {log_file}: {e}")
    
    # Configure our module logger separately
    module_logger = logging.getLogger("llm_cartographer")
    module_logger.setLevel(log_level)
    
    # Suppress verbose logging from libraries unless in debug mode
    if not verbose:
        for lib_logger_name in ["urllib3", "requests", "asyncio"]:
            logging.getLogger(lib_logger_name).setLevel(logging.WARNING)


def memory_efficient_file_sample(file_path: Union[str, Path], 
                               sample_lines: int = 10, 
                               max_size: int = 5000) -> str:
    """
    Get a sample of a file with memory efficiency in mind.
    Gets the first and last N lines without loading the entire file.
    
    Args:
        file_path: Path to the file
        sample_lines: Number of lines to get from start and end
        max_size: Maximum total sample size in characters
        
    Returns:
        Sample text from the file
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    try:
        # Check if file is small enough to read entirely
        file_size = path.stat().st_size
        if file_size == 0:
            return ""
            
        if file_size < max_size * 2:  # * 2 for safety margin
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(max_size)
                if len(content) <= max_size:
                    return content
                else:
                    return f"{content[:max_size//2]}...\n[content truncated]\n...{content[-max_size//2:]}"
        
        # For larger files, get first and last N lines
        first_lines = []
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in range(sample_lines):
                line = f.readline()
                if not line:
                    break
                first_lines.append(line)
        
        # Use a deque with maxlen to efficiently get the last N lines
        from collections import deque
        last_lines = deque(maxlen=sample_lines)
        
        # Read file in reverse efficiently using seek
        with open(path, 'rb') as f:
            # Move to end of file
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            
            # Start from the end and move backwards
            position = file_size
            line_count = 0
            chunk_size = 4096  # Read in 4KB chunks
            
            # Read chunks from the end until we have enough lines
            while position > 0 and line_count < sample_lines:
                read_size = min(chunk_size, position)
                position -= read_size
                f.seek(position, os.SEEK_SET)
                chunk = f.read(read_size).decode('utf-8', errors='ignore')
                
                # Count lines in the chunk
                lines = chunk.split('\n')
                line_count += len(lines) - 1  # -1 because the last split might not be a complete line
                
                # Add lines to our deque
                for line in reversed(lines):
                    if line:
                        last_lines.appendleft(line)
                    if len(last_lines) >= sample_lines:
                        break
        
        # Combine first and last lines with a clear truncation indicator
        combined = ''.join(first_lines)
        if first_lines and last_lines and len(first_lines) < count_lines_in_file(path):
            combined += '\n...\n[content truncated]\n...\n'
        combined += '\n'.join(last_lines)
        
        return combined
    except Exception as e:
        logger.warning(f"Error getting file sample from {path}: {e}")
        return f"[Error reading file: {str(e)}]"


def check_process_memory_usage() -> Dict[str, float]:
    """
    Check the memory usage of the current process.
    
    Returns:
        Dictionary with memory usage information in MB
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / (1024 * 1024),  # Resident Set Size in MB
            "vms_mb": memory_info.vms / (1024 * 1024),  # Virtual Memory Size in MB
            "percent": process.memory_percent()
        }
    except ImportError:
        logger.debug("psutil not installed, cannot check memory usage")
        return {"error": "psutil not installed"}
    except Exception as e:
        logger.warning(f"Error checking memory usage: {e}")
        return {"error": str(e)}