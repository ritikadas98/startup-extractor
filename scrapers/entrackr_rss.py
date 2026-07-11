from scrapers.base_scraper import RSSFeedScraper


class EntrackrRSS(RSSFeedScraper):
    name = "entrackr"
    feed_url = "https://entrackr.com/feed"
