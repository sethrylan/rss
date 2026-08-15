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
MAX_PAGES = 50


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime
    authors: tuple[str, ...]


def text(node: Node | None) -> str:
    if node is None:
        return ""
    return " ".join(node.text(strip=True).split())


def parse_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Unsupported XBOW blog date format: {value}") from error

    # Treat a date without an offset as UTC so the feed does not depend on the builder's timezone.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_card(card: Node) -> Post | None:
    href = card.attributes.get("href", "")
    if not href.startswith("/blog/") or href.startswith("/blog/category/"):
        return None

    title = text(card.css_first("h3"))
    published = card.css_first("time[datetime]")
    if not title or published is None:
        return None

    # The card markup repeats each author for a visible and an aria-hidden copy;
    # only the latter carries data-author-item, so this list is already deduped.
    authors = tuple(author for node in card.css("[data-author-item]") if (author := text(node)))

    return Post(
        title=title,
        url=urljoin(BLOG_URL, href),
        published=parse_date(published.attributes["datetime"]),
        authors=authors,
    )


def parse_page(html: str) -> list[Post]:
    return [post for card in HTMLParser(html).css("a[data-card]") if (post := parse_card(card))]


def fetch_posts(client: httpx.Client) -> list[Post]:
    posts: list[Post] = []
    seen: set[str] = set()

    # The blog paginates at /blog/page/N; walk until a page yields nothing new.
    for page in range(1, MAX_PAGES + 1):
        url = BLOG_URL if page == 1 else f"{BLOG_URL}/page/{page}"
        response = client.get(url)
        if response.status_code == httpx.codes.NOT_FOUND:
            break
        response.raise_for_status()

        fresh = [post for post in parse_page(response.text) if post.url not in seen]
        if not fresh:
            break

        posts.extend(fresh)
        seen.update(post.url for post in fresh)

    if not posts:
        raise RuntimeError("No XBOW blog posts found; the blog markup may have changed.")

    return posts


def build_feed(posts: list[Post]) -> bytes:
    updated = max(post.published for post in posts)

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
    for post in sorted(posts, key=lambda item: item.published):
        entry = feed.add_entry()
        entry.id(post.url)
        entry.title(post.title)
        entry.link(href=post.url, rel="alternate")
        entry.updated(post.published)
        entry.published(post.published)
        if post.authors:
            entry.author({"name": ", ".join(post.authors)})
            entry.summary(f"By {', '.join(post.authors)}")

    return feed.atom_str(pretty=True)


def main() -> None:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        posts = fetch_posts(client)
    sys.stdout.buffer.write(build_feed(posts))


if __name__ == "__main__":
    main()
