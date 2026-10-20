#!/usr/bin/env python3
"""
Gold News Dashboard generator.

Mengambil berita (NewsAPI) + harga emas (GoldAPI), mengelompokkan per hari,
memberi label Bullish/Bearish/Netral berdasarkan kata kunci, lalu menulis
docs/index.html (untuk GitHub Pages). Jalankan terjadwal (cron / Task Scheduler) agar otomatis per hari.

Setup:
  pip install requests
  export NEWSAPI_KEY="..."      # https://newsapi.org
  export GOLDAPI_KEY="..."      # https://www.goldapi.io  (opsional)
  python gold_news_dashboard.py

Catatan: skrip ini belum diuji dengan API key Anda. Cek format respons
tiap API jika ada error. Klasifikasi kata kunci itu kasar, bukan saran trading.
"""
import os
import html
import datetime as dt
from collections import defaultdict

import requests

DAYS_BACK = 8
OUT_FILE = "docs/index.html"
QUERY = '(gold OR XAUUSD) AND (Fed OR yields OR dollar OR oil OR inflation OR "safe haven")'

BEARISH = ["yield rises", "yields rise", "yields climb", "yields jump", "hawkish",
           "rate hike", "hike bets", "stronger dollar", "dollar strengthens",
           "hot cpi", "hotter", "gold falls", "gold slips", "gold drops",
           "gold declines", "gold tumbles", "selloff", "outflows"]
BULLISH = ["rate cut", "dovish", "weaker dollar", "dollar falls", "yields fall",
           "yields drop", "safe haven", "safe-haven", "gold rises", "gold jumps",
           "gold climbs", "gold gains", "gold rallies", "etf inflows",
           "central bank buying", "inflows"]


def fetch_news(days_back=DAYS_BACK):
    key = os.environ["NEWSAPI_KEY"]
    since = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()
    r = requests.get(
        "https://newsapi.org/v2/everything",
        params={"q": QUERY, "from": since, "language": "en",
                "sortBy": "publishedAt", "pageSize": 100, "apiKey": key},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("articles", [])


def fetch_price():
    key = os.environ.get("GOLDAPI_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://www.goldapi.io/api/XAU/USD",
                         headers={"x-access-token": key}, timeout=15)
        r.raise_for_status()
        return r.json().get("price")
    except Exception as e:  # harga hanya pelengkap
        print("Gagal ambil harga:", e)
        return None


def score(text):
    t = text.lower()
    return sum(k in t for k in BULLISH) - sum(k in t for k in BEARISH)


def label(total):
    if total >= 2:
        return "bull", "Bullish"
    if total <= -2:
        return "bear", "Bearish"
    return "neu", "Netral"


def group_by_day(articles):
    days = defaultdict(list)
    for a in articles:
        day = (a.get("publishedAt") or "")[:10]
        if not day:
            continue
        text = f"{a.get('title', '')} {a.get('description', '')}"
        days[day].append({
            "title": a.get("title") or "",
            "url": a.get("url") or "#",
            "source": (a.get("source") or {}).get("name", ""),
            "score": score(text),
        })
    return days


def render(days, price):
    cards = []
    for day in sorted(days, reverse=True):
        items = days[day]
        total = sum(i["score"] for i in items)
        cls, name = label(total)
        top = sorted(items, key=lambda i: abs(i["score"]), reverse=True)[:4]
        lis = "".join(
            f'<li><a href="{html.escape(i["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(i["title"])}</a> <small>{html.escape(i["source"])}</small></li>'
            for i in top
        )
        cards.append(
            f'<section class="day {cls}"><div class="hd"><strong>{day}</strong>'
            f'<span class="tag">{name}</span></div>'
            f'<div class="px">{len(items)} berita · skor {total:+d}</div><ul>{lis}</ul></section>'
        )
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    price_txt = f"${price:,.2f}" if price else "-"
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold News Dashboard</title>
<style>
:root{{--bg:#f6f4ee;--card:#fff;--tx:#1d1b16;--mu:#6b665a;--bd:#e4dfd2;--gold:#b8860b;--bear:#c0392b;--bull:#1e8e5a;--neu:#7a7466}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121110;--card:#1c1a17;--tx:#f1ede2;--mu:#a39d8e;--bd:#2d2a24;--gold:#e0b84a;--bear:#ef6a5b;--bull:#4cc58b;--neu:#a39d8e}}}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:640px;margin:0 auto;padding:16px}}
h1{{font-size:20px;margin:0}} .sub{{color:var(--mu);font-size:13px;margin:2px 0 14px}}
.price{{font-size:24px;color:var(--gold);font-weight:700;margin-bottom:12px}}
.day{{background:var(--card);border:1px solid var(--bd);border-left:4px solid var(--neu);border-radius:12px;padding:12px;margin-bottom:10px}}
.day.bear{{border-left-color:var(--bear)}} .day.bull{{border-left-color:var(--bull)}}
.hd{{display:flex;justify-content:space-between}}
.tag{{font-size:12px;font-weight:600}} .bear .tag{{color:var(--bear)}} .bull .tag{{color:var(--bull)}}
.px{{color:var(--mu);font-size:12px;margin:2px 0 6px}}
ul{{margin:0;padding-left:18px}} li{{margin:3px 0}} a{{color:var(--tx)}} small{{color:var(--mu)}}
</style></head><body><main>
<h1>🪙 Gold News Dashboard</h1>
<p class="sub">Diperbarui otomatis · {now}</p>
<div class="price">XAU/USD {price_txt}</div>
{''.join(cards)}
<p class="sub">Label berdasarkan kata kunci judul. Bukan saran keuangan.</p>
</main></body></html>"""


def main():
    articles = fetch_news()
    days = group_by_day(articles)
    page = render(days, fetch_price())
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Selesai: {OUT_FILE} ({len(days)} hari, {len(articles)} berita)")


if __name__ == "__main__":
    main()
