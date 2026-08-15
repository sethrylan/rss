# RSS

Generated feeds for sites that do not publish their own.

## Feeds

| Site | Feed URL |
| --- | --- |
| Claude Blog | `https://raw.githubusercontent.com/sethrylan/rss/main/claude.xml` |
| XBOW Blog | `https://raw.githubusercontent.com/sethrylan/rss/main/xbow.xml` |
| Livable City Lab News | `https://raw.githubusercontent.com/sethrylan/rss/main/livablecitylab.xml` |

## Adding a feed

Add a scraper under `scrapers/` that emits Atom XML to stdout with `uv run python scrapers/<site>.py`, then add a row to the table above. The workflow builds every `scrapers/*.py` into a matching `<site>.xml`, so no workflow change is needed.

A scraper should raise when it parses zero posts — the workflow reports that as a failure and leaves that feed's last good XML in place, without blocking the other feeds.
