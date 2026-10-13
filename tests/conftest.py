"""Every test runs against a throwaway data folder.

Loaded by pytest before any test module imports backend, so backend.config
never sees the real DATA_DIR (inside the container that is the live /data).
"""
import os
import tempfile

os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='talkcut-tests-')
