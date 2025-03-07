"""Tests for the utils module."""

import os
import time
import tempfile
import threading
from pathlib import Path
from unittest import mock

import pytest

from llm_cartographer.utils import (
    safe_read_file,
    count_lines_in_file,
    is_text_file,
    Timer,
    parallel_process,
    memory_efficient_file_sample,
    check_process_memory_usage
)


class TestSafeReadFile:
    def test_read_small_file(self, tmp_path):
        """Test reading a small file within max size."""
        test_file = tmp_path / "small.txt"
        content = "This is a test file.\nWith two lines."
        test_file.write_text(content)
        
        result = safe_read_file(test_file)
        assert result == content
        
        # Test with max_size larger than file
        result = safe_read_file(test_file, max_size=100)
        assert result == content
    
    def test_read_large_file_truncated(self, tmp_path):
        """Test reading a large file is truncated."""
        test_file = tmp_path / "large.txt"
        # Create a file with 1000 lines
        content = "".join(f"Line {i}\n" for i in range(1000))
        test_file.write_text(content)
        
        # Set max_size to only read first 100 bytes
        result = safe_read_file(test_file, max_size=100)
        assert len(result) == 100
        assert result.startswith("Line 0")
    
    def test_read_file_with_errors(self, tmp_path):
        """Test handling of read errors."""
        test_file = tmp_path / "nonexistent.txt"
        
        with mock.patch("builtins.open", side_effect=IOError("Test error")):
            result = safe_read_file(test_file)
            assert "Error reading file" in result


class TestCountLinesInFile:
    def test_count_lines_simple(self, tmp_path):
        """Test counting lines in a simple file."""
        test_file = tmp_path / "lines.txt"
        lines = ["Line 1\n", "Line 2\n", "Line 3\n"]
        test_file.write_text("".join(lines))
        
        result = count_lines_in_file(test_file)
        assert result == 3
    
    def test_count_lines_empty_file(self, tmp_path):
        """Test counting lines in an empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        result = count_lines_in_file(test_file)
        assert result == 0
    
    def test_count_lines_no_newline_at_end(self, tmp_path):
        """Test counting lines in a file with no trailing newline."""
        test_file = tmp_path / "no_final_newline.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3")
        
        result = count_lines_in_file(test_file)
        assert result == 3
    
    def test_count_lines_error_handling(self, tmp_path):
        """Test error handling when counting lines."""
        test_file = tmp_path / "nonexistent.txt"
        
        with mock.patch("builtins.open", side_effect=IOError("Test error")):
            result = count_lines_in_file(test_file)
            assert result == 0


class TestIsTextFile:
    def test_text_file_by_extension(self, tmp_path):
        """Test detecting text files by extension."""
        extensions = [".py", ".js", ".txt", ".md", ".json", ".html", ".css"]
        
        for ext in extensions:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("Sample content")
            assert is_text_file(test_file) is True
    
    def test_binary_file_by_content(self, tmp_path):
        """Test detecting binary files by content."""
        test_file = tmp_path / "binary.bin"
        
        # Write some binary data with null bytes
        with open(test_file, "wb") as f:
            f.write(b"Binary\x00Data")
        
        assert is_text_file(test_file) is False


class TestTimer:
    def test_timer_duration(self):
        """Test that Timer correctly measures duration."""
        with Timer("Test timer", verbose=False) as timer:
            time.sleep(0.1)
        
        # Duration should be approximately 0.1 seconds
        assert 0.05 < timer.duration < 0.3
    
    def test_timer_with_name(self):
        """Test that Timer works with a name."""
        with mock.patch("logging.Logger.info") as mock_info:
            with Timer("Named timer") as timer:
                time.sleep(0.01)
        
        # Check that log message contains the timer name
        mock_info.assert_called_once()
        assert "Named timer" in mock_info.call_args[0][0]


class TestParallelProcess:
    def test_parallel_process_simple(self):
        """Test parallel processing of a simple function."""
        def square(x):
            return x * x
        
        items = [1, 2, 3, 4, 5]
        results = parallel_process(items, square)
        
        assert sorted(results) == [1, 4, 9, 16, 25]
    
    def test_parallel_process_with_progress(self):
        """Test parallel processing with progress tracking."""
        def slow_square(x):
            time.sleep(0.01)
            return x * x
        
        items = [1, 2, 3]
        with mock.patch("tqdm.tqdm") as mock_tqdm:
            results = parallel_process(items, slow_square, show_progress=True)
        
        assert sorted(results) == [1, 4, 9]
        mock_tqdm.assert_called_once()
    
    def test_parallel_process_with_error(self):
        """Test parallel processing handling errors."""
        def failing_function(x):
            if x == 3:
                raise ValueError("Test error")
            return x * x
        
        items = [1, 2, 3, 4]
        with mock.patch("logging.Logger.error") as mock_error:
            results = parallel_process(items, failing_function)
        
        # Should get results for non-failing items
        assert 1 in results
        assert 4 in results
        assert 16 in results
        
        # Should log error
        mock_error.assert_called_once()


class TestMemoryEfficientFileSample:
    def test_sample_small_file(self, tmp_path):
        """Test sampling a small file that's read entirely."""
        test_file = tmp_path / "small.txt"
        content = "Line 1\nLine 2\nLine 3\n"
        test_file.write_text(content)
        
        result = memory_efficient_file_sample(test_file)
        assert result == content
    
    def test_sample_large_file(self, tmp_path):
        """Test sampling a large file with first and last lines."""
        test_file = tmp_path / "large.txt"
        
        # Create a file with many lines
        with open(test_file, "w") as f:
            for i in range(100):
                f.write(f"Line {i}\n")
        
        result = memory_efficient_file_sample(test_file, sample_lines=5)
        
        # Should contain first 5 lines
        for i in range(5):
            assert f"Line {i}" in result
            
        # Should contain last 5 lines
        for i in range(95, 100):
            assert f"Line {i}" in result
            
        # Should have truncation indicator
        assert "[content truncated]" in result


class TestCheckProcessMemoryUsage:
    def test_memory_usage_returns_dict(self):
        """Test that memory usage check returns a dictionary."""
        try:
            import psutil
            result = check_process_memory_usage()
            assert isinstance(result, dict)
            assert "rss_mb" in result
            assert "vms_mb" in result
            assert "percent" in result
            
            # RSS and VMS should be positive
            assert result["rss_mb"] > 0
            assert result["vms_mb"] > 0
            
        except ImportError:
            # If psutil is not installed
            result = check_process_memory_usage()
            assert "error" in result
            assert "psutil not installed" in result["error"]
