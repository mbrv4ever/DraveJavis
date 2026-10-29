# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""DraveJavis - een persoonlijke spraakassistent die helemaal op je eigen pc draait.

* Brein: een lokaal taalmodel via een OpenAI-compatibele server (Llama-app, LM Studio, Ollama, ...)
* Stem:  neuvoice (neurale tekst-naar-spraak, offline)
* Oren:  houd de microfoonknop (of F2) ingedrukt en praat; faster-whisper maakt er tekst van (offline)

Dravenlock (Roger & Claudio), 2026. Zie README.md en LICENSE.
"""
from __future__ import annotations

import datetime
import html
import math
import os
import re
import sys
import threading
import time
import webbrowser

from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QRadialGradient, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, QPushButton, QLineEdit, QTextBrowser,
                             QHBoxLayout, QVBoxLayout, QDialog, QFormLayout, QComboBox, QCheckBox,
                             QDoubleSpinBox, QTextEdit, QMessageBox, QDialogButtonBox, QSizePolicy,
                             QScrollArea, QFrame)

import brein as B
import drave_motor as DM
import geheugen as G
import oren as O
import stem as S
import vaardigheden as V
import zoeken as Z
import pc as P
import ochtend as OC

APP = "DraveJavis"
VERSIE = "1.2.0"


def hier(*p):
    basis = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False)
                                                                         else __file__)))
    return os.path.join(basis, *p)


T = {
    "nl": dict(
        sub="je persoonlijke assistent, helemaal op je eigen pc", typ="Typ hier, of houd de microfoon ingedrukt...",
        stuur="Verstuur", mic="🎙  Houd vast en praat", mic_aan="🔴  Ik luister... laat los als je klaar bent",
        stop="■  Stil", nieuw="Nieuw gesprek", instel="Instellingen", jij="Jij", denkt="denkt na...",
        luistert="luistert", spreekt="spreekt", rust="klaar", fout="Oeps", zoekt="zoekt online",
        bronnen="Bronnen", niets_gevonden="Ik kon daar online niets over vinden.",
        welkom=("Goedendag! Ik ben DraveJavis. Typ iets, of houd de microfoonknop (of F2) ingedrukt en praat. "
                "Ik denk met een lokaal taalmodel. Het makkelijkst is mijn eigen motor: kies Instellingen -> "
                "Motor downloaden (eenmalig ongeveer 2 GB). Een Llama-app, LM Studio of Ollama kan ook."),
        geen_tekst="Ik verstond niets. Probeer het nog eens, iets dichter bij de microfoon.",
        timer_klaar="Je timer van %s is klaar!", omzetten="even omzetten naar tekst...",
        stem_status=dict(uit="stem: wacht", laden="stem: laden (eerste keer downloaden)...", klaar="stem: klaar",
                         mislukt="stem: mislukt", geen_neuvoice="stem: neuvoice ontbreekt",
                         geen_geluid="stem: geen geluid"),
        oor_status=dict(klaar="microfoon: klaar", laden="spraakherkenning: laden (eerste keer downloaden)...",
                        mislukt="spraakherkenning: mislukt", geen_whisper="spraakherkenning ontbreekt",
                        geen_microfoon="geen microfoon"),
    ),
    "en": dict(
        sub="your personal assistant, entirely on your own computer", typ="Type here, or hold the microphone...",
        stuur="Send", mic="🎙  Hold and speak", mic_aan="🔴  Listening... release when done",
        stop="■  Quiet", nieuw="New chat", instel="Settings", jij="You", denkt="thinking...",
        luistert="listening", spreekt="speaking", rust="ready", fout="Oops", zoekt="searching online",
        bronnen="Sources", niets_gevonden="I couldn't find anything about that online.",
        welkom=("Good day! I'm DraveJavis. Type something, or hold the microphone button (or F2) and speak. "
                "I need a local language model: start the Llama app (or LM Studio / Ollama) and load a model."),
        geen_tekst="I didn't catch that. Please try again, a bit closer to the microphone.",
        timer_klaar="Your %s timer is done!", omzetten="converting speech to text...",
        stem_status=dict(uit="voice: waiting", laden="voice: loading (first time: downloading)...",
                         klaar="voice: ready", mislukt="voice: failed", geen_neuvoice="voice: neuvoice missing",
                         geen_geluid="voice: no audio"),
        oor_status=dict(klaar="microphone: ready", laden="speech recognition: loading (first time: downloading)...",
                        mislukt="speech recognition: failed", geen_whisper="speech recognition missing",
                        geen_microfoon="no microphone"),
    ),
}

STIJL = """
QWidget { background:#05080f; color:#dfe9f5; font-family:'Segoe UI'; font-size:18px; }
QLabel#titel { font-size:34px; font-weight:bold; color:#ffffff; letter-spacing:2px; }
QLabel#sub { color:#39d0ff; font-size:16px; }
QLabel#status { color:#7f93ab; font-size:15px; }
QLabel#toestand { color:#39d0ff; font-size:20px; font-weight:bold; letter-spacing:3px; }
QPushButton { background:#0b1424; color:#e8f3ff; border:2px solid #1f6f99; border-radius:10px; padding:10px 16px; }
QPushButton:hover { border-color:#39d0ff; background:#0f1d33; }
QPushButton#mic { font-size:21px; font-weight:bold; padding:16px; border:3px solid #39d0ff; }
QPushButton#mic[aan="true"] { background:#3a0d14; border-color:#ff5a6e; }
QPushButton#goud { border-color:#ffb347; }
QLineEdit { background:#0b1424; border:2px solid #1f6f99; border-radius:10px; padding:12px; font-size:19px; }
QLineEdit:focus { border-color:#39d0ff; }
QTextBrowser { background:#070c16; border:2px solid #14324a; border-radius:12px; padding:8px; font-size:19px; }
QComboBox, QDoubleSpinBox, QTextEdit { background:#0b1424; border:2px solid #1f6f99; border-radius:8px; padding:6px; }
QCheckBox { spacing:10px; }
"""


# =============================================================================== de kern
class Kern(QWidget):
    """De gloeiende, draaiende kern. Eigen ontwerp (ringen en segmenten)."""

    KLEUR = {"rust": QColor(57, 208, 255), "denkt": QColor(255, 179, 71), "luistert": QColor(90, 255, 160),
             "spreekt": QColor(57, 208, 255), "zoekt": QColor(190, 120, 255)}

    def __init__(self, niveau_fn, toestand_fn):
        super().__init__()
        self.niveau_fn = niveau_fn
        self.toestand_fn = toestand_fn
        self.hoek = 0.0
        self.puls = 0.0
        self.setMinimumSize(340, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.klok = QTimer(self)
        self.klok.timeout.connect(self._tik)
        self.klok.start(33)

    def _tik(self):
        st = self.toestand_fn()
        self.hoek += {"rust": 0.6, "denkt": 4.5, "luistert": 1.5, "spreekt": 1.2, "zoekt": 3.0}.get(st, 0.6)
        doel = self.niveau_fn()
        self.puls += (doel - self.puls) * 0.35
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        r = min(w, h) * 0.42
        st = self.toestand_fn()
        kl = self.KLEUR.get(st, self.KLEUR["rust"])
        t = time.time()
        adem = 0.5 + 0.5 * math.sin(t * (1.2 if st == "rust" else 3.0))
        sterk = max(self.puls, 0.15 + 0.15 * adem)
        # gloed
        g = QRadialGradient(c, r * 1.15)
        g.setColorAt(0.0, QColor(kl.red(), kl.green(), kl.blue(), int(70 + 120 * sterk)))
        g.setColorAt(0.45, QColor(kl.red(), kl.green(), kl.blue(), int(25 + 40 * sterk)))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, r * 1.15, r * 1.15)
        # buitenste segmentring
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(24):
            a = self.hoek + i * 15
            dikte = 0.5 + 0.5 * math.sin(math.radians(a * 2) + t)
            pen = QPen(QColor(kl.red(), kl.green(), kl.blue(), int(90 + 140 * dikte)), max(3, r * 0.045))
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            rr = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
            p.drawArc(rr, int(a * 16), int(9 * 16))
        # middelste ring, tegen de klok in
        r2 = r * 0.74
        pen = QPen(QColor(255, 179, 71, 200), max(2, r * 0.02))
        p.setPen(pen)
        for i in range(3):
            a = -self.hoek * 1.6 + i * 120
            p.drawArc(QRectF(c.x() - r2, c.y() - r2, 2 * r2, 2 * r2), int(a * 16), int(70 * 16))
        # golfring (beweegt mee met het geluid)
        r3 = r * 0.55
        pen = QPen(QColor(kl.red(), kl.green(), kl.blue(), 230), max(2, r * 0.025))
        p.setPen(pen)
        punten = []
        for i in range(0, 361, 6):
            a = math.radians(i)
            golf = math.sin(a * 6 + t * 5) * r * 0.06 * self.puls + math.sin(a * 11 - t * 3) * r * 0.03 * self.puls
            rr = r3 + golf
            punten.append(QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a)))
        for i in range(len(punten) - 1):
            p.drawLine(punten[i], punten[i + 1])
        # hart
        r4 = r * (0.24 + 0.06 * sterk)
        g2 = QRadialGradient(c, r4)
        g2.setColorAt(0.0, QColor(255, 255, 255, 255))
        g2.setColorAt(0.35, QColor(kl.red(), kl.green(), kl.blue(), 255))
        g2.setColorAt(1.0, QColor(kl.red() // 3, kl.green() // 3, kl.blue() // 3, 255))
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.setBrush(g2)
        p.drawEllipse(c, r4, r4)
        p.end()


# =============================================================================== signalen
class Sein(QObject):
    stukje = pyqtSignal(str)
    klaar = pyqtSignal(str)
    fout = pyqtSignal(str)
    gehoord = pyqtSignal(str)
    begin = pyqtSignal(str)
    pc = pyqtSignal(object)
    modellen = pyqtSignal(list)
    zeg = pyqtSignal(str)


# =============================================================================== instellingen
class Instellingen(QDialog):
    def __init__(self, ouder, cfg, stemmen):
        super().__init__(ouder)
        self.setWindowTitle("%s - instellingen" % APP)
        self.setStyleSheet(STIJL)
        # schuif-instellingen-1.1.2: past op elk scherm; knoppen blijven altijd onderaan zichtbaar
        try:
            _sg = QApplication.primaryScreen().availableGeometry(); _w, _h = _sg.width(), _sg.height()
        except Exception:
            _w, _h = 1280, 800
        self.cfg = dict(cfg)
        buiten = QVBoxLayout(self)
        _vak = QScrollArea(); _vak.setWidgetResizable(True); _vak.setFrameShape(QFrame.Shape.NoFrame)
        _bin = QWidget(); _vak.setWidget(_bin); buiten.addWidget(_vak, 1)
        f = QFormLayout(_bin)
        f.setVerticalSpacing(12)
        self.taal = QComboBox(); self.taal.addItem("Nederlands", "nl"); self.taal.addItem("English", "en")
        self.taal.setCurrentIndex(0 if cfg.get("taal") == "nl" else 1)
        f.addRow("Taal / language", self.taal)
        self.naam = QLineEdit(cfg.get("naam", "")); f.addRow("Jouw naam", self.naam)
        self.aanspreek = QLineEdit(cfg.get("aanspreek", ""))
        self.aanspreek.setPlaceholderText("bijv. meneer, mevrouw, of je voornaam")
        f.addRow("Spreek me aan als", self.aanspreek)
        self.server_keuze = QComboBox()
        for naam, url in B.SERVERS:
            self.server_keuze.addItem("%s  (%s)" % (naam, url.split("//")[1].split("/")[0]), url)
        self.server_keuze.addItem("Eigen adres...", "")
        self.server = QLineEdit(cfg.get("server", B.SERVERS[0][1]))
        idx = [u for _, u in B.SERVERS].index(self.server.text()) if self.server.text() in [u for _, u in B.SERVERS] \
            else len(B.SERVERS)
        self.server_keuze.setCurrentIndex(idx)
        self.server_keuze.currentIndexChanged.connect(self._server)
        # ---- eigen motor (DraveMotor, 29-10-2026)
        self.motor_aan = QCheckBox("Eigen motor gebruiken (aanbevolen: geen losse app nodig)")
        self.motor_aan.setChecked(cfg.get("motor_aan", True))
        f.addRow("Motor", self.motor_aan)
        self._motor = DM.van_cfg(cfg)
        self.motor_lab = QLabel(); self.motor_lab.setWordWrap(True)
        mrij = QHBoxLayout(); mrij.addWidget(self.motor_lab, 1)
        self.motor_knop = QPushButton("Motor downloaden..."); self.motor_knop.clicked.connect(self._motor_download)
        mrij.addWidget(self.motor_knop)
        f.addRow("", mrij)
        self._motor_tekst = ""
        self._motor_bezig = False
        self._motor_klok = QTimer(self); self._motor_klok.timeout.connect(self._motor_ververs); self._motor_klok.start(500)
        self._motor_ververs()
        f.addRow("Taalmodel-server", self.server_keuze)
        f.addRow("Adres", self.server)
        rij = QHBoxLayout()
        self.model = QComboBox(); self.model.setEditable(True)
        self.model.addItem("(automatisch kiezen)", "")
        if cfg.get("model"):
            self.model.addItem(cfg["model"], cfg["model"]); self.model.setCurrentIndex(1)
        rij.addWidget(self.model, 1)
        tb = QPushButton("Zoek modellen"); tb.clicked.connect(self._zoek); rij.addWidget(tb)
        f.addRow("Model", rij)
        self.stem_aan = QCheckBox("Antwoorden hardop uitspreken"); self.stem_aan.setChecked(cfg.get("stem_aan", True))
        f.addRow("Stem", self.stem_aan)
        self.stem = QComboBox(); self.stem.setEditable(True)
        for s in (stemmen or ["Leon", "Cole", "Cem", "Giray", "Mustafa", "Sarp", "Soras", "Alina", "Lina", "Linda", "Selin", "Sema"]):
            self.stem.addItem(s)
        self.stem.setCurrentText(cfg.get("stem", "Leon"))
        f.addRow("Welke stem", self.stem)
        self.snelheid = QDoubleSpinBox(); self.snelheid.setRange(0.6, 1.8); self.snelheid.setSingleStep(0.05)
        self.snelheid.setValue(float(cfg.get("snelheid", 1.05)))
        f.addRow("Spreeksnelheid", self.snelheid)
        self.whisper = QComboBox()
        for sl, uitleg in O.MODELLEN:
            self.whisper.addItem("%s - %s" % (sl, uitleg), sl)
        self.whisper.setCurrentIndex([s for s, _ in O.MODELLEN].index(cfg.get("whisper", "base"))
                                     if cfg.get("whisper") in dict(O.MODELLEN) else 1)
        f.addRow("Spraakherkenning", self.whisper)
        self.sync = QCheckBox("Tekst tegelijk met de stem tonen")
        self.sync.setChecked(cfg.get("tekst_met_stem", True))
        f.addRow("", self.sync)
        self.pcacties = QCheckBox("Dingen op de pc laten doen (programma's, geluid, bestanden, opruimen)")
        self.pcacties.setChecked(cfg.get("pc_acties", True))
        f.addRow("Pc", self.pcacties)
        self.progmappen = QLineEdit(cfg.get("programma_mappen", ""))
        self.progmappen.setPlaceholderText("Extra mappen met eigen programma's, gescheiden door ;  (mag leeg)")
        f.addRow("Eigen programma's", self.progmappen)
        self.online = QCheckBox("Online zoeken toestaan (alleen de zoekvraag gaat het internet op)")
        self.online.setChecked(cfg.get("online_zoeken", True))
        f.addRow("Internet", self.online)
        self.meteen = QCheckBox("Na het praten meteen versturen")
        self.meteen.setChecked(cfg.get("meteen_versturen", True))
        f.addRow("", self.meteen)
        self.ochtend = QCheckBox("Ochtendoverzicht bij de eerste start van de dag (weer + agenda)")
        self.ochtend.setChecked(cfg.get("ochtend_auto", True))
        f.addRow("Ochtend", self.ochtend)
        pl = cfg.get("plaats") or {}
        self.plaats_lab = QLabel(("Plaats voor het weer: %s  (wijzig door te zeggen: 'mijn plaats is ...')" % pl["naam"])
                                 if pl.get("naam") else "Nog geen plaats. Zeg of typ: 'mijn plaats is Amsterdam'.")
        self.plaats_lab.setWordWrap(True)
        f.addRow("", self.plaats_lab)
        self.bewaren = QCheckBox("Gesprekken bewaren in de geheugenmap (gewone tekstbestanden)")
        self.bewaren.setChecked(cfg.get("gesprekken_bewaren", True))
        rij2 = QHBoxLayout(); rij2.addWidget(self.bewaren, 1)
        gm = QPushButton("Geheugenmap openen"); gm.clicked.connect(lambda: os.startfile(G.map_pad()))
        rij2.addWidget(gm)
        f.addRow("Geheugen", rij2)
        self.pers = QTextEdit(); self.pers.setAcceptRichText(False); self.pers.setFixedHeight(130)
        self.pers.setPlainText(cfg.get("persoonlijkheid", ""))
        self.pers.setPlaceholderText("Leeg = standaard persoonlijkheid. Of beschrijf zelf hoe DraveJavis moet zijn.")
        f.addRow("Persoonlijkheid", self.pers)
        kn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        kn.accepted.connect(self.accept); kn.rejected.connect(self.reject)
        buiten.addWidget(kn)
        _vak.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _bw = _bin.minimumSizeHint().width() + 46
        self.resize(min(max(760, _bw), _w - 40), min(760, _h - 80))

    def _motor_ververs(self):
        if self._motor_bezig:
            self.motor_lab.setText(self._motor_tekst)
            return
        if self._motor.klaar():
            self.motor_lab.setText("✔ %s staat klaar in %s" % (self._motor.naam, os.path.dirname(self._motor.model)))
            self.motor_knop.setText("Andere map...")
        else:
            self.motor_lab.setText(self._motor_tekst or "Nog niet gedownload. Eenmalig ongeveer 2 GB (motor + model %s)."
                                   % self._motor.naam)
            self.motor_knop.setText("Motor downloaden...")

    def _motor_download(self):
        from PyQt6.QtWidgets import QFileDialog
        if self._motor_bezig:
            return
        start = self._motor.map if os.path.isdir(os.path.dirname(self._motor.map) or ".") else DM.standaard_map()
        d = QFileDialog.getExistingDirectory(self, "Kies de map voor de motor en het model (liefst niet op C:)",
                                             os.path.dirname(start) if not os.path.isdir(start) else start)
        if not d:
            return
        if d[:2].upper() == "C:" and QMessageBox.question(
                self, APP, "Dit is schijf C:. Het model is ongeveer 2 GB. Toch hier neerzetten?") \
                != QMessageBox.StandardButton.Yes:
            return
        self._motor = DM.Motor(d)
        if self._motor.klaar():
            self._motor_tekst = ""
            self._motor_ververs()
            return
        self._motor_bezig = True
        self._motor_tekst = "Downloaden..."
        self.motor_knop.setEnabled(False)

        def werk():
            try:
                self._motor.download(lambda t: setattr(self, "_motor_tekst", t))
                self._motor_tekst = ""
            except Exception as e:
                self._motor_tekst = "Downloaden lukte niet: %s" % e
            self._motor_bezig = False
            QTimer.singleShot(0, lambda: self.motor_knop.setEnabled(True))
        threading.Thread(target=werk, daemon=True).start()

    def _server(self, i):
        url = self.server_keuze.itemData(i)
        if url:
            self.server.setText(url)

    def _zoek(self):
        b = B.Brein(self.server.text().strip())
        ids = b.modellen()
        self.model.clear(); self.model.addItem("(automatisch kiezen)", "")
        for i in ids:
            self.model.addItem(i, i)
        if not ids:
            QMessageBox.information(self, APP, "Geen modellen gevonden op %s.\n\nDraait de server, en is er een "
                                                "model geladen?" % self.server.text())

    def uitkomst(self):
        c = dict(self.cfg)
        model = self.model.currentData()
        if model is None:
            model = self.model.currentText().strip()
            if model.startswith("("):
                model = ""
        c.update(motor_aan=self.motor_aan.isChecked(), motor_map=self._motor.map, motor_exe=self._motor.exe,
                 motor_model=self._motor.model)
        c.update(taal=self.taal.currentData(), naam=self.naam.text().strip(), aanspreek=self.aanspreek.text().strip(),
                 server=self.server.text().strip() or B.SERVERS[0][1], model=model or "",
                 stem_aan=self.stem_aan.isChecked(), stem=self.stem.currentText().strip() or "Leon",
                 snelheid=round(self.snelheid.value(), 2), whisper=self.whisper.currentData(),
                 meteen_versturen=self.meteen.isChecked(), tekst_met_stem=self.sync.isChecked(),
                 online_zoeken=self.online.isChecked(), pc_acties=self.pcacties.isChecked(),
                 ochtend_auto=self.ochtend.isChecked(), gesprekken_bewaren=self.bewaren.isChecked(),
                 programma_mappen=self.progmappen.text().strip(), persoonlijkheid=self.pers.toPlainText().strip())
        return c


# =============================================================================== hoofdvenster
class Javis(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gh = G.Geheugen()
        c = self.gh.cfg
        self.taal = c.get("taal", "nl")
        if not c.get("motor_exe") and not c.get("motor_model"):
            exe, mdl = DM.zoek_bestaande()             # staat er al een DraveMotor/Dave-motor? Dan die gebruiken
            if exe and mdl:
                c.update(motor_exe=exe, motor_model=mdl, motor_map=os.path.dirname(mdl))
                self.gh.bewaar_cfg()
        self.motor = DM.van_cfg(c)
        self.motor_soort = ""
        self.brein = B.Brein(c.get("server"), c.get("model"))
        self.stem = S.Stem(c.get("stem", "Leon"), self.taal, c.get("snelheid", 1.05))
        self.stem.aan = c.get("stem_aan", True)
        self.oren = O.Oren(self.gh.modelmap(), c.get("whisper", "base"), self.taal)
        self.sein = Sein()
        self.sein.stukje.connect(self._stukje)
        self.sein.klaar.connect(self._klaar)
        self.sein.fout.connect(self._fout)
        self.sein.gehoord.connect(self._gehoord)
        self.sein.begin.connect(self._begin)
        self.sein.pc.connect(self._pc_klaar)
        self.sein.zeg.connect(self._klaar_extra)
        self.bevestig = None
        self.laatste_bestanden = []
        P.zet_extra_mappen((c.get("programma_mappen") or "").split(";"))
        threading.Thread(target=P._alle_snelkoppelingen, daemon=True).start()   # programmalijst alvast maken
        self.stem.bij_begin = self.sein.begin.emit
        self.getoond = ""
        self.wacht_op_stem = False
        self.live_index = None
        self.zoekt = False
        self.bronnen = None
        self.zoek_modus = False
        self.mag_zoeken = True
        self.bezig = False
        self.buffer = ""
        self.lopend = ""
        self.berichten = []          # (rol, tekst) voor het scherm
        self.timers = []
        self._ververs_nodig = False

        self.setWindowTitle("%s %s" % (APP, VERSIE))
        self.setWindowIcon(QIcon(hier("assets", "icon.ico")))
        self.setStyleSheet(STIJL)
        self.resize(1320, 840)
        hoofd = QWidget(); self.setCentralWidget(hoofd)
        h = QHBoxLayout(hoofd); h.setContentsMargins(20, 16, 20, 16); h.setSpacing(18)

        links = QVBoxLayout()
        self.titel = QLabel("DRAVEJAVIS"); self.titel.setObjectName("titel")
        self.sub = QLabel(); self.sub.setObjectName("sub")
        links.addWidget(self.titel); links.addWidget(self.sub)
        self.kern = Kern(self._niveau, self._toestand)
        links.addWidget(self.kern, 1)
        self.toestand_lab = QLabel(); self.toestand_lab.setObjectName("toestand")
        self.toestand_lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links.addWidget(self.toestand_lab)
        self.mic = QPushButton(); self.mic.setObjectName("mic")
        self.mic.pressed.connect(self.mic_in); self.mic.released.connect(self.mic_uit)
        links.addWidget(self.mic)
        rij = QHBoxLayout()
        self.b_stop = QPushButton(); self.b_stop.clicked.connect(self.stil); rij.addWidget(self.b_stop)
        self.b_nieuw = QPushButton(); self.b_nieuw.clicked.connect(self.nieuw_gesprek); rij.addWidget(self.b_nieuw)
        self.b_instel = QPushButton(); self.b_instel.setObjectName("goud"); self.b_instel.clicked.connect(self.instellingen)
        rij.addWidget(self.b_instel)
        links.addLayout(rij)
        self.status = QLabel(); self.status.setObjectName("status"); self.status.setWordWrap(True)
        links.addWidget(self.status)
        lw = QWidget(); lw.setLayout(links); lw.setFixedWidth(470)
        h.addWidget(lw)

        rechts = QVBoxLayout()
        self.chat = QTextBrowser(); self.chat.setOpenExternalLinks(True)
        # Meescrollen (29-10-2026): zodra de tekst langer wordt, gaat het venster mee naar beneden.
        # Scroll je zelf omhoog om iets terug te lezen, dan blijft hij staan tot je weer onderaan bent.
        self._meescrollen = True
        self._html_bezig = False
        _sb = self.chat.verticalScrollBar()
        _sb.rangeChanged.connect(lambda _mn, mx: _sb.setValue(mx) if self._meescrollen else None)
        _sb.valueChanged.connect(lambda v: None if self._html_bezig else
                                 setattr(self, "_meescrollen", v >= _sb.maximum() - 40))
        rechts.addWidget(self.chat, 1)
        invoer = QHBoxLayout()
        self.invoer = QLineEdit(); self.invoer.returnPressed.connect(self.verstuur_invoer)
        invoer.addWidget(self.invoer, 1)
        self.b_stuur = QPushButton(); self.b_stuur.clicked.connect(self.verstuur_invoer); invoer.addWidget(self.b_stuur)
        rechts.addLayout(invoer)
        self.jn = QWidget(); jl = QHBoxLayout(self.jn); jl.setContentsMargins(0, 0, 0, 0)
        self.jn_tekst = QLabel(); self.jn_tekst.setStyleSheet("color:#ffb347; font-weight:bold;")
        jl.addWidget(self.jn_tekst, 1)
        bj = QPushButton("✔  Ja"); bj.setObjectName("goud"); bj.clicked.connect(lambda: self.verstuur("ja"))
        bn = QPushButton("✖  Nee"); bn.clicked.connect(lambda: self.verstuur("nee"))
        jl.addWidget(bj); jl.addWidget(bn)
        self.jn.hide()
        rechts.addWidget(self.jn)
        h.addLayout(rechts, 1)

        QShortcut(QKeySequence("Escape"), self, activated=self.stil)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.nieuw_gesprek)
        self.teksten()
        for rol, tekst in [(m["role"], m["content"]) for m in self.gh.gesprek[-20:]]:
            self.berichten.append((rol, tekst))
        if not self.berichten:
            self.berichten.append(("assistant", self.t("welkom")))
        self.ververs_chat()
        self.klok = QTimer(self); self.klok.timeout.connect(self._klok); self.klok.start(120)
        self.stem.warm_op()
        threading.Thread(target=self._zoek_model, daemon=True).start()
        # ochtendoverzicht bij de eerste start van de dag (tussen 5 en 12 uur)
        nu = datetime.datetime.now()
        if c.get("ochtend_auto", True) and 5 <= nu.hour < 12 and c.get("laatste_ochtend") != nu.date().isoformat():
            QTimer.singleShot(3500, self._ochtend)

    # ------------------------------------------------------------ hulp
    def t(self, sl):
        return T.get(self.taal, T["nl"])[sl]

    def teksten(self):
        self.sub.setText(self.t("sub"))
        self.invoer.setPlaceholderText(self.t("typ"))
        self.b_stuur.setText(self.t("stuur"))
        self.mic.setText(self.t("mic"))
        self.b_stop.setText(self.t("stop"))
        self.b_nieuw.setText(self.t("nieuw"))
        self.b_instel.setText(self.t("instel"))

    def _zoek_model(self):
        c = self.gh.cfg
        if c.get("motor_aan", True) and self.motor.klaar():
            self.motor_soort = "motor starten..."
            if self.motor.start():
                self.brein = B.Brein(self.motor.url(), "")
                self.motor_soort = "eigen motor"
            else:
                self.motor_soort = "eigen motor startte niet"
        else:
            self.motor_soort = ""
        gevonden = self.brein.kies_model()
        if self.motor_soort != "eigen motor" and gevonden:
            self.motor_soort = "Llama-app" if ":9931" in self.brein.url else "server"
        self._ververs_nodig = True

    def _toestand(self):
        if self.oren.neemt_op:
            return "luistert"
        if self.zoekt:
            return "zoekt"
        if self.bezig and not self.lopend:
            return "denkt"
        if self.stem.bezig():
            return "spreekt"
        if self.bezig:
            return "denkt"
        return "rust"

    def _niveau(self):
        if self.oren.neemt_op:
            return self.oren.niveau()
        return self.stem.niveau()

    def _klok(self):
        st = self._toestand()
        self.toestand_lab.setText({"rust": self.t("rust"), "denkt": self.t("denkt"), "luistert": self.t("luistert"),
                                   "spreekt": self.t("spreekt"), "zoekt": self.t("zoekt")}[st].upper())
        model = self.brein.naam()
        if self.motor_soort:
            model = "%s · %s" % (model, self.motor_soort)
        titel = "%s %s  ·  %s" % (APP, VERSIE, model)
        if self.windowTitle() != titel:
            self.setWindowTitle(titel)               # modelnaam bovenin (29-10-2026)
        stem = self.t("stem_status").get(self.stem.status, self.stem.status) if self.stem.aan else "stem: uit"
        oor = self.t("oor_status").get(self.oren.status, self.oren.status)
        self.status.setText("🧠 %s   ·   🔊 %s   ·   🎙 %s" % (model, stem, oor))
        if self.wacht_op_stem and not self.stem.bezig():
            self.wacht_op_stem = False
            self._ververs_nodig = True
        if self._ververs_nodig:
            self._ververs_nodig = False
            self.ververs_chat()
        nu = time.time()
        for tm in list(self.timers):
            if nu >= tm[0]:
                self.timers.remove(tm)
                zin = self.t("timer_klaar") % tm[1]
                QApplication.beep()
                self.berichten.append(("assistant", "⏰ " + zin))
                self.ververs_chat()
                self.stem.zeg(zin, label="")

    # ------------------------------------------------------------ chat tonen
    def ververs_chat(self):
        delen = []
        start = max(0, len(self.berichten) - 60)
        for i in range(start, len(self.berichten)):
            rol, tekst = self.berichten[i]
            if i == self.live_index and self.wacht_op_stem:
                tekst = self.getoond.strip() or "…"
            delen.append(self._bel(rol, tekst))
        if self.bezig:
            toon = self.getoond.strip() if self._sync() else self.lopend
            delen.append(self._bel("assistant", toon or "…"))
        sb = self.chat.verticalScrollBar()
        if len(self.berichten) != getattr(self, "_laatst_aantal", -1):
            self._laatst_aantal = len(self.berichten)
            self._meescrollen = True                       # nieuw bericht: altijd naar beneden
        self._html_bezig = True
        self.chat.setHtml("<div>%s</div>" % "".join(delen))
        self._html_bezig = False
        if self._meescrollen:
            sb.setValue(sb.maximum())

    def _sync(self):
        return (self.gh.cfg.get("tekst_met_stem", True) and self.stem.aan
                and self.stem.status in ("uit", "laden", "klaar"))

    def _begin(self, label):
        if self.bezig or self.wacht_op_stem:
            self.getoond += label + " "
            self._ververs_nodig = True

    def _bel(self, rol, tekst):
        if rol == "bestanden":
            links = "".join('<li><a style="color:#7fdcff;" href="%s">%d. %s</a><br><span style="color:#7f93ab; '
                            'font-size:14px;">%s</span></li>' % (html.escape("file:///" + p.replace("\\", "/"), quote=True),
                                                                i + 1, html.escape(os.path.basename(p)),
                                                                html.escape(os.path.dirname(p)))
                            for i, p in enumerate(tekst))
            return '<ul style="font-size:17px;">%s</ul><br>' % links
        if rol == "bronnen":
            links = "".join('<li><a style="color:#7fdcff;" href="%s">%s</a></li>' % (html.escape(r["url"], quote=True),
                                                                                   html.escape(r["titel"][:90]))
                            for r in tekst[:5])
            return ('<p style="color:#7f93ab; font-size:16px; margin-left:20px;"><b>%s:</b></p>'
                    '<ul style="font-size:16px;">%s</ul><br>' % (self.t("bronnen"), links))
        t = html.escape(tekst).replace("\n", "<br>")
        if rol == "user":
            return ('<table width="100%%" cellspacing="0" cellpadding="0"><tr><td width="22%%"></td>'
                    '<td style="background:#123047; padding:12px 16px; border-radius:12px;">'
                    '<span style="color:#7fdcff; font-size:15px;"><b>%s</b></span><br>%s</td></tr></table><br>'
                    % (html.escape(self.gh.cfg.get("naam") or self.t("jij")), t))
        if rol == "fout":
            return ('<p style="color:#ff7a7a; background:#2a0c10; padding:10px;"><b>%s:</b> %s</p>'
                    % (self.t("fout"), t))
        return ('<table width="100%%" cellspacing="0" cellpadding="0"><tr>'
                '<td style="background:#0d1a2b; padding:12px 16px; border-left:4px solid #39d0ff;">'
                '<span style="color:#ffb347; font-size:15px;"><b>DraveJavis</b></span><br>%s</td>'
                '<td width="12%%"></td></tr></table><br>' % t)

    # ------------------------------------------------------------ praten
    def verstuur_invoer(self):
        tekst = self.invoer.text().strip()
        if tekst:
            self.invoer.clear()
            self.verstuur(tekst)

    def verstuur(self, tekst):
        if self.bezig:
            return
        self.stem.stil()
        self.berichten.append(("user", tekst))
        if self.bevestig:
            self._beantwoord_bevestiging(tekst)
            return
        m = re.match(r"^(open|start) (nummer |bestand |het |de )?(\d+|eerste|tweede|derde|vierde|vijfde|laatste)( bestand| file)?$",
                     tekst.lower().strip().rstrip(".!"))
        if m and self.laatste_bestanden:
            w = m.group(3)
            i = {"eerste": 1, "tweede": 2, "derde": 3, "vierde": 4, "vijfde": 5}.get(w)
            i = len(self.laatste_bestanden) if w == "laatste" else (i or int(w))
            if 1 <= i <= len(self.laatste_bestanden):
                ok, zin = P.open_bestand(self.laatste_bestanden[i - 1])
                self._zeg_kort(zin)
                return
        uit = V.doe(tekst, self.gh, self.taal)
        if not uit and self.gh.cfg.get("pc_acties", True):
            gevonden = P.herken(tekst)
            if gevonden:
                self.gh.voeg_toe("user", tekst)
                self._pc_actie(*gevonden)
                return
        if uit and uit[1] and uit[1][0] == "zoek":
            self.gh.voeg_toe("user", tekst)
            self._start_zoek(uit[1][1])
            return
        if uit and uit[1] and uit[1][0] == "ochtend":
            self.gh.voeg_toe("user", tekst)
            self._ochtend()
            return
        if uit and uit[1] and uit[1][0] == "plaats":
            self.gh.voeg_toe("user", tekst)
            self._zet_plaats(uit[1][1])
            return
        if uit:
            antwoord, actie = uit
            self.gh.voeg_toe("user", tekst)
            self.gh.voeg_toe("assistant", antwoord)
            self.berichten.append(("assistant", antwoord))
            self.ververs_chat()
            self.stem.zeg(antwoord, label="")
            if actie and actie[0] == "timer":
                self.timers.append((time.time() + actie[1], actie[2]))
            elif actie and actie[0] == "open":
                webbrowser.open(actie[1])
            elif actie and actie[0] == "map":
                try:
                    os.startfile(actie[1])
                except Exception:
                    pass
            return
        self.gh.voeg_toe("user", tekst)
        self.bezig = True
        self.buffer = ""
        self.lopend = ""
        self.getoond = ""
        self.wacht_op_stem = False
        self.live_index = None
        self.zoek_modus = False
        self.mag_zoeken = self.gh.cfg.get("online_zoeken", True) or self.gh.cfg.get("pc_acties", True)
        self.ververs_chat()
        berichten = self.gh.berichten()
        meten = self.gh.cfg.get("pc_acties", True) and any(P.over_pc(m["content"]) for m in self.gh.gesprek[-3:]
                                                           if m["role"] == "user")
        threading.Thread(target=self._denk, args=(berichten, meten), daemon=True).start()

    # ------------------------------------------------------------ ochtendoverzicht en plaats
    def _ochtend(self):
        """Weer + agenda + notities, in een eigen draad (het weer komt van internet)."""
        if self.bezig:
            return
        self.bezig = True
        self.ververs_chat()

        def werk():
            try:
                tekst = OC.overzicht(self.gh, self.taal)
            except Exception as e:
                tekst = "Het ochtendoverzicht lukte niet: %s" % e
            self.sein.zeg.emit("OCHTEND|" + tekst)
        threading.Thread(target=werk, daemon=True).start()

    def _zet_plaats(self, naam):
        self.bezig = True
        self.ververs_chat()

        def werk():
            try:
                import weer_engine as W
                r = W.zoek_plaats(naam, aantal=1)
            except Exception:
                r = []
            if not r:
                self.sein.zeg.emit("ZEG|" + ("Die plaats kon ik niet vinden: %s." % naam if self.taal == "nl"
                                             else "I couldn't find that place: %s." % naam))
                return
            p = r[0]
            self.gh.cfg["plaats"] = dict(naam=p["naam"], regio=p.get("regio", ""), land=p.get("land", ""),
                                         lat=p["lat"], lon=p["lon"])
            self.gh.bewaar_cfg()
            waar = p["naam"] + (", " + p["regio"] if p.get("regio") else "")
            self.sein.zeg.emit("ZEG|" + ("Goed, voor het weer gebruik ik voortaan %s." % waar if self.taal == "nl"
                                         else "Got it, I'll use %s for the weather." % waar))
        threading.Thread(target=werk, daemon=True).start()

    def _klaar_extra(self, bericht):
        soort, _, tekst = bericht.partition("|")
        self.bezig = False
        if soort == "OCHTEND":
            self.gh.cfg["laatste_ochtend"] = datetime.date.today().isoformat()
            self.gh.bewaar_cfg()
        self._zeg_kort(tekst)

    # ------------------------------------------------------------ pc-acties
    def _zeg_kort(self, zin, opslaan=True):
        self.berichten.append(("assistant", zin))
        if opslaan:
            self.gh.voeg_toe("assistant", zin)
        self.ververs_chat()
        self.stem.zeg(zin, label="")

    def _pc_actie(self, actie, arg="", bevestigd=False, data=None):
        if actie not in P.ACTIES:
            self._zeg_kort("Die actie ken ik niet.")
            return
        if actie == "schermafbeelding":
            self._schermafbeelding()
            return
        self.bezig = True
        self.ververs_chat()
        threading.Thread(target=self._pc_werk, args=(actie, arg, bevestigd, data), daemon=True).start()

    def _pc_werk(self, actie, arg, bevestigd, data):
        try:
            uit = self._pc_uitvoeren(actie, (arg or "").strip(), bevestigd, data)
        except Exception as e:
            uit = dict(tekst="Dat lukte niet: %s" % e)
        self.sein.pc.emit(uit)

    def _pc_uitvoeren(self, actie, arg, bevestigd, data):
        if actie == "open_programma":
            return dict(tekst=P.open_programma(arg)[1])
        if actie == "open_map":
            return dict(tekst=P.open_map(arg or "documenten")[1])
        if actie == "geluid":
            return dict(tekst=P.geluid(arg if arg in P.VK else "pauze")[1])
        if actie == "gezondheid":
            return dict(tekst=P.gezondheid()[1])
        if actie == "vergrendel":
            return dict(tekst=P.vergrendel()[1])
        if actie == "annuleer_afsluiten":
            return dict(tekst=P.annuleer_afsluiten()[1])
        if actie == "zoek_bestand":
            res = P.zoek_bestanden(arg)
            if not res:
                return dict(tekst="Ik vond geen bestanden met '%s' in de naam (in je bureaublad, documenten, "
                                  "downloads, afbeeldingen, muziek en video's)." % arg)
            return dict(tekst="Ik vond %d bestand%s. Zeg bijvoorbeeld 'open nummer 1'." % (
                len(res), "" if len(res) == 1 else "en"), bestanden=res)
        if actie == "sluit_programma":
            if not bevestigd:
                treffers = P.zoek_proces(arg)
                if not treffers:
                    return dict(tekst="Ik zie geen programma '%s' draaien." % arg)
                naam = treffers[0][0]
                return dict(tekst="Zal ik %s afsluiten? Werk dat niet is opgeslagen kan verloren gaan." % naam[:-4],
                            bevestig=(actie, arg, naam))
            return dict(tekst=P.sluit_programma(data)[1])
        if actie in ("afsluiten", "herstarten"):
            if not bevestigd:
                return dict(tekst="Weet je zeker dat ik de pc moet %s?" % ("herstarten" if actie == "herstarten"
                                                                         else "afsluiten"),
                            bevestig=(actie, arg, None))
            return dict(tekst=P.afsluiten(herstart=actie == "herstarten")[1])
        if actie == "opruimen":
            if not bevestigd:
                plekken, grootte = P.opruim_plan()
                return dict(tekst="In de tijdelijke mappen staat ongeveer %.0f MB. Ik ruim alles op wat ouder is dan "
                                  "een dag, en leeg de prullenbak. Zal ik dat doen?" % (grootte / 2 ** 20),
                            bevestig=(actie, arg, plekken))
            return dict(tekst=P.opruimen(data)[1])
        return dict(tekst="Die actie ken ik niet.")

    def _pc_klaar(self, uit):
        self.bezig = False
        if uit.get("bevestig"):
            self.bevestig = uit["bevestig"]
            self.jn_tekst.setText("Zeg of typ ja of nee")
            self.jn.show()
        self._zeg_kort(uit.get("tekst", ""))
        if uit.get("bestanden"):
            self.laatste_bestanden = uit["bestanden"]
            self.berichten.append(("bestanden", uit["bestanden"]))
            self.ververs_chat()

    def _beantwoord_bevestiging(self, tekst):
        actie, arg, data = self.bevestig
        self.bevestig = None
        self.jn.hide()
        t = tekst.lower().strip().rstrip("!. ")
        if re.match(r"^(ja|jawel|jazeker|ja graag|doe maar|doe het|oké|ok|okay|prima|graag|yes|sure|go ahead)\b", t):
            self._pc_actie(actie, arg, bevestigd=True, data=data)
        else:
            self._zeg_kort("Goed, dan doe ik het niet.")

    def _schermafbeelding(self):
        scherm = QApplication.primaryScreen()
        geo = scherm.virtualGeometry()
        beeld = scherm.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
        map_ = os.path.join(P._map("afbeeldingen"), "DraveJavis")
        os.makedirs(map_, exist_ok=True)
        pad = os.path.join(map_, datetime.datetime.now().strftime("schermafbeelding_%Y-%m-%d_%H-%M-%S.png"))
        if beeld.save(pad):
            self.laatste_bestanden = [pad]
            self._zeg_kort("Schermafbeelding gemaakt. Hij staat in je afbeeldingen, map DraveJavis.")
            self.berichten.append(("bestanden", [pad]))
            self.ververs_chat()
        else:
            self._zeg_kort("De schermafbeelding lukte niet.")

    def _start_zoek(self, term):
        self.stem.stil()
        self.bezig = True
        self.zoekt = True
        self.mag_zoeken = False
        self.zoek_modus = False
        self.buffer = self.lopend = self.getoond = ""
        self.wacht_op_stem = False
        self.live_index = None
        self.ververs_chat()
        threading.Thread(target=self._zoek_denk, args=(term,), daemon=True).start()

    def _zoek_denk(self, term):
        try:
            res = Z.zoek(term, taal=self.taal)
        except Exception:
            res = []
        self.zoekt = False
        if not res:
            self.sein.klaar.emit(self.t("niets_gevonden"))
            return
        self.bronnen = res
        berichten = self.gh.berichten() + [dict(role="user", content=Z.als_context(term, res, self.taal))]
        self._denk(berichten)

    def _denk(self, berichten, meten=False):
        if meten:
            try:
                ok, meting = P.gezondheid()
                if ok:
                    berichten[0]["content"] += (
                        "\n\nECHTE METING van deze pc, zojuist gedaan (gebruik ALLEEN deze cijfers, verzin niets): "
                        + meting + "\nGeheugen tot ongeveer 85 procent is normaal en betekent NIET dat het 'vol' is. "
                        "Wat jij zelf kunt doen: een programma sluiten (vraag welk), tijdelijke bestanden opruimen, "
                        "laten zien wat het meeste geheugen gebruikt. Noem geen Windows-menu's of programma's die je "
                        "niet zeker kent.")
            except Exception:
                pass
        try:
            antwoord = self.brein.praat(berichten, bij_stukje=self.sein.stukje.emit)
            self.sein.klaar.emit(antwoord)
        except B.BreinFout as e:
            self.sein.fout.emit(str(e))
        except Exception as e:
            self.sein.fout.emit(str(e))

    def _stukje(self, s):
        self.lopend += s
        if self.mag_zoeken:
            begin = self.lopend.lstrip().upper()
            if len(begin) < 6 and ("ZOEK:".startswith(begin) or "ACTIE:".startswith(begin)):
                return                      # nog even afwachten: wordt het een zoekopdracht of actie?
            if begin.startswith(("ZOEK:", "ZOEK :", "ACTIE:", "ACTIE :")):
                self.zoek_modus = True
                return
            self.mag_zoeken = False
            s = self.lopend                 # wat we vasthielden alsnog verwerken
        if self.zoek_modus:
            return
        self.buffer += s
        zinnen, self.buffer = B.zinnen(self.buffer)
        for z in zinnen:
            self.stem.zeg(z)
        self._ververs_nodig = True

    def _klaar(self, antwoord):
        if self.zoek_modus:
            regel = (antwoord or self.lopend).strip().splitlines()[0]
            term = regel.split(":", 1)[1].strip().strip('"') if ":" in regel else regel
            if regel.upper().startswith("ACTIE"):
                self.bezig = False
                self.lopend = ""
                naam, _, arg = term.partition("|")
                naam = naam.strip().lower()
                if self.gh.cfg.get("pc_acties", True) and naam in P.ACTIES:
                    self._pc_actie(naam, arg.strip())
                else:
                    self._zeg_kort("Dat kan ik op de pc niet voor je doen.")
                return
            if not self.gh.cfg.get("online_zoeken", True):
                self.bezig = False
                self.lopend = ""
                self._zeg_kort("Online zoeken staat uit bij de instellingen.")
                return
            self._start_zoek(term or self.gh.gesprek[-1]["content"])
            return
        if self.mag_zoeken and self.lopend and not self.buffer:
            self.buffer = self.lopend       # kort antwoord dat we nog vasthielden
        self.mag_zoeken = False
        if self.buffer.strip():
            self.stem.zeg(self.buffer)
        self.buffer = ""
        antwoord = antwoord or self.lopend.strip()
        self.bezig = False
        self.lopend = ""
        if antwoord:
            self.berichten.append(("assistant", antwoord))
            self.gh.voeg_toe("assistant", antwoord)
            if self._sync() and self.stem.bezig():
                self.live_index = len(self.berichten) - 1
                self.wacht_op_stem = True
        if self.bronnen:
            self.berichten.append(("bronnen", self.bronnen))
            self.bronnen = None
        self.ververs_chat()

    def _fout(self, tekst):
        self.bezig = False
        self.zoekt = False
        self.bronnen = None
        self.lopend = ""
        self.berichten.append(("fout", tekst))
        if self.gh.gesprek and self.gh.gesprek[-1]["role"] == "user":
            self.gh.gesprek.pop()
        self.ververs_chat()

    def stil(self):
        self.stem.stil()
        self.brein.stop()
        if self.wacht_op_stem:
            self.wacht_op_stem = False
            self._ververs_nodig = True

    def nieuw_gesprek(self):
        self.stil()
        self.gh.wis_gesprek()
        self.berichten = [("assistant", self.t("welkom"))]
        self.ververs_chat()

    # ------------------------------------------------------------ microfoon
    def mic_in(self):
        self.stem.stil()
        if self.oren._model is None:
            self.oren.warm_op()
        if self.oren.start():
            self.mic.setText(self.t("mic_aan"))
            self.mic.setProperty("aan", True)
            self.mic.style().unpolish(self.mic); self.mic.style().polish(self.mic)

    def mic_uit(self):
        if not self.oren.neemt_op:
            return
        audio = self.oren.stop()
        self.mic.setText(self.t("omzetten"))
        self.mic.setProperty("aan", False)
        self.mic.style().unpolish(self.mic); self.mic.style().polish(self.mic)
        threading.Thread(target=self._luister, args=(audio,), daemon=True).start()

    def _luister(self, audio):
        tekst = self.oren.naar_tekst(audio)
        self.sein.gehoord.emit(tekst)

    def _gehoord(self, tekst):
        self.mic.setText(self.t("mic"))
        if not tekst:
            self.berichten.append(("assistant", self.t("geen_tekst")))
            self.ververs_chat()
            return
        if self.gh.cfg.get("meteen_versturen", True):
            self.verstuur(tekst)
        else:
            self.invoer.setText(tekst)
            self.invoer.setFocus()

    def eventFilter(self, obj, e):
        """F2 overal in het venster: ingedrukt houden = praten."""
        from PyQt6.QtCore import QEvent
        if e.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and e.key() == Qt.Key.Key_F2:
            if not e.isAutoRepeat():
                if e.type() == QEvent.Type.KeyPress:
                    self.mic_in()
                else:
                    self.mic_uit()
            return True
        return super().eventFilter(obj, e)

    # ------------------------------------------------------------ instellingen
    def instellingen(self):
        d = Instellingen(self, self.gh.cfg, self.stem.stemmen)
        if not d.exec():
            return
        c = d.uitkomst()
        self.gh.cfg = c
        self.gh.bewaar_cfg()
        self.taal = c["taal"]
        nieuwe = DM.van_cfg(c)
        if (nieuwe.exe, nieuwe.model) != (self.motor.exe, self.motor.model):
            self.motor.stop()
            self.motor = nieuwe
        self.brein = B.Brein(c["server"], c["model"])
        threading.Thread(target=self._zoek_model, daemon=True).start()
        self.stem.aan = c["stem_aan"]
        self.stem.taal = self.taal
        self.stem.snelheid = c["snelheid"]
        self.stem.kies_stem(c["stem"])
        self.oren.taal = self.taal
        self.oren.grootte = c["whisper"]
        P.zet_extra_mappen((c.get("programma_mappen") or "").split(";"))
        threading.Thread(target=P._alle_snelkoppelingen, daemon=True).start()
        self.teksten()
        self.ververs_chat()

    def closeEvent(self, e):
        self.stil()
        try:
            self.motor.stop()                   # alleen als Javis hem zelf startte
        except Exception:
            pass
        e.accept()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dravenlock.DraveJavis")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setWindowIcon(QIcon(hier("assets", "icon.ico")))
    f = QFont("Segoe UI", 12)
    app.setFont(f)
    w = Javis()
    app.installEventFilter(w)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
