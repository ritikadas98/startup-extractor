from scrapers.base_scraper import RSSFeedScraper


class ETTechScraper(RSSFeedScraper):
    name = "ettech"
    # Economic Times "Tech" section RSS
    feed_url = "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"
