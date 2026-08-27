"""Regression tests for atomic kestrel_database.csv writes.

The analysis pipeline calls ``save_database`` after every processed image while
the UI auto-refresh timer reads the same path (``read_kestrel_csv`` /
``apply_normalization``). A non-atomic ``DataFrame.to_csv(path)`` truncates the
destination and streams rows into it, so a concurrent reader can observe a
partial file and raise ``EmptyDataError`` or ``ParserError``.
"""

import errno
import os
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kestrel_analyzer import database as _dbmod
from kestrel_analyzer.database import (
    _to_csv_atomic,
    read_database_csv,
    save_database,
)

pytestmark = pytest.mark.unit


def _frame(rows: int = 2000) -> pd.DataFrame:
    """A frame whose quoted fields span commas, so truncation lands mid-string."""
    return pd.DataFrame(
        {
            "filename": [f"DSC_{i:04d}.NEF" for i in range(rows)],
            "quality": [0.5] * rows,
            "species": ["Northern Cardinal, adult male"] * rows,
            "crops_json": ['[{"x": 1, "y": 2, "label": "bird, perched"}]'] * rows,
        }
    )


class TestAtomicCsvWrite:
    def test_output_is_byte_identical_to_plain_to_csv(self, tmp_path):
        """The atomic path must not change the file pandas would have written."""
        df = _frame(50)
        plain = tmp_path / "plain.csv"
        atomic = tmp_path / "atomic.csv"

        df.to_csv(plain, index=False)
        _to_csv_atomic(df, str(atomic))

        assert atomic.read_bytes() == plain.read_bytes()

    def test_no_temp_files_left_behind(self, tmp_path):
        df = _frame(50)
        _to_csv_atomic(df, str(tmp_path / "kestrel_database.csv"))

        assert [p.name for p in tmp_path.iterdir()] == ["kestrel_database.csv"]

    def test_existing_file_survives_a_failed_write(self, tmp_path):
        """A write that raises must leave the previous database intact."""
        db_path = tmp_path / "kestrel_database.csv"
        _to_csv_atomic(_frame(10), str(db_path))
        good = db_path.read_bytes()

        class Exploding(pd.DataFrame):
            def to_csv(self, *a, **kw):
                raise OSError("disk full")

        with pytest.raises(OSError):
            _to_csv_atomic(Exploding(_frame(10)), str(db_path))

        assert db_path.read_bytes() == good
        assert [p.name for p in tmp_path.iterdir()] == ["kestrel_database.csv"]

    def test_concurrent_reads_never_see_a_partial_file(self, tmp_path):
        """Reproduces the production race: pipeline saves while the UI reads.

        Against the pre-fix ``database.to_csv(db_path, index=False)`` this fails
        within a few hundred milliseconds with the two signatures seen in crash
        reports: ``No columns to parse from file`` and ``EOF inside string``.

        The reader goes through ``read_database_csv`` because that is what every
        reader in the app uses. On Windows the atomic write guarantees
        all-or-nothing content but not a collision-free ``open()``: a reader can
        still catch the destination mid-rename and get ``PermissionError``, which
        both sides absorb by retrying. A bare ``pd.read_csv`` here would be
        testing a call path the app does not have.

        The reader pauses briefly between reads to model the UI's auto-refresh
        timer. A zero-gap reopen loop can starve the writer past its retry window
        on Windows — see ``retry_on_file_lock`` — which is an artifact of the
        test harness rather than a race the app can hit.
        """
        db_path = str(tmp_path / "kestrel_database.csv")
        df = _frame()
        save_database(df, db_path)

        stop = threading.Event()
        errors = []
        reads = []
        write_errors = []

        def writer():
            while not stop.is_set():
                try:
                    save_database(df, db_path)
                except Exception as exc:  # noqa: BLE001 - recording for assert
                    write_errors.append(f"{type(exc).__name__}: {exc}")

        def reader():
            while not stop.is_set():
                try:
                    reads.append(len(read_database_csv(db_path)))
                except Exception as exc:  # noqa: BLE001 - recording for assert
                    errors.append(f"{type(exc).__name__}: {exc}")
                stop.wait(0.01)  # poll like the UI timer, don't spin

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        stop.wait(3.0)
        stop.set()
        for t in threads:
            t.join()

        assert not errors, f"{len(errors)} partial read(s), e.g. {errors[0]}"
        # A save that raises is a silently lost write — the failure mode the
        # writer-side retry exists to close.
        assert not write_errors, (
            f"{len(write_errors)} dropped save(s), e.g. {write_errors[0]}"
        )
        assert reads, "reader never completed a read"
        # Every successful read must see the whole database, never a prefix.
        assert set(reads) == {len(df)}

    def test_no_temp_files_survive_concurrent_saves(self, tmp_path):
        """Parallel saves each get a unique mkstemp path and clean up after."""
        db_path = str(tmp_path / "kestrel_database.csv")
        df = _frame(200)

        threads = [
            threading.Thread(target=lambda: [save_database(df, db_path) for _ in range(5)])
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(os.listdir(tmp_path)) == ["kestrel_database.csv"]
        assert len(pd.read_csv(db_path)) == len(df)

    def test_flush_error_does_not_replace_existing(self, tmp_path, monkeypatch):
        """ENOSPC on flush must not promote a partial temp over the last good file."""
        db_path = tmp_path / "kestrel_database.csv"
        _to_csv_atomic(_frame(10), str(db_path))
        good = db_path.read_bytes()
        real_fdopen = _dbmod.os.fdopen

        class FlushBoom:
            """Delegates to the real fdopen file; flush is not assignable on TextIOWrapper.

            pandas ``to_csv(file)`` uses more than ``write`` (encoding, newline,
            writelines, …), so unknown attributes forward to the real handle.
            """

            def __init__(self, real):
                self._real = real

            def flush(self):
                raise OSError(errno.ENOSPC, "No space left on device")

            def __getattr__(self, name):
                return getattr(self._real, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self._real.close()
                return False

        def wrapping_fdopen(*a, **k):
            return FlushBoom(real_fdopen(*a, **k))

        monkeypatch.setattr(_dbmod.os, "fdopen", wrapping_fdopen)
        with pytest.raises(OSError):
            _to_csv_atomic(_frame(10), str(db_path))
        assert db_path.read_bytes() == good
        assert [p.name for p in tmp_path.iterdir()] == ["kestrel_database.csv"]

    def test_fsync_error_still_replaces(self, tmp_path, monkeypatch):
        """Network-FS fsync failures are ignored; the flushed temp still replaces."""

        def boom_fsync(_fd):
            raise OSError(errno.EINVAL, "Operation not supported")

        monkeypatch.setattr(_dbmod.os, "fsync", boom_fsync)
        db_path = tmp_path / "kestrel_database.csv"
        _to_csv_atomic(_frame(5), str(db_path))
        assert db_path.exists()
        assert len(pd.read_csv(db_path)) == 5

    def test_fdopen_failure_closes_tmp_and_leaves_existing(self, tmp_path, monkeypatch):
        """If fdopen fails, close the mkstemp fd so Windows can unlink the temp."""
        db_path = tmp_path / "kestrel_database.csv"
        _to_csv_atomic(_frame(10), str(db_path))
        good = db_path.read_bytes()

        def boom_fdopen(*_a, **_k):
            raise OSError("fdopen failed")

        monkeypatch.setattr(_dbmod.os, "fdopen", boom_fdopen)
        with pytest.raises(OSError, match="fdopen failed"):
            _to_csv_atomic(_frame(10), str(db_path))
        assert db_path.read_bytes() == good
        assert [p.name for p in tmp_path.iterdir()] == ["kestrel_database.csv"]
