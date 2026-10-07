import unittest
from unittest.mock import Mock
from scripts.collect_wayback_urls import resolve_archives
from tests.test_nation_archive import ORIGINAL


class WaybackUrlTests(unittest.TestCase):
    def client(self, text):
        client = Mock(user_agent='SyntheticTestBot')
        client.fetch.return_value = Mock(text=text)
        return client

    def test_real_waybackpy_parser_uses_bounded_shared_transport(self):
        text = f'africa,nation)/kenya/business/sample 20240616122729 {ORIGINAL} text/html 200 ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 1234'
        client = self.client(text)
        urls = resolve_archives([ORIGINAL], client)
        self.assertEqual(urls, ['https://web.archive.org/web/20240616122729/' + ORIGINAL])
        query = client.fetch.call_args.args[0]
        self.assertIn('limit=1', query)
        self.assertIn('matchType=exact', query)
        self.assertEqual(client.fetch.call_args.kwargs, {'stage': 'CDX_INDEX'})
        self.assertEqual(client.fetch.call_count, 1)

    def test_missing_archive_and_index_failure_are_distinct(self):
        with self.assertLogs(level='WARNING'):
            self.assertEqual(resolve_archives([ORIGINAL], self.client('')), [])
        client = self.client('')
        client.fetch.return_value = None
        with self.assertRaises(RuntimeError):
            resolve_archives([ORIGINAL], client)

    def test_existing_replay_needs_no_lookup(self):
        client = self.client('')
        replay = 'https://web.archive.org/web/20240616122729/' + ORIGINAL
        self.assertEqual(resolve_archives([replay, replay], client), [replay])
        client.fetch.assert_not_called()
