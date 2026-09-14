"""Day91 deterministic tests for signed, revision-bound Tool cursors."""
import unittest

from mcp_server_inventory import InvalidInventoryCursor, ToolInventoryPaginator


class Day91ToolInventoryPaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paginator = ToolInventoryPaginator(
            secret=b"day91-unit-test-cursor-secret-value",
            page_size=2,
        )

    def test_all_pages_are_required_for_complete_inventory(self) -> None:
        first = self.paginator.page(
            item_count=3,
            revision="revision-a",
            cursor=None,
        )
        assert first.next_cursor is not None
        second = self.paginator.page(
            item_count=3,
            revision="revision-a",
            cursor=first.next_cursor,
        )

        self.assertEqual((first.start, first.end), (0, 2))
        self.assertEqual((second.start, second.end), (2, 3))
        self.assertIsNone(second.next_cursor)

    def test_forged_cursor_is_rejected(self) -> None:
        with self.assertRaises(InvalidInventoryCursor):
            self.paginator.page(
                item_count=3,
                revision="revision-a",
                cursor="forged-cursor",
            )

    def test_cursor_from_old_revision_is_rejected(self) -> None:
        first = self.paginator.page(
            item_count=3,
            revision="revision-a",
            cursor=None,
        )
        assert first.next_cursor is not None

        with self.assertRaises(InvalidInventoryCursor):
            self.paginator.page(
                item_count=3,
                revision="revision-b",
                cursor=first.next_cursor,
            )


if __name__ == "__main__":
    unittest.main()
