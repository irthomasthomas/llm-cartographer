"""Tests for the config module."""

import os
import json
import yaml
from pathlib import Path
import tempfile

import pytest

from llm_cartographer.config import CartographerConfig, ANALYSIS_MODES, DIAGRAM_FORMATS


class TestCartographerConfig:
    def test_default_config(self):
        """Test default configuration values."""
        config = CartographerConfig()
        
        assert config.directory == Path(".")
        assert config.max_files == 100
        assert config.model_name == "gpt-4o"
        assert config.mode == "overview"
        assert config.reasoning == 5
        assert config.visual is False
        assert config.diagram_format == "graphviz"
        assert config.parallel is True
        
    def test_path_normalization(self):
        """Test that paths are properly normalized."""
        config = CartographerConfig(
            directory="./test",
            output_path="./output",
            cache_dir="./cache"
        )
        
        assert isinstance(config.directory, Path)
        assert isinstance(config.output_path, Path)
        assert isinstance(config.cache_dir, Path)
        
    def test_extension_normalization(self):
        """Test that extensions are normalized with dots."""
        config = CartographerConfig(
            filter_extensions={"py", ".js", "ts"}
        )
        
        assert ".py" in config.filter_extensions
        assert ".js" in config.filter_extensions
        assert ".ts" in config.filter_extensions
        assert len(config.filter_extensions) == 3
        
    def test_validation(self):
        """Test configuration validation."""
        # Invalid mode
        with pytest.raises(ValueError, match="Invalid mode"):
            CartographerConfig(mode="invalid")
            
        # Invalid reasoning depth
        with pytest.raises(ValueError, match="Reasoning depth"):
            CartographerConfig(reasoning=10)
            
        # Invalid diagram format
        with pytest.raises(ValueError, match="Invalid diagram format"):
            CartographerConfig(diagram_format="invalid")
            
    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = CartographerConfig(
            directory="./test",
            filter_extensions={".py", ".js"}
        )
        
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["directory"] == str(Path("./test").resolve())
        assert set(config_dict["filter_extensions"]) == {".py", ".js"}
        
    def test_save_and_load_json(self, tmp_path):
        """Test saving and loading config as JSON."""
        config = CartographerConfig(
            directory="./test",
            max_files=200,
            filter_extensions={".py", ".js"}
        )
        
        # Save config
        config_path = tmp_path / "config.json"
        config.save(config_path)
        
        # Check file exists
        assert config_path.exists()
        
        # Load config
        loaded_config = CartographerConfig.load(config_path)
        
        # Check values
        assert loaded_config.max_files == 200
        assert loaded_config.filter_extensions == {".py", ".js"}
        
    def test_save_and_load_yaml(self, tmp_path):
        """Test saving and loading config as YAML."""
        config = CartographerConfig(
            directory="./test",
            max_files=200,
            filter_extensions={".py", ".js"}
        )
        
        # Save config
        config_path = tmp_path / "config.yaml"
        config.save(config_path)
        
        # Check file exists
        assert config_path.exists()
        
        # Load config
        loaded_config = CartographerConfig.load(config_path)
        
        # Check values
        assert loaded_config.max_files == 200
        assert loaded_config.filter_extensions == {".py", ".js"}
        
    def test_from_cli_args(self):
        """Test creating config from CLI args."""
        config = CartographerConfig.from_cli_args(
            directory="./test",
            exclude=["node_modules", ".git"],
            filter_extension=["py", "js"],
            output="output.md",
            visual=True
        )
        
        assert config.directory == Path("./test").resolve()
        assert "node_modules" in config.exclude_patterns
        assert ".git" in config.exclude_patterns
        assert config.filter_extensions == {".py", ".js"}
        assert config.output_path == Path("output.md")
        assert config.visual is True
        
    def test_find_config_file(self, tmp_path):
        """Test finding config file in directory."""
        # Create test directory
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()
        
        # No config file
        config = CartographerConfig(directory=test_dir)
        assert config.find_config_file() is None
        
        # Create JSON config
        json_config = test_dir / ".llm-cartographer.json"
        json_config.write_text("{}")
        
        assert config.find_config_file() == json_config
        
        # Create YAML config (should still find JSON first)
        yaml_config = test_dir / ".llm-cartographer.yaml"
        yaml_config.write_text("---\n")
        
        assert config.find_config_file() == json_config
        
        # Remove JSON config, should find YAML
        json_config.unlink()
        assert config.find_config_file() == yaml_config
