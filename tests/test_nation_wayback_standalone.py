from datetime import date
import unittest
from unittest.mock import Mock
from scripts.nation_wayback_standalone import months, publication_date, snapshots
from tests.test_nation_archive import ORIGINAL


class StandaloneTests(unittest.TestCase):
    def test_months_and_publication_dates(self):
        self.assertEqual(len(list(months(date(2026, 1, 1), date(2026, 8, 31)))), 8)
        self.assertEqual(publication_date('2026-08-31T12:00:00Z'), date(2026, 8, 31))
        self.assertIsNone(publication_date(None))
        self.assertIsNone(publication_date('invalid'))

    def test_month_bounds_and_continuation_with_real_library_parser(self):
        row = f'africa,nation)/kenya/business/sample 20260116122729 {ORIGINAL} text/html 200 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 1234'
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.side_effect = [Mock(text=row + '\n\nnext%21'), Mock(text='')]
        found = list(snapshots(client, date(2026, 1, 1), 2))
        self.assertEqual(len(found), 1)
        query = client.fetch.call_args_list[0].args[0]
        self.assertIn('from=20260101', query)
        self.assertIn('to=20260131', query)
        self.assertIn('matchType=prefix', query)
        self.assertIn('resumeKey=next%21', client.fetch.call_args.args[0])

    def test_index_failure_and_page_cap_are_not_empty_success(self):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'CDX failed'):
            list(snapshots(client, date(2026, 1, 1), 1))
        row = f'africa,nation)/kenya/business/sample 20260116122729 {ORIGINAL} text/html 200 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 1234'
        client.fetch.return_value = Mock(text=row + '\n\nnext')
        with self.assertRaisesRegex(RuntimeError, 'page bound'):
            list(snapshots(client, date(2026, 1, 1), 1))
