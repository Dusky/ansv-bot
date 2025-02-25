#!/usr/bin/env python3
"""
NLTK Resource Downloader

This script downloads required NLTK resources for TTS functionality.
Run this script if you encounter NLTK resource errors.
"""

import nltk
import os
import sys

def main():
    print("Installing NLTK resources for TTS...")
    
    # Create nltk_data directory in the project directory
    nltk_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'nltk_data')
    os.makedirs(nltk_dir, exist_ok=True)
    nltk.data.path.append(nltk_dir)
    
    # Download 'punkt' tokenizer
    try:
        nltk.download('punkt', download_dir=nltk_dir)
        print(f"✅ Successfully installed 'punkt' to {nltk_dir}")
    except Exception as e:
        print(f"⚠️ Error installing 'punkt': {e}")
        sys.exit(1)
    
    # Check if installation was successful
    try:
        from nltk.tokenize import sent_tokenize
        test = sent_tokenize("This is a test. It should split into two sentences.")
        assert len(test) == 2, "Tokenization failed"
        print("✅ NLTK punkt is working correctly")
    except Exception as e:
        print(f"⚠️ NLTK punkt installation was unsuccessful: {e}")
        sys.exit(1)
    
    print("\nNLTK resources are properly installed!")

if __name__ == "__main__":
    main() 