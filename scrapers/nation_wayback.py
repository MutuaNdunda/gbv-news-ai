"""Compatibility adapter for the shared publisher-independent Wayback discovery."""
from types import SimpleNamespace
from scrapers import nation
from scrapers.wayback_discovery import ArchiveSource, Discovery

def accepts_fetch(url):
    return ArchiveSource(nation).accepts_fetch(url)

def candidates(client, max_pages=1, urls=None, start=None, end=None, section=None):
    publisher = SimpleNamespace(**vars(nation))
    publisher.ARCHIVE_PREFIXES = ("https://nation.africa/kenya/" + (section + "/" if section else ""),)
    discovery = Discovery(ArchiveSource(publisher), client, start=start, end=end,
                          max_pages=max_pages, max_requests=max_pages,
                          max_records=max_pages * 500, urls=urls)
    yield from discovery.candidates()
    if discovery.stats["index_failures"]:
        raise RuntimeError("Nation archive discovery failed; coverage incomplete")
