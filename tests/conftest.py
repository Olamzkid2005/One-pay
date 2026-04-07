"""
Pytest configuration for OnePay tests.
Sets up the Python path to include the project root.
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
