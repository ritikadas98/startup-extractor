from scrapers.base_scraper import RSSFeedScraper


class Inc42RSS(RSSFeedScraper):
    name = "inc42"
    feed_url = "https://inc42.com/feed/"
