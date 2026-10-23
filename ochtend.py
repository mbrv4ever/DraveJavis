# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""ochtend.py - het ochtendoverzicht van DraveJavis.

Zeg "goedemorgen" (of "ochtendoverzicht", "wat staat er vandaag") en Javis vertelt in gewone taal:
- een begroeting met de datum,
- het weer van vandaag (zelfde weermotor als DraveWeer: storm, regen, windstoten in gewone taal),
- je afspraken van vandaag uit DraveAgenda (als je die gebruikt) en wat er de komende dagen aankomt,
- en een paar dingen die je hebt laten onthouden met 'noteer' voor vandaag.

Alles wordt alleen GELEZEN: Javis verandert niets aan je agenda.
Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
           "oktober", "november", "december"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def uitspreekbaar(t):
    """Tijden netjes voor de stem: 9:30 -> half 10, 14:00 -> 14 uur."""
    t = re.sub(r"\b(\d{1,2}):00\b", lambda m: "%s uur" % int(m.group(1)), t)
    t = re.sub(r"\b(\d{1,2}):30\b", lambda m: "half %s" % ((int(m.group(1)) % 12) + 1), t)
    t = re.sub(r"\b(\d{1,2}):15\b", lambda m: "kwart over %s" % (int(m.group(1)) % 12 or 12), t)
    t = re.sub(r"\b(\d{1,2}):45\b", lambda m: "kwart voor %s" % ((int(m.group(1)) % 12) + 1), t)
    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda m: "%s uur %s" % (int(m.group(1)), int(m.group(2))), t)
    return t.replace("–", " tot ")


def _groet(nu, naam, taal):
    u = nu.hour
    if taal == "nl":
        g = "Goedemorgen" if 5 <= u < 12 else "Goedemiddag" if 12 <= u < 18 else "Goedenavond" if 18 <= u < 24 else "Goedenacht"
        return "%s%s. Het is %s %d %s." % (g, (" " + naam) if naam else "", DAGEN[nu.weekday()], nu.day,
                                           MAANDEN[nu.month - 1])
    g = "Good morning" if 5 <= u < 12 else "Good afternoon" if 12 <= u < 18 else "Good evening"
    return "%s%s. It is %s, %s." % (g, (" " + naam) if naam else "", DAYS_EN[nu.weekday()], nu.strftime("%d %B"))


# ------------------------------------------------------------------ weer
def weer_zin(plaats, taal="nl"):
    """Eén of twee zinnen over het weer van vandaag, of None."""
    if not plaats or plaats.get("lat") is None:
        return None
    try:
        import weer_engine as W
        w = W.haal_weer(plaats["lat"], plaats["lon"])
    except Exception:
        w = None
    if not w or not w.get("dagen"):
        return ("Het weer kon ik nu niet ophalen." if taal == "nl" else "I couldn't get the weather right now.")
    d = w["dagen"][0]
    h = w.get("huidig") or {}
    tekst = d.get("tekst") or ""
    # "Vandaag: storm met ..." -> "In Amsterdam vandaag storm met ..."
    kern = tekst.split(":", 1)[1].strip() if ":" in tekst else tekst
    zin = []
    if taal == "nl":
        if h.get("temp") is not None:
            zin.append("In %s is het nu %d graden." % (plaats.get("naam", ""), round(h["temp"])))
        if kern:
            zin.append("Vandaag: " + kern)
        if d.get("max") is not None:
            zin.append("Het wordt maximaal %d graden." % round(d["max"]))
        if d.get("waarschuwing", 0) >= 2:
            zin.append("Let op, doe vandaag voorzichtig buiten.")
    else:
        if h.get("temp") is not None:
            zin.append("In %s it's %d degrees right now." % (plaats.get("naam", ""), round(h["temp"])))
        if d.get("max") is not None:
            zin.append("Today's high is %d degrees." % round(d["max"]))
    return " ".join(zin)


# ------------------------------------------------------------------ agenda (alleen lezen)
def _agenda_bestand():
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DraveAgenda", "agenda.json")


def agenda_zinnen(taal="nl", vandaag=None):
    """Afspraken van vandaag + wat er de komende 6 dagen aankomt (verjaardagen en dergelijke)."""
    p = _agenda_bestand()
    if not os.path.exists(p):
        return None
    try:
        import agenda_model as M
        with open(p, encoding="utf-8-sig") as f:
            afspraken = json.load(f).get("afspraken", [])
    except Exception:
        return None
    vandaag = vandaag or dt.date.today()
    nl = taal == "nl"
    zinnen = []
    lijst = M.op_dag(afspraken, vandaag)
    if not lijst:
        zinnen.append("Je agenda is vandaag leeg." if nl else "Your calendar is empty today.")
    else:
        delen = []
        for a in lijst[:8]:
            titel = a.get("titel") or ("iets zonder naam" if nl else "something untitled")
            lft = M.leeftijd(a, vandaag)
            if lft and nl:
                titel += " (wordt %d)" % lft
            if a.get("hele_dag") or not a.get("begin"):
                delen.append(("de hele dag: %s" if nl else "all day: %s") % titel)
            else:
                stuk = ("om %s: %s" if nl else "at %s: %s") % (a["begin"], titel)
                if a.get("plaats"):
                    stuk += (", in %s" if nl else ", at %s") % a["plaats"]
                delen.append(stuk)
        if nl:
            n = len(lijst)
            zinnen.append("Je hebt vandaag %s: %s." % ("één ding" if n == 1 else "%d dingen" % n, "; ".join(delen)))
        else:
            zinnen.append("Today you have: %s." % "; ".join(delen))
    # komende dagen: alleen verjaardagen en hele-dag-dingen, kort
    later = []
    for i in range(1, 7):
        d = vandaag + dt.timedelta(days=i)
        for a in M.op_dag(afspraken, d):
            if a.get("soort") == "verjaardag" or a.get("hele_dag"):
                wanneer = ("morgen" if i == 1 else DAGEN[d.weekday()]) if nl else ("tomorrow" if i == 1 else DAYS_EN[d.weekday()])
                later.append("%s %s" % (wanneer, a.get("titel", "")))
    if later:
        zinnen.append(("Binnenkort: %s." if nl else "Coming up: %s.") % ", ".join(later[:4]))
    return " ".join(zinnen)


# ------------------------------------------------------------------ alles samen
def overzicht(geheugen, taal="nl"):
    """Het hele ochtendoverzicht als gewone, uitspreekbare tekst."""
    cfg = geheugen.cfg
    nu = dt.datetime.now()
    delen = [_groet(nu, cfg.get("aanspreek") or cfg.get("naam") or "", taal)]
    w = weer_zin(cfg.get("plaats"), taal)
    if w:
        delen.append(w)
    elif taal == "nl":
        delen.append("Wil je ook het weer horen? Zeg dan bijvoorbeeld: mijn plaats is Amsterdam.")
    a = agenda_zinnen(taal, nu.date())
    if a:
        delen.append(a)
    try:
        notities = geheugen.notities_van(nu.date())
    except Exception:
        notities = []
    if notities:
        delen.append(("Je had voor vandaag genoteerd: %s." if taal == "nl" else "You noted for today: %s.")
                     % "; ".join(notities[:3]))
    if taal == "nl":
        delen.append("Fijne dag!")
    else:
        delen.append("Have a good day!")
    return uitspreekbaar(" ".join(delen)) if taal == "nl" else " ".join(delen)
