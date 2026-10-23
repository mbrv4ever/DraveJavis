# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""vaardigheden.py - dingen die DraveJavis zelf meteen kan, zonder taalmodel.

doe(tekst, geheugen, taal) -> None (laat het taalmodel antwoorden)
                           of (antwoord, actie) met actie None / ("timer", sec, label) / ("open", url)
                           / ("zoek", term) / ("ochtend",) / ("plaats", naam) / ("map", pad)
"""
from __future__ import annotations

import datetime
import re

SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "wikipedia": "https://nl.wikipedia.org", "gmail": "https://mail.google.com",
    "github": "https://github.com", "nos": "https://nos.nl", "nu.nl": "https://www.nu.nl",
    "buienradar": "https://www.buienradar.nl", "weer": "https://www.buienradar.nl",
    "facebook": "https://www.facebook.com", "maps": "https://www.openstreetmap.org",
    "kaart": "https://www.openstreetmap.org", "netflix": "https://www.netflix.com",
}
GETALLEN = {"een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
            "negen": 9, "tien": 10, "elf": 11, "twaalf": 12, "vijftien": 15, "twintig": 20, "dertig": 30,
            "veertig": 40, "vijftig": 50, "zestig": 60, "half": 0.5, "anderhalf": 1.5, "kwartier": 15,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "a": 1, "an": 1}
DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
           "oktober", "november", "december"]


def _getal(w):
    w = w.strip().lower().replace(",", ".")
    try:
        return float(w)
    except ValueError:
        return GETALLEN.get(w)


def _duur(t):
    """'5 minuten', 'anderhalf uur', '30 seconden', 'een kwartier' -> seconden."""
    if "kwartier" in t:
        n = _getal(re.search(r"(\w+)\s+kwartier", t).group(1)) if re.search(r"(\w+)\s+kwartier", t) else 1
        return int((n or 1) * 15 * 60)
    m = re.search(r"([\d.,]+|\w+)\s*(seconden|seconde|sec|s\b|minuten|minuut|min|uur|uren|seconds?|minutes?|hours?)", t)
    if not m:
        return None
    n = _getal(m.group(1))
    if n is None:
        return None
    eenheid = m.group(2)
    if eenheid.startswith(("sec", "s")):
        return int(n)
    if eenheid.startswith(("min",)):
        return int(n * 60)
    return int(n * 3600)


def mooi_duur(sec, taal="nl"):
    u, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    delen = []
    if taal == "nl":
        if u:
            delen.append("%d uur" % u)
        if m:
            delen.append("%d minu%s" % (m, "ut" if m == 1 else "ten"))
        if s:
            delen.append("%d seconde%s" % (s, "" if s == 1 else "n"))
        return " en ".join(delen) or "0 seconden"
    if u:
        delen.append("%d hour%s" % (u, "" if u == 1 else "s"))
    if m:
        delen.append("%d minute%s" % (m, "" if m == 1 else "s"))
    if s:
        delen.append("%d second%s" % (s, "" if s == 1 else "s"))
    return " and ".join(delen) or "0 seconds"


def doe(tekst, geheugen, taal="nl"):
    t = tekst.lower().strip().rstrip("?!. ")
    nu = datetime.datetime.now()
    nl = taal == "nl"
    # ---- tijd en datum
    if re.search(r"\b(hoe laat is het|hoe laat|wat is de tijd|what time is it|what's the time)\b", t):
        return (("Het is %d:%02d." % (nu.hour, nu.minute)) if nl else nu.strftime("It's %H:%M.")), None
    if re.search(r"\b(welke dag is het|wat is de datum|welke datum|de hoeveelste|what day is it|what's the date|what is the date)\b", t):
        if nl:
            return "Het is vandaag %s %d %s %d." % (DAGEN[nu.weekday()], nu.day, MAANDEN[nu.month - 1], nu.year), None
        return nu.strftime("Today is %A, %d %B %Y."), None
    # ---- timer
    if re.search(r"\b(timer|wekker|herinner|remind|countdown)\b", t):
        sec = _duur(t)
        if sec:
            label = mooi_duur(sec, taal)
            return (("Timer gezet: %s. Ik laat het je weten." % label) if nl
                    else ("Timer set: %s. I'll let you know." % label)), ("timer", sec, label)
    # ---- onthouden / vergeten
    m = re.match(r"^(onthoud|onthou|remember)( (dat|that))?\s+(.+)$", tekst.strip(), re.I)
    if m:
        feit = geheugen.onthoud(m.group(4))
        return (("Goed, dat onthoud ik: %s." % feit) if nl else ("Got it, I'll remember: %s." % feit)), None
    m = re.match(r"^(vergeet|forget)( (dat|that|over|about))?\s+(.+)$", tekst.strip(), re.I)
    if m:
        n = geheugen.vergeet(m.group(4).rstrip(".!? "))
        if nl:
            return ("Vergeten." if n else "Dat had ik niet onthouden."), None
        return ("Forgotten." if n else "I hadn't remembered that."), None
    if re.search(r"\b(wat heb je onthouden|wat weet je over mij|wat weet jij over mij|what do you remember|what do you know about me)\b", t):
        if not geheugen.feiten:
            return ("Ik heb nog niets onthouden. Zeg maar 'onthoud dat...'." if nl
                    else "I haven't remembered anything yet. Just say 'remember that...'."), None
        lijst = "; ".join(re.sub(r"\b(mijn|my)\b", lambda m: "jouw" if m.group(1) == "mijn" else "your", f,
                                 flags=re.I) for f in geheugen.feiten[-12:])
        return (("Dit heb ik onthouden: %s." % lijst) if nl else ("This is what I remember: %s." % lijst)), None
    # ---- ochtendoverzicht
    if re.match(r"^(goede ?morgen|goeiemorgen|morgen javis|ochtendoverzicht|ochtend overzicht|dagoverzicht|"
                r"wat staat er (vandaag|op de planning)|wat heb ik vandaag|wat moet ik vandaag|"
                r"good morning|morning brief|what'?s on today)\b", t):
        return None, ("ochtend",)
    # ---- plaats voor het weer
    m = re.match(r"^(mijn plaats is|ik woon in|mijn woonplaats is|stel (mijn )?plaats in op|my (city|town|location) is|"
                 r"i live in)\s+(.+)$", tekst.strip().rstrip(".!? "), re.I)
    if m:
        return None, ("plaats", m.group(m.lastindex).strip())
    # ---- notities (komen als tekstbestand in je geheugenmap)
    m = re.match(r"^(noteer|notitie|maak een notitie|schrijf op|zet op mijn lijst|note|make a note|write down)"
                 r"( (dat|that|:))?\s*:?\s+(.+)$", tekst.strip(), re.I)
    if m:
        n = geheugen.noteer(m.group(4))
        return (("Genoteerd: %s." % n) if nl else ("Noted: %s." % n)), None
    # ---- zoeken in het eigen geheugen
    m = re.match(r"^(wat weet je (nog )?over|wat weet jij (nog )?over|zoek in (mijn|je|jouw) geheugen( naar| op)?|"
                 r"wat heb ik (gezegd|genoteerd|verteld) over|what do you know about|search (my )?memory for)\s+(.+)$", t)
    if m and not re.match(r"^(mij|me|mezelf)$", m.group(m.lastindex).strip()):
        vraag = m.group(m.lastindex)
        hits = geheugen.zoek(vraag, n=4)
        if not hits:
            return (("Daar heb ik niets over in mijn geheugen." if nl else "I have nothing about that in my memory.")), None
        delen = []
        for d, soort, regel in hits:
            regel = re.sub(r"\*\*", "", regel)
            regel = re.sub(r"^\d{1,2}:\d{2}\s*", "", regel)
            if d and nl:
                try:
                    dd = datetime.date.fromisoformat(d)
                    regel = "op %d %s: %s" % (dd.day, MAANDEN[dd.month - 1], regel)
                except Exception:
                    pass
            delen.append(regel)
        return (("Dit vond ik in mijn geheugen: %s." if nl else "This is what I found in my memory: %s.") % "; ".join(delen)), None
    if re.search(r"\b(open (mijn|je|jouw|het) geheugen(map)?|toon (mijn|je) geheugen|open my memory)\b", t):
        return (("Ik open je geheugenmap. Daar staan gewone tekstbestanden die je zelf mag aanpassen." if nl
                 else "Opening your memory folder.")), ("map", geheugen.map())
    # ---- websites
    m = re.match(r"^(open|ga naar|go to|start)\s+(de website\s+|website\s+)?([\w.\-/]+)$", t)
    if m:
        doel = m.group(3)
        url = SITES.get(doel)
        if not url and "." in doel:
            url = "https://" + doel if not doel.startswith("http") else doel
        if url:
            naam = doel if doel in SITES else url.split("//")[-1]
            return (("Ik open %s." % naam) if nl else ("Opening %s." % naam)), ("open", url)
    m = re.match(r"^(zoek (eens )?(op internet|online|op het web)( naar| op)?|zoek op|google( eens)?|search the web for|"
                 r"search online for|search for|look up)\s+(.+)$", t)
    if m:
        vraag = m.group(m.lastindex)
        return None, ("zoek", vraag)
    return None
