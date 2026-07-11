from scrapers.base_scraper import RSSFeedScraper


class YourStoryScraper(RSSFeedScraper):
    name = "yourstory"
    feed_url = "https://yourstory.com/feed"
