"""Test-wide setup.

The API writes drafts, the document store and the audit trail under
RUNTIME_DIR. Left alone, the suite would write into Backend/api/runtime —
the same place a local run keeps its real drafts and audit trail — so every
test session gets a throwaway directory instead. It has to be set before
``utils.paths`` is first imported, which is why it happens here, at
collection time, rather than in a fixture.
"""

from __future__ import annotations

import os
import shutil
import tempfile

_RUNTIME = tempfile.mkdtemp(prefix="regrep-tests-")
os.environ["RUNTIME_DIR"] = _RUNTIME


def pytest_unconfigure(config):
    shutil.rmtree(_RUNTIME, ignore_errors=True)
