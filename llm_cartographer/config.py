"""Configuration handling for llm-cartographer."""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("llm_cartographer")

# Default exclusion patterns
DEFAULT_EXCLUDE_PATTERNS = [
    "node_modules", ".git", "__pycache__", "*.pyc", "*.pyo", "*.pyd", 
    "*.so", "*.dll", "*.exe", "*.bin", "*.obj", "*.o", "*.a", "*.lib", 
    "*.dylib", "*.ncb", "*.sdf", "*.suo", "*.pdb", "*.idb", "venv", 
    "env", ".env", ".venv", ".pytest_cache", ".mypy_cache", ".ruff_cache", 
    "build", "dist", "*.egg-info", "*.egg", ".tox", ".nox", ".coverage",
    ".DS_Store", "*.min.js", "*.min.css", "*.map", "package-lock.json",
    "yarn.lock", ".vscode", ".idea", "*.swp", "*.swo", ".ipynb_checkpoints",
    "debug", "target", "vendor"
]

# Maximum file size in bytes (default 100KB)
DEFAULT_MAX_FILE_SIZE = 100 * 1024

# Extensions to consider as text files
DEFAULT_TEXT_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.rb', '.php', '.html', '.htm', '.css', '.scss', 
    '.sass', '.less', '.md', '.rst', '.txt', '.yaml', '.yml', '.toml', '.ini',
    '.json', '.xml', '.sh', '.bat', '.ps1', '.R', '.kt', '.swift', '.m', 
    '.mm', '.pl', '.pm', '.sql', '.graphql', '.lua', '.ex', '.exs', '.erl',
    '.elm', '.clj', '.scala', '.dart', '.vue', '.svelte', '.sol', '.pde',
    '.proto', '.groovy', '.jl', '.cf', '.tf', '.kt', '.kts'
}

# Analysis modes with descriptions
ANALYSIS_MODES = {
    "overview": "Provide a high-level overview of the codebase structure and purpose",
    "components": "Focus on identifying and explaining the main components and modules",
    "architecture": "Analyze the architectural patterns and system organization",
    "flows": "Identify key data and control flows through the system"
}

# Diagram formats
DIAGRAM_FORMATS = ["graphviz", "mermaid", "plantuml"]

@dataclass
class CartographerConfig:
    """Configuration for CodebaseCartographer."""
    
    # Basic settings
    directory: Path = field(default_factory=lambda: Path("."))
    exclude_patterns: List[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    max_files: int = 100
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    max_map_tokens: int = 6000
    output_path: Optional[Path] = None
    model_name: str = "gpt-4o"
    follow_symlinks: bool = False
    cache_dir: Path = field(default_factory=lambda: Path(os.path.expanduser("~/.cache/llm-cartographer")))
    
    # Output formats
    json_format: bool = False
    
    # File filtering
    filter_extensions: Optional[Set[str]] = None
    
    # Analysis options
    mode: str = "overview"
    focus: Optional[str] = None
    reasoning: int = 5
    
    # Visualization options
    visual: bool = False
    diagram_format: str = "graphviz"
    
    # Processing options
    parallel: bool = True
    max_workers: Optional[int] = None
    
    # Debug options
    verbose: bool = False
    log_file: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize configuration after initialization."""
        # Convert string paths to Path objects
        if isinstance(self.directory, str):
            self.directory = Path(self.directory).resolve()
        
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
            
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
            
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate mode
        if self.mode not in ANALYSIS_MODES:
            raise ValueError(f"Invalid mode: {self.mode}. Must be one of: {', '.join(ANALYSIS_MODES.keys())}")
            
        # Validate reasoning depth
        if not 0 <= self.reasoning <= 9:
            raise ValueError(f"Reasoning depth must be between 0 and 9, got {self.reasoning}")
            
        # Validate diagram format
        if self.diagram_format not in DIAGRAM_FORMATS:
            raise ValueError(f"Invalid diagram format: {self.diagram_format}. Must be one of: {', '.join(DIAGRAM_FORMATS)}")
            
        # Set default max_workers if not specified
        if self.max_workers is None:
            import os
            self.max_workers = min(32, (os.cpu_count() or 4) + 4)
            
        # Normalize filter_extensions
        if self.filter_extensions:
            # Ensure all extensions start with a dot
            self.filter_extensions = {
                ext if ext.startswith('.') else f'.{ext}' 
                for ext in self.filter_extensions
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary, converting Path objects to strings."""
        config_dict = asdict(self)
        
        # Convert Path objects to strings
        for key, value in config_dict.items():
            if isinstance(value, Path):
                config_dict[key] = str(value)
            elif isinstance(value, set):
                config_dict[key] = list(value) if value else None
                
        return config_dict
    
    def save(self, path: Union[str, Path]) -> None:
        """Save configuration to a file."""
        config_path = Path(path) if isinstance(path, str) else path
        
        try:
            config_dict = self.to_dict()
            
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(config_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False)
            else:
                # Default to JSON
                with open(config_path, 'w') as f:
                    json.dump(config_dict, f, indent=2)
                    
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving configuration to {config_path}: {e}")
            raise
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'CartographerConfig':
        """Create a configuration from a dictionary."""
        # Make a copy to avoid modifying the original
        config = config_dict.copy()
        
        # Convert string paths to Path objects
        for key in ['directory', 'output_path', 'cache_dir']:
            if key in config and config[key] is not None:
                config[key] = Path(config[key])
                
        # Convert list back to set if needed
        if 'filter_extensions' in config and config['filter_extensions']:
            config['filter_extensions'] = set(config['filter_extensions'])
            
        return cls(**config)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'CartographerConfig':
        """Load configuration from a file."""
        config_path = Path(path) if isinstance(path, str) else path
        
        try:
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
                
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(config_path, 'r') as f:
                    config_dict = yaml.safe_load(f)
            else:
                # Default to JSON
                with open(config_path, 'r') as f:
                    config_dict = json.load(f)
                    
            logger.info(f"Configuration loaded from {config_path}")
            return cls.from_dict(config_dict)
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            raise
    
    @classmethod
    def from_cli_args(cls, **kwargs) -> 'CartographerConfig':
        """Create configuration from command-line arguments."""
        # Filter out None values to allow defaults to take effect
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        # Special handling for extensions
        if 'filter_extension' in filtered_kwargs:
            extensions = filtered_kwargs.pop('filter_extension')
            if extensions:
                filtered_kwargs['filter_extensions'] = {
                    ext if ext.startswith('.') else f'.{ext}' 
                    for ext in extensions
                }
        
        # Special handling for exclude patterns
        if 'exclude' in filtered_kwargs:
            filtered_kwargs['exclude_patterns'] = filtered_kwargs.pop('exclude')
            
        # Special handling for output
        if 'output' in filtered_kwargs:
            filtered_kwargs['output_path'] = filtered_kwargs.pop('output')
            
        return cls(**filtered_kwargs)
    
    def find_config_file(self) -> Optional[Path]:
        """Find a configuration file in the project directory."""
        config_names = [
            '.llm-cartographer.json',
            '.llm-cartographer.yaml',
            '.llm-cartographer.yml',
        ]
        
        for name in config_names:
            config_path = self.directory / name
            if config_path.exists():
                return config_path
        
        return None
