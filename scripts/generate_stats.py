#!/usr/bin/env python3
"""Собирает статистику профиля GitHub и рисует две SVG-карточки.

Скрипт не требует сторонних библиотек: только стандартная библиотека Python.
Карточки кладутся в assets/ и подключаются в README обычными <img src="...">,
поэтому они рендерятся силами самого GitHub и не зависят от того, жив ли
очередной публичный инстанс github-readme-stats.

Токен берётся из переменной окружения GITHUB_TOKEN (или GH_TOKEN).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER = "andreyvol2005"
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# Палитра темы tokyonight — та же, что была у карточек из README.
BG = "#1a1b27"
TITLE = "#70a5fd"
TEXT = "#38bdae"
VALUE = "#c0caf5"
ACCENT = "#bf91f3"
DIM = "#2f80ed"
FALLBACK_LANG = "#8b9dc3"

CARD_W = 495
CARD_H = 195
FONT = "'Segoe UI', Ubuntu, Sans-Serif"


def token() -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    sys.exit("не задан GITHUB_TOKEN")


def request_json(path: str, payload: dict | None = None) -> dict:
    url = path if path.startswith("http") else API + path
    data = None
    headers = {
        "Authorization": f"bearer {token()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-stats-generator",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        body = exc.read().decode("utf-8", "replace")[:400]
        sys.exit(f"GitHub API {exc.code} на {url}: {body}")
    except urllib.error.URLError as exc:
        sys.exit(f"нет связи с GitHub API ({url}): {exc.reason}")


PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        name
        stargazerCount
        isPrivate
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def search_total(kind: str, query: str) -> int:
    """Количество результатов поиска GitHub (search/issues или search/commits)."""
    path = f"/search/{kind}?" + urllib.parse.urlencode({"q": query, "per_page": 1})
    data = request_json(path)
    return int(data.get("total_count") or 0)


def collect() -> dict:
    data = request_json("/graphql", {"query": PROFILE_QUERY, "variables": {"login": USER}})
    if "errors" in data:
        sys.exit(f"ошибка GraphQL: {data['errors']}")
    user = data["data"]["user"]

    stars = 0
    languages: dict[str, dict] = {}
    for repo in user["repositories"]["nodes"]:
        if repo["isPrivate"] or repo["name"] == USER:
            continue
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = languages.setdefault(
                name,
                {"name": name, "color": edge["node"].get("color") or FALLBACK_LANG, "bytes": 0},
            )
            entry["bytes"] += edge["size"]

    commits = search_total("commits", f"author:{USER}")
    prs = search_total("issues", f"author:{USER} type:pr")
    issues = search_total("issues", f"author:{USER} type:issue")

    ordered = sorted(languages.values(), key=lambda item: item["bytes"], reverse=True)
    total_bytes = sum(item["bytes"] for item in ordered) or 1
    for item in ordered:
        item["percent"] = 100.0 * item["bytes"] / total_bytes

    return {
        "stars": stars,
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "followers": user["followers"]["totalCount"],
        "languages": ordered[:6],
    }


def esc(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def stats_svg(stats: dict) -> str:
    rows = [
        (ACCENT, "Всего звёзд", stats["stars"]),
        (TITLE, "Всего коммитов", stats["commits"]),
        (TEXT, "Pull requests", stats["prs"]),
        ("#7dcfff", "Issues", stats["issues"]),
        ("#e0af68", "Подписчики", stats["followers"]),
    ]
    parts = [
        f'<svg width="{CARD_W}" height="{CARD_H}" viewBox="0 0 {CARD_W} {CARD_H}" '
        'fill="none" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-labelledby="stats-title">',
        '<title id="stats-title">Статистика GitHub: Andrikck</title>',
        "<style>",
        f".title {{ font: 600 17px {FONT}; fill: {TITLE}; }}",
        f".label {{ font: 400 13px {FONT}; fill: {TEXT}; }}",
        f".value {{ font: 700 13px {FONT}; fill: {VALUE}; }}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="6" '
        f'fill="{BG}" stroke="{DIM}" stroke-opacity="0.35"/>',
        '<text class="title" x="25" y="38">Andrikck · статистика GitHub</text>',
        f'<line x1="25" y1="52" x2="{CARD_W - 25}" y2="52" stroke="{DIM}" '
        'stroke-opacity="0.35"/>',
    ]
    y = 76
    for color, label, value in rows:
        parts.append(f'<circle cx="30" cy="{y - 4.5}" r="4" fill="{color}"/>')
        parts.append(f'<text class="label" x="46" y="{y}">{esc(label)}</text>')
        parts.append(
            f'<text class="value" x="{CARD_W - 25}" y="{y}" text-anchor="end">'
            f"{value}</text>"
        )
        y += 26
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def langs_svg(stats: dict) -> str:
    parts = [
        f'<svg width="{CARD_W}" height="{CARD_H}" viewBox="0 0 {CARD_W} {CARD_H}" '
        'fill="none" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-labelledby="langs-title">',
        '<title id="langs-title">Самые используемые языки</title>',
        "<style>",
        f".title {{ font: 600 17px {FONT}; fill: {TITLE}; }}",
        f".label {{ font: 400 13px {FONT}; fill: {TEXT}; }}",
        f".value {{ font: 700 13px {FONT}; fill: {VALUE}; }}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="6" '
        f'fill="{BG}" stroke="{DIM}" stroke-opacity="0.35"/>',
        '<text class="title" x="25" y="38">Самые используемые языки</text>',
        f'<line x1="25" y1="52" x2="{CARD_W - 25}" y2="52" stroke="{DIM}" '
        'stroke-opacity="0.35"/>',
    ]
    y = 74
    bar_x, bar_w = 152, 272
    for lang in stats["languages"]:
        pct = lang["percent"]
        parts.append(
            f'<circle cx="30" cy="{y - 4.5}" r="4" fill="{esc(lang["color"])}"/>'
        )
        parts.append(f'<text class="label" x="46" y="{y}">{esc(lang["name"])}</text>')
        parts.append(
            f'<rect x="{bar_x}" y="{y - 8.5}" width="{bar_w}" height="6" rx="3" '
            f'fill="{DIM}" fill-opacity="0.3"/>'
        )
        parts.append(
            f'<rect x="{bar_x}" y="{y - 8.5}" width="{bar_w * pct / 100:.1f}" '
            f'height="6" rx="3" fill="{esc(lang["color"])}"/>'
        )
        parts.append(
            f'<text class="value" x="{CARD_W - 25}" y="{y}" text-anchor="end">'
            f"{pct:.1f}%</text>"
        )
        y += 20
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stats = collect()
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "stats.svg").write_text(stats_svg(stats), encoding="utf-8")
    (ASSETS / "top-langs.svg").write_text(langs_svg(stats), encoding="utf-8")
    print(
        "готово: звёзд {stars}, коммитов {commits}, PR {prs}, issues {issues}, "
        "подписчиков {followers}".format(**stats)
    )


if __name__ == "__main__":
    main()
