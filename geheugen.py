# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""geheugen.py - instellingen, het lopende gesprek en wat DraveJavis moet onthouden.

Alles staat lokaal in %APPDATA%\\DraveJavis (Windows) of ~/.drave_javis (andere systemen).
"""
from __future__ import annotations

import datetime
import json
import os

if os.name == "nt" and os.environ.get("APPDATA"):
    DATA = os.path.join(os.environ["APPDATA"], "DraveJavis")
else:
    DATA = os.path.join(os.path.expanduser("~"), ".drave_javis")

STANDAARD = dict(
    taal="nl", naam="", aanspreek="", server="http://127.0.0.1:9931/v1", model="",
    stem_aan=True, stem="Cole", snelheid=1.1, whisper="base", persoonlijkheid="",
    meteen_versturen=True, tekst_met_stem=True, online_zoeken=True, pc_acties=True, programma_mappen="", max_gesprek=30,
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


class Geheugen:
    def __init__(self):
        c = dict(STANDAARD)
        c.update(_lees("instellingen.json", {}) or {})
        self.cfg = c
        self.feiten = list(_lees("feiten.json", []) or [])
        self.gesprek = list(_lees("gesprek.json", []) or [])

    # ------------------------------------------------------------ instellingen
    def bewaar_cfg(self):
        _schrijf("instellingen.json", self.cfg)

    def modelmap(self):
        return _pad("whisper-modellen")

    # ------------------------------------------------------------ feiten
    def onthoud(self, feit):
        feit = feit.strip().rstrip(".")
        if feit and feit not in self.feiten:
            self.feiten.append(feit)
            _schrijf("feiten.json", self.feiten)
        return feit

    def vergeet(self, stukje):
        stukje = stukje.strip().lower()
        if stukje in ("alles", "everything", "all"):
            n = len(self.feiten)
            self.feiten = []
        else:
            oud = len(self.feiten)
            self.feiten = [f for f in self.feiten if stukje not in f.lower()]
            n = oud - len(self.feiten)
        _schrijf("feiten.json", self.feiten)
        return n

    # ------------------------------------------------------------ gesprek
    def voeg_toe(self, rol, tekst):
        self.gesprek.append(dict(role=rol, content=tekst))
        self.gesprek = self.gesprek[-int(self.cfg.get("max_gesprek", 30)) * 2:]
        _schrijf("gesprek.json", self.gesprek)

    def wis_gesprek(self):
        self.gesprek = []
        _schrijf("gesprek.json", self.gesprek)

    def berichten(self):
        """Systeemprompt + feiten + recent gesprek, klaar voor het taalmodel."""
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
