from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from feedgen.feed import FeedGenerator
from selectolax.parser import HTMLParser, Node


BLOG_URL = "https://livablecitylab.yale.edu/news"
FEED_URL = "https://raw.githubusercontent.com/sethrylan/rss/main/livablecitylab.xml"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime
    summary: str


def text(node: Node | None) -> str:
    if node is None:
        return ""
    return " ".join(node.text(strip=True).split())


def parse_date(value: str) -> datetime:
    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unsupported Livable City Lab news date format: {value}")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def parse_card(card: Node) -> Post | None:
    title = text(card.css_first("h2.h2-project"))
    date_text = text(card.css_first("p.p-text-grey"))
    if not title or not date_text:
        return None

    # Some items are announcements without an external link; anchor those to the news page.
    link = card.css_first("a.link[href]")
    href = link.attributes.get("href", "") if link is not None else ""
    url = urljoin(BLOG_URL, href) if href and href != "#" else f"{BLOG_URL}#{slug(title)}"

    return Post(
        title=title,
        url=url,
        published=parse_date(date_text),
        summary=text(card.css_first("p.p-text-news")),
    )


def parse_posts(html: str) -> list[Post]:
    tree = HTMLParser(html)
    posts: list[Post] = []
    seen: set[str] = set()

    for card in tree.css(".news-item.w-dyn-item"):
        post = parse_card(card)
        if post is None or post.url in seen:
            continue
        posts.append(post)
        seen.add(post.url)

    if not posts:
        raise RuntimeError("No Livable City Lab news items found; the page markup may have changed.")

    return posts


def build_feed(posts: list[Post]) -> bytes:
    updated = max(post.published for post in posts)

    feed = FeedGenerator()
    feed.id(BLOG_URL)
    feed.title("Livable City Lab News")
    feed.subtitle("News from the Yale Livable City Lab on urban design, geospatial data, and sustainability.")
    feed.author({"name": "Yale Livable City Lab"})
    feed.link(href=BLOG_URL, rel="alternate")
    feed.link(href=FEED_URL, rel="self")
    feed.language("en-US")
    feed.updated(updated)

    # feedgen emits entries in reverse insertion order, so add oldest to newest.
    for post in sorted(posts, key=lambda item: item.published):
        entry = feed.add_entry()
        entry.id(post.url)
        entry.title(post.title)
        entry.link(href=post.url, rel="alternate")
        entry.updated(post.published)
        entry.published(post.published)
        entry.author({"name": "Yale Livable City Lab"})
        if post.summary:
            entry.summary(post.summary)

    return feed.atom_str(pretty=True)


def main() -> None:
    response = httpx.get(BLOG_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    sys.stdout.buffer.write(build_feed(parse_posts(response.text)))


if __name__ == "__main__":
    main()
