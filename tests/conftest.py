import os
import sys

# Ensure repository root is on sys.path for 'src' package imports
REPO_ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)