import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest import mock

# Import directly from the module file
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
from llm_cartographer import CodebaseCartographer

def test_analysis_modes():
    """Test that different analysis modes work correctly."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        
        # Create a README
        (tempdir_path / "README.md").write_text("# Test Project\nThis is a test project.")
        
        # Mock the LLM model
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = "<overview>Test overview</overview>"
        
        # Test different modes
        for mode in ["overview", "components", "architecture", "flows"]:
            with mock.patch('llm.get_model', return_value=mock_model):
                cartographer = CodebaseCartographer(
                    directory=tempdir,
                    max_files=3,
                    mode=mode
                )
                
                # Run scan_directory
                cartographer.scan_directory()
                
                # Generate the map
                codebase_map = cartographer.generate_map()
                
                # Check that the mode is in the map
                assert f"Analysis mode: {mode}" in codebase_map
                
                # Verify analysis call includes mode-specific prompt
                cartographer.analyze_codebase()
                
                # Check that the model was called with the correct mode info
                called_args = mock_model.prompt.call_args[0][0]
                assert mode in called_args

def test_focus_subdirectory():
    """Test focusing on a subdirectory."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        
        # Create main files
        (tempdir_path / "README.md").write_text("# Main Project\nThis is the main project.")
        (tempdir_path / "main.py").write_text("print('Main script')")
        
        # Create a subdirectory with files
        os.makedirs(tempdir_path / "subdir")
        (tempdir_path / "subdir" / "README.md").write_text("# Submodule\nThis is a submodule.")
        (tempdir_path / "subdir" / "submodule.py").write_text("print('Submodule code')")
        
        # Mock the LLM model
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = "<overview>Test overview</overview>"
        
        # Test with focus on subdirectory
        with mock.patch('llm.get_model', return_value=mock_model):
            cartographer = CodebaseCartographer(
                directory=tempdir,
                max_files=5,
                focus="subdir"
            )
            
            # Run scan_directory
            cartographer.scan_directory()
            
            # Check that the focus information is stored
            assert "focus" in cartographer.collected_data["project_info"]
            assert cartographer.collected_data["project_info"]["focus"] == "subdir"
            
            # Check that the files from the subdirectory are analyzed
            all_analyzed_files = list(cartographer.collected_data["important_files"].keys()) + \
                               list(cartographer.collected_data["file_samples"].keys())
                               
            # Should find the subdir/README.md and subdir/submodule.py
            assert any("submodule.py" in file for file in all_analyzed_files)
            
            # Generate the map
            codebase_map = cartographer.generate_map()
            
            # Check that focus is in the map
            assert "Focus: subdir" in codebase_map

def test_reasoning_depth():
    """Test different reasoning depth levels."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Create a simple project structure
        tempdir_path = Path(tempdir)
        (tempdir_path / "test.py").write_text("print('Hello world')")
        
        # Mock the LLM model
        mock_model = mock.MagicMock()
        mock_model.prompt.return_value.text.return_value = "<overview>Test overview</overview>"
        
        # Test with different reasoning depths
        with mock.patch('llm.get_model', return_value=mock_model):
            for depth in [0, 5, 9]:
                cartographer = CodebaseCartographer(
                    directory=tempdir,
                    max_files=3,
                    reasoning=depth
                )
                
                # Run scan_directory
                cartographer.scan_directory()
                
                # Generate the map
                codebase_map = cartographer.generate_map()
                
                # Check that the reasoning depth is in the map
                assert f"Reasoning depth: {depth}" in codebase_map
                
                # Verify analysis call includes reasoning-specific instructions
                cartographer.analyze_codebase()
                
                # Check that the system prompt contains reasoning depth info
                system_arg = mock_model.prompt.call_args[1]["system"]
                assert "Reasoning depth:" in system_arg

def test_invalid_parameters():
    """Test handling of invalid parameters."""
    with tempfile.TemporaryDirectory() as tempdir:
        # Test invalid mode
        with pytest.raises(ValueError, match="Mode 'invalid' not recognized"):
            CodebaseCartographer(
                directory=tempdir,
                mode="invalid"
            )
        
        # Test invalid reasoning depth
        with pytest.raises(ValueError, match="Reasoning depth must be between 0 and 9"):
            CodebaseCartographer(
                directory=tempdir,
                reasoning=10
            )
        
        # Test invalid focus directory
        with pytest.raises(ValueError, match="Focus directory 'nonexistent' does not exist"):
            CodebaseCartographer(
                directory=tempdir,
                focus="nonexistent"
            )
