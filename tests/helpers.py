from __future__ import annotations

import shutil
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


@contextmanager
def workspace_temp_dir() -> Iterator[str]:
    root = Path.cwd() / ".tmp-tests"
    root.mkdir(exist_ok=True)
    path = root / f"case-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)
