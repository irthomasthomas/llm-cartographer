"""Tests for memory efficiency improvements."""

import os
import tempfile
import json
import hashlib
from pathlib import Path
import pytest
from unittest import mock

from llm_cartographer import CodebaseCartographer
from llm_cartographer.utils import check_process_memory_usage


class TestMemoryEfficiency:
    @pytest.fixture
    def mock_llm_model(self):
        """Create a mock LLM model."""
        mock_model = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.text.return_value = "<overview>Test overview</overview>"
        mock_model.prompt.return_value = mock_response
        return mock_model
    
    @pytest.fixture
    def test_project_dir(self, tmp_path):
        """Create a test project directory with files."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # Create some Python files
        for i in range(10):
            file_path = project_dir / f"file_{i}.py"
            file_path.write_text(f"# Test file {i}\ndef function_{i}():\n    return {i}\n")
        
        # Create a README
        readme = project_dir / "README.md"
        readme.write_text("# Test Project\nThis is a test project.")
        
        return project_dir
    
    def test_memory_efficient_hashing(self, test_project_dir, mock_llm_model):
        """Test that the memory-efficient hashing works."""
        with mock.patch("llm.get_model", return_value=mock_llm_model):
            cartographer = CodebaseCartographer(
                directory=str(test_project_dir),
                max_files=5,
                verbose=True
            )
            
            # Fill collected_data with some test data
            cartographer.collected_data = {
                "project_info": {"name": "Test Project"},
                "statistics": {"total_files": 10, "analyzed_files": 5},
                "language_stats": {"Python": {"files": 5, "percentage": 100}},
                "important_files": {"README.md": {"language": "Markdown", "sample": "# Test Project"}},
                "file_samples": {}
            }
            
            # Mock the entire md5 class instead of just the update method
            mock_md5 = mock.MagicMock()
            mock_md5.hexdigest.return_value = "mock_hash_value"
            
            with mock.patch("hashlib.md5", return_value=mock_md5):
                # Call generate_map which should use memory-efficient hashing
                cartographer.generate_map()
                
                # Check that md5 was instantiated and updated
                assert mock_md5.update.called, "md5 update should have been called"
    
    def test_memory_usage_tracking(self, test_project_dir, mock_llm_model):
        """Test that memory usage is tracked when verbose is enabled."""
        with mock.patch("llm.get_model", return_value=mock_llm_model), \
             mock.patch("llm_cartographer.utils.check_process_memory_usage") as mock_check:
            
            mock_check.return_value = {"rss_mb": 100, "vms_mb": 200, "percent": 5}
            
            cartographer = CodebaseCartographer(
                directory=str(test_project_dir),
                max_files=5,
                verbose=True
            )
            
            # Mock the scan_directory to avoid actual scanning
            cartographer.scan_directory = mock.MagicMock()
            cartographer.scan_directory.return_value = {}
            
            # Call analyze_codebase which should track memory usage
            cartographer.analyze_codebase()
            
            # Check if memory usage was tracked
            mock_check.assert_called()
    
    def test_large_file_handling(self, tmp_path, mock_llm_model):
        """Test that large files are handled efficiently."""
        project_dir = tmp_path / "large_file_project"
        project_dir.mkdir()
        
        # Create a large file
        large_file = project_dir / "large.txt"
        with open(large_file, "w") as f:
            for i in range(10000):  # 10K lines
                f.write(f"Line {i} with some content to make it longer\n")
        
        with mock.patch("llm.get_model", return_value=mock_llm_model):
            cartographer = CodebaseCartographer(
                directory=str(project_dir),
                max_files=1,
                max_file_size=1024 * 10,  # 10KB
                verbose=True
            )
            
            # Mock the scan_directory to avoid full scanning
            original_analyze_file = cartographer.analyze_file
            
            # Track memory usage before and after file analysis
            memory_before = None
            memory_after = None
            
            def mock_analyze_file(file_path):
                nonlocal memory_before, memory_after
                try:
                    import psutil
                    memory_before = psutil.Process(os.getpid()).memory_info().rss
                    result = original_analyze_file(file_path)
                    memory_after = psutil.Process(os.getpid()).memory_info().rss
                    return result
                except ImportError:
                    return original_analyze_file(file_path)
            
            cartographer.analyze_file = mock_analyze_file
            
            # Analyze just the large file
            cartographer.analyze_file(large_file)
            
            # Check if file was analyzed efficiently (if psutil is available)
            if memory_before is not None and memory_after is not None:
                # Memory increase should be less than the file size
                memory_increase_mb = (memory_after - memory_before) / (1024 * 1024)
                file_size_mb = os.path.getsize(large_file) / (1024 * 1024)
                
                # Memory increase should be much less than the file size
                # since we're reading efficiently
                assert memory_increase_mb < file_size_mb / 2, \
                    f"Memory increase ({memory_increase_mb}MB) too large compared to file size ({file_size_mb}MB)"
