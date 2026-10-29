# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""geheugen.py - instellingen, het lopende gesprek en wat DraveJavis moet onthouden.

Alles staat lokaal in de map DraveJavis-data naast de app (portable; niets in AppData of op C:
tenzij de app zelf op C: staat). Een oude map in %APPDATA%\\DraveJavis wordt eenmalig verhuisd.

Het geheugen is "allebei":
- GEWONE TEKSTBESTANDEN die je zelf kunt lezen en aanpassen (map Geheugen):
    laatjes\\<onderwerp>.md   wat je Javis vraagt te onthouden, per laatje (Mensen, Interesses, ...)
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
import shutil
import sqlite3
import sys

# Portable (29-10-2026): de gegevens staan naast de app, niet in AppData.
_BASIS = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
DATA = os.path.join(_BASIS, "DraveJavis-data")
_OUD = (os.path.join(os.environ["APPDATA"], "DraveJavis") if os.name == "nt" and os.environ.get("APPDATA")
        else os.path.join(os.path.expanduser("~"), ".drave_javis"))
if not os.path.isdir(DATA) and os.path.isdir(_OUD):
    try:                                   # eenmalig verhuizen; de oude map blijft als reserve staan
        shutil.copytree(_OUD, DATA)
        with open(os.path.join(_OUD, "VERHUISD.txt"), "w", encoding="utf-8") as _f:
            _f.write("DraveJavis bewaart alles nu in: %s\nDeze map mag je zelf weggooien.\n" % DATA)
    except Exception:
        pass
GMAP = os.path.join(DATA, "Geheugen")

# Het geheugen in laatjes, zoals mensen onthouden (29-10-2026). Een feit gaat naar het laatje
# waarvan een woord in het feit voorkomt; anders naar Overig. Bij een vraag gaat het juiste laatje eerst.
LAATJES = [
    ("Mensen", "vrouw man vriend vriendin moeder vader zoon dochter broer zus opa oma oom tante kind kinderen "
               "familie collega buurman buurvrouw baas partner neef nicht verjaardag jarig "
               "wife husband friend mother father son daughter brother sister family colleague neighbour birthday"),
    ("Dieren", "hond kat poes konijn vogel paard vis huisdier dier dog cat pet horse bird"),
    ("Interesses", "hobby graag leuk favoriet lievelings houd hou muziek film serie boek spel game sport "
                   "voetbal tekenen schilderen koken fotografie like love favourite favorite music movie book"),
    ("Eten", "eten drinken lust allergie allergisch vegetarisch recept koffie thee food drink allergic coffee tea"),
    ("Werk", "werk baan bedrijf kantoor school studie opleiding cursus les job work company office study"),
    ("Thuis", "huis woning adres straat woon woont wonen auto fiets tuin home house address street car garden"),
    ("Afspraken", "afspraak afspraken altijd nooit elke iedere regel wil niet herinner remind always never rule"),
]
LA_OVERIG = "Overig"
KOP_LA = ("# %s\n\nWat DraveJavis voor je onthoudt in dit laatje. Eén feit per regel, beginnend met een streepje. "
          "Je mag dit bestand zelf aanpassen.\n\n")


_WW_EIND = set("heet heten is ben bent zijn was waren woont woon wonen werkt werk werken houdt hou houden "
               "heeft heb hebt hebben wil wilt willen kan kun kunt kunnen mag mogen moet moeten eet eten "
               "drinkt drink speelt speel rijdt rijd doet doe leest lees zit staat ligt komt kom gaat ga "
               "vindt vind lust lusten studeert studeer verjaart".split())
_ONDERWERP_1 = {"ik", "jij", "je", "hij", "zij", "ze", "wij", "we", "u", "het"}
_LIDWOORD = {"mijn", "m'n", "onze", "ons", "de", "het", "een", "zijn", "haar", "hun", "jouw"}


def hoofdzin(feit):
    """'mijn hond Kira heet' (bijzin na 'onthoud dat') -> 'mijn hond heet Kira' (29-10-2026)."""
    w = (feit or "").split()
    if len(w) < 3 or w[-1].lower() not in _WW_EIND:
        return feit
    if w[0].lower() in _ONDERWERP_1:
        n = 1
    elif w[0].lower() in _LIDWOORD:
        n = 2
    else:
        return feit
    if len(w) <= n + 1:
        return feit
    return " ".join(w[:n] + [w[-1]] + w[n:-1])


