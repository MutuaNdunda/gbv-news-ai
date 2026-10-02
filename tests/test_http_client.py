"""Transient rate limits retry conservatively without retrying access denials."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import unittest
from unittest.mock import call, patch

import requests

from scrapers.common import Client


URL = "https://web.archive.org/cdx/search/cdx"


def response(status, retry_after=None):
    result = requests.Response()
    result.status_code = status
    result.url = URL
    if retry_after is not None:
        result.headers["Retry-After"] = retry_after
    return result


class HttpClientTests(unittest.TestCase):
    def test_rate_limit_honors_seconds_then_recovers(self):
        client = Client(("web.archive.org",), delay=0)
        success = response(200)
        with patch.object(client.session, "get", side_effect=[response(429, "7"), success]) as get, \
                patch("scrapers.common.time.sleep") as sleep:
            self.assertIs(client._request(URL), success)
        self.assertEqual(get.call_count, 2)
        self.assertIn(call(7), sleep.call_args_list)

    def test_retry_after_http_date_and_invalid_header(self):
        client = Client(("web.archive.org",), delay=2)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        header = format_datetime(now + timedelta(seconds=20), usegmt=True)
        with patch("scrapers.common.datetime") as clock:
            clock.now.return_value = now
            self.assertEqual(client._retry_wait(response(429, header), 0), 20)
        self.assertEqual(client._retry_wait(response(429, "invalid"), 1), 2)

    def test_long_retry_after_defers_without_early_retry(self):
        client = Client(("web.archive.org",), delay=0)
        limited = response(429, "120")
        with patch.object(client.session, "get", return_value=limited) as get, \
                patch("scrapers.common.time.sleep"):
            self.assertIs(client._request(URL), limited)
        self.assertEqual(get.call_count, 1)

    def test_repeated_rate_limits_stop_after_three_attempts(self):
        client = Client(("web.archive.org",), delay=0, request_stage="CDX_INDEX")
        with patch.object(client, "permitted", return_value=True), \
                patch.object(client.session, "get", return_value=response(429)) as get, \
                patch("scrapers.common.time.sleep"):
            self.assertIsNone(client.fetch(URL))
        self.assertEqual(get.call_count, 3)
        self.assertEqual(client.last_failure["http_status"], 429)
        self.assertEqual(client.last_failure["stage"], "CDX_INDEX")

    def test_forbidden_responses_are_not_retried(self):
        client = Client(("web.archive.org",), delay=0)
        denied = response(403)
        with patch.object(client.session, "get", return_value=denied) as get, \
                patch("scrapers.common.time.sleep"):
            self.assertIs(client._request(URL), denied)
        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
