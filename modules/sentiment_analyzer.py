import feedparser
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import datetime

analyzer = SentimentIntensityAnalyzer()

# Google News RSS feeds — no API key needed
NEWS_FEEDS = {
    "PSU Banks": "https://news.google.com/rss/search?q=PSU+Bank+India+RBI&hl=en-IN&gl=IN&ceid=IN:en",
    "HDFC Bank": "https://news.google.com/rss/search?q=HDFC+Bank+stock+NSE&hl=en-IN&gl=IN&ceid=IN:en",
    "Nifty Bank": "https://news.google.com/rss/search?q=Nifty+Bank+index+India&hl=en-IN&gl=IN&ceid=IN:en",
    "RBI Policy": "https://news.google.com/rss/search?q=RBI+interest+rate+policy+India&hl=en-IN&gl=IN&ceid=IN:en",
    "Indian Market": "https://news.google.com/rss/search?q=Nifty+Smallcap+250+ETF+India+NSE&hl=en-IN&gl=IN&ceid=IN:en",
    "Smallcap": "https://news.google.com/rss/search?q=Nifty+Smallcap+India+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en",
}


def fetch_news(etf_name: str = "PSU Banks", max_articles: int = 10) -> list:
    """Fetch latest news from Google News RSS for a given topic."""
    feed_url = NEWS_FEEDS.get(etf_name, NEWS_FEEDS["Indian Market"])
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:max_articles]:
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "link": entry.get("link", ""),
            })
        return articles
    except Exception as e:
        print(f"[SentimentAnalyzer] News fetch error: {e}")
        return []


def analyze_sentiment(articles: list) -> dict:
    """Run VADER sentiment on all article titles and summaries."""
    if not articles:
        return {"score": 0, "label": "NEUTRAL", "articles_analyzed": 0, "details": []}

    scores = []
    details = []
    for article in articles:
        text = article["title"] + " " + article.get("summary", "")
        vs = analyzer.polarity_scores(text)
        scores.append(vs["compound"])
        details.append({
            "title": article["title"],
            "score": round(vs["compound"], 3),
            "label": _label(vs["compound"]),
            "published": article.get("published", ""),
            "link": article.get("link", ""),
        })

    avg_score = round(sum(scores) / len(scores), 3)
    return {
        "score": avg_score,
        "label": _label(avg_score),
        "articles_analyzed": len(articles),
        "details": details,
    }


def get_sentiment_for_etf(etf_key: str) -> dict:
    """Full pipeline: fetch news → analyze → return sentiment result."""
    articles = fetch_news(etf_name=etf_key)
    result = analyze_sentiment(articles)
    result["etf"] = etf_key
    result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result


def _label(score: float) -> str:
    if score >= 0.15:
        return "BULLISH"
    elif score <= -0.15:
        return "BEARISH"
    else:
        return "NEUTRAL"
