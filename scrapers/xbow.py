from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from feedgen.feed import FeedGenerator
from selectolax.parser import HTMLParser, Node


BLOG_URL = "https://xbow.com/blog"
FEED_URL = "https://raw.githubusercontent.com/sethrylan/rss/main/xbow.xml"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime | None
    authors: tuple[str, ...]


def text(node: Node | None) -> str:
    if node is None:
        return ""
    return " ".join(node.text(strip=True).split())


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unsupported XBOW blog date format: {value}")


def parse_posts(html: str) -> list[Post]:
    tree = HTMLParser(html)
    posts: list[Post] = []
    seen: set[str] = set()

    for card in tree.css("div.ds_blog_card.w-dyn-item"):
        link = card.css_first('a.link_cover[href^="/blog/"], a.link_cover[href^="https://xbow.com/blog/"]')
        title = text(card.css_first('[fs-list-field="name"]'))
        if link is None or not title:
            continue

        url = urljoin(BLOG_URL, link.attributes["href"])
        if url in seen:
            continue

        date_text = text(card.css_first('[fs-list-field="date"]'))
        authors = tuple(
            author
            for node in card.css(".ds_blog_card_content p.ds-text-style-regular.ds-text-color-secondary")
            if (author := text(node))
        )

        posts.append(Post(title=title, url=url, published=parse_date(date_text), authors=authors))
        seen.add(url)

    if not posts:
        raise RuntimeError("No XBOW blog posts found; the blog markup may have changed.")

    return posts


def build_feed(posts: list[Post]) -> bytes:
    fallback_updated = datetime(1970, 1, 1, tzinfo=timezone.utc)
    updated = max((post.published for post in posts if post.published), default=fallback_updated)

    feed = FeedGenerator()
    feed.id(BLOG_URL)
    feed.title("XBOW Blog")
    feed.subtitle("AI-powered pentesting insights from XBOW.")
    feed.author({"name": "XBOW"})
    feed.link(href=BLOG_URL, rel="alternate")
    feed.link(href=FEED_URL, rel="self")
    feed.language("en")
    feed.updated(updated)

    # feedgen emits entries in reverse insertion order, so add oldest to newest.
    for post in sorted(posts, key=lambda item: item.published or fallback_updated):
        entry_updated = post.published or updated
        entry = feed.add_entry()
        entry.id(post.url)
        entry.title(post.title)
        entry.link(href=post.url, rel="alternate")
        entry.updated(entry_updated)
        entry.published(entry_updated)
        if post.authors:
            entry.author({"name": ", ".join(post.authors)})
            entry.summary(f"By {', '.join(post.authors)}")

    return feed.atom_str(pretty=True)


def main() -> None:
    response = httpx.get(BLOG_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    sys.stdout.buffer.write(build_feed(parse_posts(response.text)))


if __name__ == "__main__":
    main()
