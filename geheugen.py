# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""geheugen.py - instellingen, het lopende gesprek en wat DraveJavis moet onthouden.

Alles staat lokaal in %APPDATA%\\DraveJavis (Windows) of ~/.drave_javis (andere systemen).

Het geheugen is "allebei":
- GEWONE TEKSTBESTANDEN die je zelf kunt lezen en aanpassen (map Geheugen):
    feiten.md                 wat je Javis vraagt te onthouden (één regel per feit)
    notities\\JJJJ-MM-DD.md    wat je laat noteren ("noteer ...")
    gesprekken\\JJJJ-MM-DD.md  het gesprek van die dag (uit te zetten in de instellingen)
- en een SNELLE ZOEKINDEX (zoekindex.db, SQLite) ernaast. Die wordt vanzelf opnieuw gemaakt
  als je zelf iets in de tekstbestanden verandert. Gooi je hem weg, dan maakt Javis hem gewoon opnieuw.
Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re
import sqlite3

if os.name == "nt" and os.environ.get("APPDATA"):
    DATA = os.path.join(os.environ["APPDATA"], "DraveJavis")
else:
    DATA = os.path.join(os.path.expanduser("~"), ".drave_javis")
GMAP = os.path.join(DATA, "Geheugen")

STANDAARD = dict(
    taal="nl", naam="", aanspreek="", server="http://127.0.0.1:9931/v1", model="",
    stem_aan=True, stem="Cole", snelheid=1.1, whisper="base", persoonlijkheid="",
    meteen_versturen=True, tekst_met_stem=True, online_zoeken=True, pc_acties=True, programma_mappen="", max_gesprek=30,
    plaats=None, ochtend_auto=True, laatste_ochtend="", gesprekken_bewaren=True,
)

PERSOONLIJKHEID = {
    "nl": ("Je bent DraveJavis, een slimme, beleefde en licht droog-gevatte persoonlijke assistent. "
           "Je draait helemaal lokaal op de pc van de gebruiker, zonder internet. "
           "Je antwoorden worden hardop uitgesproken: houd ze kort en duidelijk (meestal één tot drie zinnen), "
           "zonder opsommingstekens, tabellen of emoji, tenzij de gebruiker om meer uitleg vraagt. "
           "Antwoord in het Nederlands. Weet je iets niet zeker, zeg dat dan eerlijk; verzin niets, "
           "ook geen Windows-functies, menu's of cijfers. "
           "Je kunt zelf geen dingen op de pc veranderen."),
    "en": ("You are DraveJavis, a smart, polite and dryly witty personal assistant. "
           "You run fully locally on the user's computer, without internet. "
           "Your answers are spoken aloud: keep them short and clear (usually one to three sentences), "
           "without bullet points, tables or emoji unless the user asks for more detail. "
           "Answer in English. If you are not sure about something, say so honestly; never make things up. "
           "You cannot change things on the computer yourself."),
}

KOP_FEITEN = ("# Wat DraveJavis voor je onthoudt\n\n"
              "Eén feit per regel, beginnend met een streepje. Je mag dit bestand zelf aanpassen.\n\n")
STOP = set("de het een en of van in op te is dat die dit wat wie hoe waar wanneer mijn jouw je ik jij we wij "
           "zijn was er niet ook nog maar dan als om aan bij met voor over naar uit kan wil zou heb heeft "
           "the a an and or of in on to is that this what who how where when my your i you we are was".split())


def map_pad():
    """De map met de gewone tekstbestanden van het geheugen."""
    os.makedirs(GMAP, exist_ok=True)
    return GMAP


def _pad(naam):
    os.makedirs(DATA, exist_ok=True)
    return os.path.join(DATA, naam)


