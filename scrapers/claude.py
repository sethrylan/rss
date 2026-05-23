from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from feedgen.feed import FeedGenerator
from selectolax.parser import HTMLParser, Node


BLOG_URL = "https://claude.com/blog"
FEED_URL = "https://raw.githubusercontent.com/sethrylan/rss/main/claude.xml"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime
    category: str


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
    raise ValueError(f"Unsupported Claude blog date format: {value}")


def parse_card(card: Node) -> Post | None:
    link = card.css_first('a[href^="/blog/"]')
    title = text(card.css_first('[fs-list-field="heading"], .card_blog_title, h1, h2, h3, h4, h5, h6'))
    date_text = text(card.css_first('[fs-list-field="date"], .u-text-style-caption.u-foreground-tertiary'))
    if link is None or not title or not date_text:
        return None

    category = text(card.css_first('[fs-list-field="category"]'))
    return Post(
        title=title,
        url=urljoin(BLOG_URL, link.attributes["href"]),
        published=parse_date(date_text),
        category=category,
    )


def parse_posts(html: str) -> list[Post]:
    tree = HTMLParser(html)
    posts: list[Post] = []
    seen: set[str] = set()

    for card in [*tree.css(".blog_cms_item"), *tree.css(".marquee_cms_blog_list_item")]:
        post = parse_card(card)
        if post is None or post.url in seen:
            continue
        posts.append(post)
        seen.add(post.url)

    if not posts:
        raise RuntimeError("No Claude blog posts found; the blog markup may have changed.")

    return posts


def build_feed(posts: list[Post]) -> bytes:
    updated = max(post.published for post in posts)

    feed = FeedGenerator()
    feed.id(BLOG_URL)
    feed.title("Claude Blog")
    feed.subtitle("Practical guidance and best practices for building with Claude.")
    feed.author({"name": "Anthropic"})
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
        entry.author({"name": "Anthropic"})
        if post.category:
            entry.summary(post.category)

    return feed.atom_str(pretty=True)


def main() -> None:
    response = httpx.get(BLOG_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    sys.stdout.buffer.write(build_feed(parse_posts(response.text)))


if __name__ == "__main__":
    main()
