"""TLDR Product newsletter (tldr.tech/product): PM-learning reference source.

Each feed item is a daily newsletter edition (a page of curated PM links with
blurbs). Reference source: collected and searchable, never AI-analyzed —
it's learning material, not funding news.
"""
from scrapers.base_scraper import RSSFeedScraper


class TLDRProductRSS(RSSFeedScraper):
    name = "tldr_product"
    feed_url = "https://tldr.tech/api/rss/product"
    filter_funding = False
