import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# run qt headless everywhere; the package resolves via pyproject pythonpath
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
