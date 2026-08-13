"""Put the Day62 ``src/`` directory on the import path for the test suite."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
