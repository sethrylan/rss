# RSS

Generated feeds for sites that do not publish their own.

## Feeds

| Site | Feed URL |
| --- | --- |
| XBOW Blog | `https://raw.githubusercontent.com/sethrylan/rss/main/xbow.xml` |

## Adding a feed

Add a scraper under `scrapers/`, emit Atom XML to stdout with `uv run python scrapers/<site>.py`, then add a matching build command to `.github/workflows/feeds.yml` that writes `<site>.xml`.
