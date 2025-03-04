#!/usr/bin/env python

import argparse
import sys
from pathlib import Path
from typing import Optional

from llm_cartographer.codebase_navigator import CodebaseNavigator
from llm_cartographer import CodebaseCartographer

def main():
    """Command line interface for the CodebaseNavigator."""
    parser = argparse.ArgumentParser(
        description="Generate an LLM-optimized navigation map of a codebase"
    )
    
    parser.add_argument("directory", help="Directory to analyze")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--format", "-f", choices=["markdown", "json", "compact"], 
                      default="markdown", help="Output format")
    parser.add_argument("--include-source", "-s", action="store_true",
                      help="Include source code snippets for functions and methods in the output")
    parser.add_argument("--max-files", type=int, default=100,
                      help="Maximum number of files to analyze")
    parser.add_argument("--focus", help="Focus on a specific subdirectory")
    
    args = parser.parse_args()
    
    try:
        # Create a cartographer to collect data
        cartographer = CodebaseCartographer(
            directory=args.directory,
            max_files=args.max_files,
            focus=args.focus
        )
        
        # Scan the codebase
        print(f"Scanning directory: {args.directory}")
        collected_data = cartographer.scan_directory()
        
        # Create the navigator
        focus_dir = cartographer.focus_dir if cartographer.focus else None
        navigator = CodebaseNavigator(
            directory=Path(args.directory),
            collected_data=collected_data,
            focus=focus_dir,
            include_source=args.include_source
        )
        
        # Generate the output
        print("Generating navigation map...")
        output = navigator.generate_llm_output(format=args.format)
        
        # Save or print the output
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Navigation map saved to: {args.output}")
        else:
            print("\n" + "=" * 80)
            print(output)
            print("=" * 80)
            
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