def _lees(naam, std):
    try:
        with open(_pad(naam), encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return std


def _schrijf(naam, data):
    p = _pad(naam)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


def _gpad(*delen):
    p = os.path.join(GMAP, *delen)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _voeg_regel(pad, kop, regel):
    nieuw = not os.path.exists(pad)
    with open(pad, "a", encoding="utf-8") as f:
        if nieuw:
            f.write(kop)
        f.write(regel.rstrip() + "\n")


class Geheugen:
    def __init__(self):
        c = dict(STANDAARD)
        c.update(_lees("instellingen.json", {}) or {})
        self.cfg = c
        self.gesprek = list(_lees("gesprek.json", []) or [])
        self._feiten_mtime = None
        self._migreer()
        self.feiten = self._lees_feiten()

    # ------------------------------------------------------------ instellingen
    def bewaar_cfg(self):
        _schrijf("instellingen.json", self.cfg)

    def modelmap(self):
        return _pad("whisper-modellen")

    def map(self):
        return map_pad()

    # ------------------------------------------------------------ feiten (feiten.md)
    def _migreer(self):
        """Eenmalig: de oude feiten.json omzetten naar feiten.md (de oude blijft als .bak bewaard)."""
        oud = _pad("feiten.json")
        fm = _gpad("feiten.md")
        if os.path.exists(oud) and not os.path.exists(fm):
            try:
                feiten = json.load(open(oud, encoding="utf-8-sig")) or []
                with open(fm, "w", encoding="utf-8") as f:
                    f.write(KOP_FEITEN + "".join("- %s\n" % x for x in feiten))
                os.replace(oud, oud + ".bak")
            except Exception:
                pass

    def _lees_feiten(self):
        fm = _gpad("feiten.md")
        try:
            self._feiten_mtime = os.path.getmtime(fm)
            with open(fm, encoding="utf-8-sig") as f:
                return [r[1:].strip() for r in f if r.lstrip().startswith("-") and r[1:].strip()]
        except Exception:
            return []

    def _schrijf_feiten(self):
        fm = _gpad("feiten.md")
        with open(fm + ".tmp", "w", encoding="utf-8") as f:
            f.write(KOP_FEITEN + "".join("- %s\n" % x for x in self.feiten))
        os.replace(fm + ".tmp", fm)
        self._feiten_mtime = os.path.getmtime(fm)

    def _ververs_feiten(self):
        """Heb je feiten.md zelf aangepast? Dan dat meteen gebruiken."""
        try:
            if os.path.getmtime(_gpad("feiten.md")) != self._feiten_mtime:
                self.feiten = self._lees_feiten()
        except Exception:
            pass

    def onthoud(self, feit):
        self._ververs_feiten()
        feit = feit.strip().rstrip(".")
        if feit and feit not in self.feiten:
            self.feiten.append(feit)
            self._schrijf_feiten()
        return feit

    def vergeet(self, stukje):
        self._ververs_feiten()
        stukje = stukje.strip().lower()
        if stukje in ("alles", "everything", "all"):
            n = len(self.feiten)
            self.feiten = []
        else:
            oud = len(self.feiten)
            self.feiten = [f for f in self.feiten if stukje not in f.lower()]
            n = oud - len(self.feiten)
        self._schrijf_feiten()
        return n

    # ------------------------------------------------------------ notities
    def noteer(self, tekst):
        nu = datetime.datetime.now()
        p = _gpad("notities", nu.strftime("%Y-%m-%d") + ".md")
        _voeg_regel(p, "# Notities van %s\n\n" % nu.strftime("%d-%m-%Y"), "- %s  %s" % (nu.strftime("%H:%M"), tekst.strip()))
        return tekst.strip()

    def notities_van(self, dag):
        """Voor het ochtendoverzicht: notities van vandaag, en die van gisteren waarin 'morgen' staat."""
        uit = []
        for d, alleen_morgen in ((dag - datetime.timedelta(days=1), True), (dag, False)):
            p = os.path.join(GMAP, "notities", d.strftime("%Y-%m-%d") + ".md")
            try:
                with open(p, encoding="utf-8-sig") as f:
                    for r in f:
                        if not r.lstrip().startswith("-"):
                            continue
                        t = re.sub(r"^-\s*\d{1,2}:\d{2}\s*", "", r.strip()).strip()
                        if t and (not alleen_morgen or re.search(r"\bmorgen\b|\btomorrow\b", t, re.I)):
                            uit.append(t)
            except Exception:
                pass
        return uit

    # ------------------------------------------------------------ gesprek
    def voeg_toe(self, rol, tekst):
        self.gesprek.append(dict(role=rol, content=tekst))
        self.gesprek = self.gesprek[-int(self.cfg.get("max_gesprek", 30)) * 2:]
        _schrijf("gesprek.json", self.gesprek)
        if self.cfg.get("gesprekken_bewaren", True) and rol in ("user", "assistant"):
            try:
                nu = datetime.datetime.now()
                p = _gpad("gesprekken", nu.strftime("%Y-%m-%d") + ".md")
                wie = "Jij" if rol == "user" else "Javis"
                _voeg_regel(p, "# Gesprek van %s\n\n" % nu.strftime("%d-%m-%Y"),
                            "- %s **%s:** %s" % (nu.strftime("%H:%M"), wie, " ".join(tekst.split())))
            except Exception:
                pass

    def wis_gesprek(self):
        self.gesprek = []
        _schrijf("gesprek.json", self.gesprek)

    # ------------------------------------------------------------ zoekindex (SQLite)
    def _bestanden(self):
        return [p for p in glob.glob(os.path.join(GMAP, "**", "*.md"), recursive=True)]

    def _index(self):
        """Open de zoekindex; maak hem opnieuw als een tekstbestand nieuwer is dan de index."""
        db = _pad("zoekindex.db")
        bestanden = self._bestanden()
        nieuwste = max([os.path.getmtime(p) for p in bestanden] or [0])
        opnieuw = (not os.path.exists(db)) or os.path.getmtime(db) < nieuwste
        con = sqlite3.connect(db)
        self._fts = True
        try:
            con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS regels USING fts5(tekst, soort UNINDEXED, datum UNINDEXED, pad UNINDEXED)")
        except sqlite3.OperationalError:
            self._fts = False
            con.execute("CREATE TABLE IF NOT EXISTS regels(tekst TEXT, soort TEXT, datum TEXT, pad TEXT)")
        if opnieuw:
            con.execute("DELETE FROM regels")
            for p in bestanden:
                rel = os.path.relpath(p, GMAP)
                soort = rel.split(os.sep)[0] if os.sep in rel else "feiten"
                datum = os.path.splitext(os.path.basename(p))[0] if soort != "feiten" else ""
                try:
                    with open(p, encoding="utf-8-sig") as f:
                        rijen = [(r.strip()[1:].strip(), soort, datum, rel) for r in f
                                 if r.strip().startswith("-") and len(r.strip()) > 3]
                except Exception:
                    continue
                con.executemany("INSERT INTO regels(tekst, soort, datum, pad) VALUES (?,?,?,?)", rijen)
            con.commit()
            os.utime(db, None)
        return con

    def zoek(self, vraag, n=5, zonder_vandaag=False):
        """Zoek in feiten, notities en gesprekken. Geeft [(datum, soort, tekst)]."""
        woorden = [w for w in re.findall(r"\w+", (vraag or "").lower()) if len(w) > 2 and w not in STOP]
        if not woorden:
            return []
        try:
            con = self._index()
        except Exception:
            return []
        vandaag = datetime.date.today().strftime("%Y-%m-%d")
        try:
            if self._fts:
                q = " OR ".join('"%s"*' % w.replace('"', "") for w in woorden[:8])
                rijen = con.execute("SELECT datum, soort, tekst FROM regels WHERE regels MATCH ? ORDER BY bm25(regels) LIMIT ?",
                                    (q, n * 3)).fetchall()
            else:
                rijen = []
                for w in woorden[:4]:
                    rijen += con.execute("SELECT datum, soort, tekst FROM regels WHERE lower(tekst) LIKE ? LIMIT ?",
                                         ("%" + w + "%", n * 2)).fetchall()
        except Exception:
            rijen = []
        finally:
            con.close()
        uit, gezien = [], set()
        for d, s, t in rijen:
            if zonder_vandaag and s == "gesprekken" and d == vandaag:
                continue
            if t in gezien:
                continue
            gezien.add(t)
            uit.append((d, s, t))
            if len(uit) >= n:
                break
        return uit

    # ------------------------------------------------------------ voor het taalmodel
    def berichten(self):
        """Systeemprompt + feiten + wat relevant is uit het geheugen + recent gesprek."""
        self._ververs_feiten()
        taal = self.cfg.get("taal", "nl")
        tekst = (self.cfg.get("persoonlijkheid") or "").strip() or PERSOONLIJKHEID.get(taal, PERSOONLIJKHEID["nl"])
        nu = datetime.datetime.now()
        if taal == "nl":
            dagen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
            maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                       "september", "oktober", "november", "december"]
            tekst += "\nHet is nu %s %d %s %d, %02d:%02d." % (dagen[nu.weekday()], nu.day, maanden[nu.month - 1],
                                                             nu.year, nu.hour, nu.minute)
            if self.cfg.get("naam"):
                tekst += "\nDe gebruiker heet %s." % self.cfg["naam"]
            if self.cfg.get("aanspreek"):
                tekst += " Spreek de gebruiker aan als '%s'." % self.cfg["aanspreek"]
            if self.feiten:
                tekst += "\nDit heeft de gebruiker je gevraagd te onthouden:\n- " + "\n- ".join(self.feiten)
        else:
            tekst += "\nIt is now %s, %02d:%02d." % (nu.strftime("%A %d %B %Y"), nu.hour, nu.minute)
            if self.cfg.get("naam"):
                tekst += "\nThe user's name is %s." % self.cfg["naam"]
            if self.cfg.get("aanspreek"):
                tekst += " Address the user as '%s'." % self.cfg["aanspreek"]
            if self.feiten:
                tekst += "\nThe user asked you to remember:\n- " + "\n- ".join(self.feiten)
        # relevante herinneringen uit eerdere notities en gesprekken (snelle zoekindex)
        laatste = next((m["content"] for m in reversed(self.gesprek) if m["role"] == "user"), "")
        treffers = [t for t in self.zoek(laatste, n=4, zonder_vandaag=True) if t[1] != "feiten"]
        if treffers:
            regels = "\n".join("- (%s, %s) %s" % (d or "?", s, re.sub(r"\*\*", "", t)) for d, s, t in treffers)
            tekst += (("\nMisschien relevant uit eerdere notities en gesprekken (gebruik het alleen als het echt past, "
                       "en zeg erbij dat het uit je geheugen komt):\n") if taal == "nl" else
                      "\nPossibly relevant from earlier notes and conversations (use only if it truly fits):\n") + regels
        if self.cfg.get("online_zoeken", True):
            if taal == "nl":
                tekst += ("\nHeb je voor een goed antwoord actuele informatie van internet nodig (nieuws, weer, "
                          "prijzen, uitslagen, openingstijden, recente gebeurtenissen of iets wat je niet zeker weet)? "
                          "Antwoord dan ALLEEN met één regel: ZOEK: <korte zoekterm>. De app zoekt het dan op "
                          "en geeft jou de resultaten.")
            else:
                tekst += ("\nIf you need current information from the internet for a good answer (news, weather, "
                          "prices, scores, opening hours, recent events or anything you're unsure of), reply ONLY "
                          "with one line: ZOEK: <short search query>. The app will search and give you the results.")
        if self.cfg.get("pc_acties", True):
            import pc
            lijst = "\n".join("- %s: %s" % (k, v) for k, v in pc.ACTIES.items())
            if taal == "nl":
                tekst += ("\nJe kunt een paar dingen op de pc doen. Vraagt de gebruiker daarom, antwoord dan ALLEEN met "
                          "één regel: ACTIE: <naam> | <argument>. Mogelijke acties:\n" + lijst +
                          "\nGebruik nooit een andere actie dan deze. Doe niets wat de gebruiker niet vraagt.")
            else:
                tekst += ("\nYou can do a few things on the computer. If the user asks for one, reply ONLY with one "
                          "line: ACTIE: <name> | <argument>. Possible actions:\n" + lijst +
                          "\nNever use any other action. Never do anything the user didn't ask for.")
        return [dict(role="system", content=tekst)] + list(self.gesprek)
