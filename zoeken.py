# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""zoeken.py - DraveJavis zoekt zelf online en leest de beste pagina's, zonder je browser te openen.

Zoekmachine: DuckDuckGo (pakket 'ddgs' als dat er is, anders de eenvoudige HTML-versie via urllib).
Alleen de zoekvraag gaat het internet op; er wordt niets over jou meegestuurd.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")


def _schoon(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def _ddgs(vraag, n, taal):
    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS
        except Exception:
            return None
    try:
        regio = "nl-nl" if taal == "nl" else "wt-wt"
        with DDGS() as d:
            uit = []
            for r in d.text(vraag, region=regio, max_results=n):
                url = r.get("href") or r.get("url") or ""
                if url:
                    uit.append(dict(titel=(r.get("title") or url).strip(), url=url,
                                    tekst=(r.get("body") or "").strip()))
            return uit
    except Exception:
        return None


def _ddg_html(vraag, n, taal):
    try:
        data = urllib.parse.urlencode({"q": vraag, "kl": "nl-nl" if taal == "nl" else "wt-wt"}).encode()
        req = urllib.request.Request("https://html.duckduckgo.com/html/", data=data,
                                     headers={"User-Agent": UA, "Accept-Language": "nl,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=10) as r:
            pagina = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    uit = []
    blokken = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)',
                         pagina, re.S)
    for href, titel, rest in blokken:
        m = re.search(r"uddg=([^&]+)", href)
        url = urllib.parse.unquote(m.group(1)) if m else href
        if url.startswith("//"):
            url = "https:" + url
        if "duckduckgo.com/y.js" in url:      # advertentie
            continue
        s = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        uit.append(dict(titel=_schoon(titel), url=url, tekst=_schoon(s.group(1)) if s else ""))
        if len(uit) >= n:
            break
    return uit


def _lees_pagina(url, max_tekens=1800):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nl,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=7) as r:
            if "html" not in (r.headers.get("Content-Type") or ""):
                return ""
            ruw = r.read(600_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""
    ruw = re.sub(r"(?is)<(script|style|noscript|header|footer|nav|form|svg)[^>]*>.*?</\1>", " ", ruw)
    m = re.search(r"(?is)<(article|main)[^>]*>(.*?)</\1>", ruw)
    deel = m.group(2) if m else ruw
    alineas = [_schoon(a) for a in re.findall(r"(?is)<p[^>]*>(.*?)</p>", deel)]
    tekst = " ".join(a for a in alineas if len(a) > 40)
    if len(tekst) < 200:
        tekst = _schoon(deel)
    return tekst[:max_tekens]


def zoek(vraag, n=5, taal="nl", lees=2):
    """Geeft een lijst resultaten: dict(titel, url, tekst). De eerste 'lees' pagina's worden ook gelezen."""
    res = _ddgs(vraag, n, taal)
    if not res:
        res = _ddg_html(vraag, n, taal)
    if lees and res:
        with ThreadPoolExecutor(max_workers=lees) as ex:
            teksten = list(ex.map(_lees_pagina, [r["url"] for r in res[:lees]]))
        for r, t in zip(res, teksten):
            if t:
                r["pagina"] = t
    return res


def als_context(vraag, res, taal="nl"):
    if taal == "nl":
        kop = "Zoekresultaten van internet voor: \"%s\"\n" % vraag
        slot = ("\nBeantwoord mijn vraag kort en duidelijk met deze informatie (een paar zinnen). "
                "Noem geen webadressen; de bronnen worden apart getoond. Staat het antwoord er niet in, zeg dat eerlijk.")
    else:
        kop = "Web search results for: \"%s\"\n" % vraag
        slot = ("\nAnswer my question briefly and clearly using this information (a few sentences). "
                "Don't read out web addresses; the sources are shown separately. If the answer isn't there, say so.")
    delen = [kop]
    for i, r in enumerate(res, 1):
        delen.append("[%d] %s\n%s" % (i, r["titel"], r.get("pagina") or r.get("tekst") or ""))
    return "\n\n".join(delen) + slot