def kies_laatje(tekst):
    w = set(re.findall(r"\w+", (tekst or "").lower()))
    beste, score = LA_OVERIG, 0
    for la, woorden in LAATJES:
        n = len(w & set(woorden.split()))
        if n > score:
            beste, score = la, n
    return beste

STANDAARD = dict(
    taal="nl", naam="", aanspreek="", server="http://127.0.0.1:9931/v1", model="",
    stem_aan=True, stem="Leon", snelheid=1.1, whisper="base", persoonlijkheid="",
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
           "Je kunt zelf geen dingen op de pc veranderen. "
           "Eindig je antwoord niet steeds met een wedervraag zoals 'kan ik nog ergens mee helpen?'; "
           "stel alleen een vraag terug als dat echt nodig is."),
    "en": ("You are DraveJavis, a smart, polite and dryly witty personal assistant. "
           "You run fully locally on the user's computer, without internet. "
           "Your answers are spoken aloud: keep them short and clear (usually one to three sentences), "
           "without bullet points, tables or emoji unless the user asks for more detail. "
           "Answer in English. If you are not sure about something, say so honestly; never make things up. "
           "You cannot change things on the computer yourself. "
           "Don't keep ending your answer with a question like 'anything else I can help with?'; "
           "only ask something back when it is really needed."),
}

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
        self.feit_la = {}
        self.laatste_la = LA_OVERIG
        self._migreer()
        self.feiten = self._lees_feiten()

    # ------------------------------------------------------------ instellingen
    def bewaar_cfg(self):
        _schrijf("instellingen.json", self.cfg)

    def modelmap(self):
        return _pad("whisper-modellen")

    def map(self):
        return map_pad()

    # ------------------------------------------------------------ feiten, in laatjes (29-10-2026)
    def _lamap(self):
        p = os.path.join(GMAP, "laatjes")
        os.makedirs(p, exist_ok=True)
        return p

    def _migreer(self):
        """Eenmalig: oude feiten.json -> feiten.md -> laatjes (de oude bestanden blijven als .bak bewaard)."""
        oud = _pad("feiten.json")
        fm = _gpad("feiten.md")
        if os.path.exists(oud) and not os.path.exists(fm):
            try:
                feiten = json.load(open(oud, encoding="utf-8-sig")) or []
                with open(fm, "w", encoding="utf-8") as f:
                    f.write("".join("- %s\n" % x for x in feiten))
                os.replace(oud, oud + ".bak")
            except Exception:
                pass
        if os.path.exists(fm):
            try:
                with open(fm, encoding="utf-8-sig") as f:
                    feiten = [r[1:].strip() for r in f if r.lstrip().startswith("-") and r[1:].strip()]
                per = {}
                for x in feiten:
                    per.setdefault(kies_laatje(x), []).append(x)
                for la, lijst in per.items():
                    lp = os.path.join(self._lamap(), la + ".md")
                    bestaand = self._lees_la(lp)
                    with open(lp, "w", encoding="utf-8") as f:
                        f.write(KOP_LA % la + "".join("- %s\n" % x for x in bestaand + [y for y in lijst if y not in bestaand]))
                os.replace(fm, fm + ".voor_laatjes.bak")
            except Exception:
                pass

    @staticmethod
    def _lees_la(pad):
        try:
            with open(pad, encoding="utf-8-sig") as f:
                return [r.strip()[1:].strip() for r in f if r.lstrip().startswith("-") and r.strip()[1:].strip()]
        except Exception:
            return []

    def _stempel(self):
        try:
            return tuple(sorted((n, os.path.getmtime(os.path.join(self._lamap(), n)))
                                for n in os.listdir(self._lamap()) if n.endswith(".md")))
        except Exception:
            return ()

    def _lees_feiten(self):
        self.feit_la = {}
        uit = []
        for n in sorted(os.listdir(self._lamap())):
            if not n.endswith(".md"):
                continue
            la = n[:-3]
            for x in self._lees_la(os.path.join(self._lamap(), n)):
                if x not in self.feit_la:
                    self.feit_la[x] = la
                    uit.append(x)
        self._feiten_mtime = self._stempel()
        return uit

    def _schrijf_feiten(self):
        per = {}
        for x in self.feiten:
            per.setdefault(self.feit_la.get(x, LA_OVERIG), []).append(x)
        for n in os.listdir(self._lamap()):                  # leeg geworden laatjes leegmaken
            if n.endswith(".md") and n[:-3] not in per:
                per[n[:-3]] = []
        for la, lijst in per.items():
            lp = os.path.join(self._lamap(), la + ".md")
            with open(lp + ".tmp", "w", encoding="utf-8") as f:
                f.write(KOP_LA % la + "".join("- %s\n" % x for x in lijst))
            os.replace(lp + ".tmp", lp)
        self._feiten_mtime = self._stempel()

    def _ververs_feiten(self):
        """Heb je een laatje zelf aangepast? Dan dat meteen gebruiken."""
        if self._stempel() != self._feiten_mtime:
            self.feiten = self._lees_feiten()

    def onthoud(self, feit):
        self._ververs_feiten()
        feit = hoofdzin(feit.strip().rstrip("."))
        self.laatste_la = self.feit_la.get(feit) or kies_laatje(feit)
        if feit and feit not in self.feiten:
            self.feiten.append(feit)
            self.feit_la[feit] = self.laatste_la
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

    def overzicht(self, per_la=4):
        """Kort overzicht per laatje: [(laatje, [feiten])]."""
        self._ververs_feiten()
        per = {}
        for x in self.feiten:
            per.setdefault(self.feit_la.get(x, LA_OVERIG), []).append(x)
        return [(la, lijst[-per_la:]) for la, lijst in sorted(per.items())]

    def feiten_voor(self, vraag, max_alle=40):
        """De feiten voor het taalmodel, per laatje. Bij veel feiten: eerst het juiste laatje."""
        per = {}
        for x in self.feiten:
            per.setdefault(self.feit_la.get(x, LA_OVERIG), []).append(x)
        if len(self.feiten) > max_alle:
            la = kies_laatje(vraag)
            per = {k: (v if k == la else v[-3:]) for k, v in per.items()}
        return per

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
                if soort == "laatjes":
                    soort = "feiten"           # datum = de naam van het laatje
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
        laatste_vraag = next((m["content"] for m in reversed(self.gesprek) if m["role"] == "user"), "")
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
                n = self.cfg["naam"]
                tekst += ("\nDe gebruiker heet %s. %s is degene met wie je nu praat: jouw gebruiker, voor wie jij "
                          "werkt en die je helpt. Spreek %s aan met 'je' of 'jij'. Vraagt %s 'wie ben ik?' of "
                          "'wie ben ik voor jou?', zeg dan warm dat het %s is, de persoon voor wie jij er bent, en "
                          "noem kort wat je over %s onthouden hebt." % (n, n, n, n, n, n))
            if self.cfg.get("aanspreek"):
                tekst += " Spreek de gebruiker aan als '%s'." % self.cfg["aanspreek"]
            if self.feiten:
                per = self.feiten_voor(laatste_vraag)
                tekst += "\nDit heeft de gebruiker je gevraagd te onthouden (per onderwerp):" + "".join(
                    "\n%s: %s" % (la, "; ".join(v)) for la, v in sorted(per.items()) if v)
        else:
            tekst += "\nIt is now %s, %02d:%02d." % (nu.strftime("%A %d %B %Y"), nu.hour, nu.minute)
            if self.cfg.get("naam"):
                n = self.cfg["naam"]
                tekst += ("\nThe user's name is %s. %s is the person you are talking to now: your user, the one you "
                          "work for and help. If %s asks 'who am I?' or 'who am I to you?', say warmly that they are "
                          "%s, the person you are there for, and briefly mention what you remember about %s."
                          % (n, n, n, n, n))
            if self.cfg.get("aanspreek"):
                tekst += " Address the user as '%s'." % self.cfg["aanspreek"]
            if self.feiten:
                per = self.feiten_voor(laatste_vraag)
                tekst += "\nThe user asked you to remember (by topic):" + "".join(
                    "\n%s: %s" % (la, "; ".join(v)) for la, v in sorted(per.items()) if v)
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
