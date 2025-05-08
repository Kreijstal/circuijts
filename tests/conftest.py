# -*- coding: utf-8 -*-
"""Configuration for pytest."""

import sys
from pathlib import Path

# Add the root directory to Python path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
