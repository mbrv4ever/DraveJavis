# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""brein.py - DraveJavis praat met een lokaal taalmodel via een OpenAI-compatibele server.

Werkt met de Llama-app (llama.cpp, standaard http://127.0.0.1:9931/v1), LM Studio, Ollama,
llama.cpp-server, Jan, ... Alles lokaal. Alleen de standaardbibliotheek.
Antwoorden komen binnen als stroom (streaming), zodat de stem al kan beginnen.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

SERVERS = [
    ("Llama-app (llama.cpp)", "http://127.0.0.1:9931/v1"),
    ("LM Studio", "http://127.0.0.1:1234/v1"),
    ("Ollama", "http://127.0.0.1:11434/v1"),
    ("llama.cpp server", "http://127.0.0.1:8080/v1"),
    ("Jan", "http://127.0.0.1:1337/v1"),
]

VOORKEUR = ["fietje", "olmo", "gemma", "qwen", "llama", "mistral", "phi"]


class BreinFout(Exception):
    pass


class Brein:
    def __init__(self, url="http://127.0.0.1:9931/v1", model="", timeout=240):
        self.url = (url or SERVERS[0][1]).rstrip("/")
        self.vast_model = (model or "").strip()
        self.timeout = timeout
        self.model = None
        self.laatste_fout = ""
        self._stop = False

    # ------------------------------------------------------------ server
    def modellen(self, timeout=4):
        try:
            with urllib.request.urlopen(self.url + "/models", timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            self.laatste_fout = str(e)
            return []
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    def kies_model(self):
        ids = self.modellen()
        if not ids:
            self.model = None
            return None
        if self.vast_model:
            for i in ids:
                if i.lower() == self.vast_model.lower():
                    self.model = i
                    return i
        for v in VOORKEUR:
            for i in ids:
                if v in i.lower():
                    self.model = i
                    return i
        self.model = ids[0]
        return self.model

    def naam(self):
        return self.model.split("/")[-1] if self.model else "geen model"

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------ praten
    def praat(self, berichten, bij_stukje=None, temperatuur=0.7, max_tokens=700):
        """Stuurt het gesprek en geeft het hele antwoord terug.
        bij_stukje(tekst) wordt aangeroepen voor elk binnenkomend stukje (streaming)."""
        self._stop = False
        if not self.model and not self.kies_model():
            raise BreinFout("Geen taalmodel bereikbaar op %s.\n\nStart de Llama-app (of je eigen server) "
                            "en laad een model." % self.url)
        body = {"model": self.model, "messages": berichten, "stream": True,
                "temperature": temperatuur, "max_tokens": max_tokens}
        req = urllib.request.Request(self.url + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              "Accept": "text/event-stream"})
        antwoord = []
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                soort = r.headers.get("Content-Type", "")
                if "event-stream" not in soort:
                    # server negeert streaming: gewoon in één keer
                    out = json.loads(r.read().decode("utf-8"))
                    t = (out["choices"][0]["message"].get("content") or "").strip()
                    if bij_stukje and t:
                        bij_stukje(t)
                    return t
                for ruw in r:
                    if self._stop:
                        break
                    regel = ruw.decode("utf-8", "replace").strip()
                    if not regel.startswith("data:"):
                        continue
                    data = regel[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        stuk = json.loads(data)["choices"][0].get("delta", {}).get("content") or ""
                    except Exception:
                        continue
                    if stuk:
                        antwoord.append(stuk)
                        if bij_stukje:
                            bij_stukje(stuk)
        except urllib.error.HTTPError as e:
            self.model = None
            try:
                uitleg = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                uitleg = ""
            raise BreinFout("De server gaf een fout (%s). %s" % (e.code, uitleg))
        except Exception as e:
            self.model = None
            raise BreinFout("Kon niet met het taalmodel praten: %s" % e)
        return "".join(antwoord).strip()


def zinnen(buffer):
    """Knipt volledige zinnen af (voor de stem). Geeft (zinnen, rest) terug."""
    uit = []
    start = 0
    i = 0
    while i < len(buffer):
        c = buffer[i]
        if c in ".!?\n" and (i + 1 >= len(buffer) or buffer[i + 1] in " \n\"')"):
            stuk = buffer[start:i + 1].strip()
            # niet afknippen na een getal ("1.") of afkorting van één letter ("d.w.z.")
            vorige = buffer[max(start, i - 2):i]
            if c == "." and (vorige[-1:].isdigit() or (len(vorige) >= 2 and vorige[-2] in " ." and vorige[-1].isalpha())):
                i += 1
                continue
            if len(stuk) > 1:
                uit.append(stuk)
            start = i + 1
        i += 1
    return uit, buffer[start:]
