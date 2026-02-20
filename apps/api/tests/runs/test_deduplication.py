"""Unit tests for proposal deduplication helpers in service.py."""

import uuid
from unittest.mock import MagicMock, patch


class TestBuildSeenSignatures:
    """Tests for _build_seen_signatures() in service.py."""

    def _call(self, rows, repo_id=None):
        """Call _build_seen_signatures with a mocked DB that returns `rows`."""
        from app.runs.service import _build_seen_signatures

        repo_id = repo_id or uuid.uuid4()
        mock_execute_result = MagicMock()
        mock_execute_result.all.return_value = rows
        mock_session = MagicMock()
        mock_session.execute.return_value = mock_execute_result

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("app.runs.service.get_sync_db", return_value=mock_ctx):
            return _build_seen_signatures(repo_id)

    def test_empty_table_returns_empty_frozenset(self):
        result = self._call(rows=[])
        assert result == frozenset()

    def test_location_with_line_numbers_is_normalized(self):
        row = MagicMock()
        row.type = "performance"
        row.location = "src/api/handler.ts:42-56"
        result = self._call(rows=[row])
        assert ("performance", "src/api/handler.ts") in result

    def test_location_without_line_numbers_is_kept_as_is(self):
        row = MagicMock()
        row.type = "tech_debt"
        row.location = "src/utils.py"
        result = self._call(rows=[row])
        assert ("tech_debt", "src/utils.py") in result

    def test_location_with_single_line_number_is_normalized(self):
        row = MagicMock()
        row.type = "security"
        row.location = "app/auth.py:10"
        result = self._call(rows=[row])
        assert ("security", "app/auth.py") in result

    def test_none_location_is_skipped(self):
        row = MagicMock()
        row.type = "performance"
        row.location = None
        result = self._call(rows=[row])
        assert result == frozenset()

    def test_multiple_rows_produce_multiple_signatures(self):
        rows = []
        for i, (t, loc) in enumerate([
            ("performance", "src/a.ts:1"),
            ("tech_debt", "src/b.ts:5-10"),
            ("security", "src/c.py"),
        ]):
            r = MagicMock()
            r.type = t
            r.location = loc
            rows.append(r)
        result = self._call(rows=rows)
        assert ("performance", "src/a.ts") in result
        assert ("tech_debt", "src/b.ts") in result
        assert ("security", "src/c.py") in result
        assert len(result) == 3

    def test_duplicate_normalized_signatures_are_collapsed(self):
        """Two rows with the same type + file (different line numbers) → one entry."""
        rows = []
        for loc in ["src/a.ts:1-5", "src/a.ts:10-20"]:
            r = MagicMock()
            r.type = "performance"
            r.location = loc
            rows.append(r)
        result = self._call(rows=rows)
        assert len(result) == 1
        assert ("performance", "src/a.ts") in result

    def test_returns_frozenset(self):
        result = self._call(rows=[])
        assert isinstance(result, frozenset)
