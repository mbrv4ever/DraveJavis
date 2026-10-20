# DraveJavis

**Een persoonlijke spraakassistent die helemaal op je eigen pc draait.**
*A personal voice assistant that runs entirely on your own computer.* (English below)

![DraveJavis](assets/icon.png)

Geen cloud, geen account, geen abonnement. Je praat met DraveJavis via je microfoon of je typt, en hij antwoordt hardop.
Alles (taalmodel, stem en spraakherkenning) draait lokaal.

## Wat kan hij?
- **Praten en luisteren**: houd de microfoonknop (of **F2**) ingedrukt, praat, en laat los. Hij antwoordt met een neurale stem, zin voor zin, terwijl het antwoord nog binnenkomt.
- **Een lokaal taalmodel als brein**: werkt met elke OpenAI-compatibele server op je pc:
  [Llama-app (llama.cpp)](https://github.com/ggml-org/llama.cpp), LM Studio, Ollama, Jan of llama.cpp-server.
  Kiest zelf een geladen model (of stel er een vast in).
- **Zelf direct**: de tijd en de datum, een **timer** ("zet een timer van 5 minuten"), dingen **onthouden**
  ("onthoud dat ...", "wat heb je onthouden?", "vergeet ...") en een **website openen** ("open youtube").
- **Zelf online zoeken**: vraag naar het weer, nieuws of openingstijden, of zeg "zoek op internet naar ...".
  DraveJavis zoekt zelf (DuckDuckGo), leest de beste pagina's, vertelt het antwoord en zet de **bronnen als links**
  eronder. Je browser gaat niet open. Alleen de zoekvraag gaat het internet op (uit te zetten bij Instellingen).
- **Nederlands en Engels.** Eigen naam, aanspreekvorm en persoonlijkheid in te stellen.
- Grote, duidelijke letters en een donker scherm met een bewegende kern die laat zien wat hij doet
  (klaar, luistert, denkt na, spreekt).

## Installeren (Windows)
1. Installeer **Python 3.10 – 3.13** van [python.org](https://www.python.org/downloads/).
2. Installeer een lokale taalmodel-server, bijvoorbeeld de **Llama-app**, **LM Studio** of **Ollama**, en laad een model.
   Voor Nederlands werkt *Fietje 2* goed; voor Engels bijvoorbeeld *Gemma 3* of *Qwen 2.5*.
3. Dubbelklik **`Installeer-DraveJavis.bat`** (eenmalig; dit maakt een `.venv` en installeert de onderdelen).
4. Start met **`Start-DraveJavis.bat`**. Bij **Instellingen** kies je je server, model, stem en taal.

De eerste keer worden het stemmodel (neuvoice) en het spraakherkenningsmodel (Whisper) automatisch gedownload.
Daarna werkt alles offline.

**Zelf een EXE maken:** na stap 3 `Bouw-DraveJavis-EXE.bat` → `dist\DraveJavis\DraveJavis.exe`.

## Waar staan mijn gegevens?
In `%APPDATA%\DraveJavis` (Windows) of `~/.drave_javis`: instellingen, het lopende gesprek, wat hij moet onthouden
en de spraakherkenningsmodellen. Niets verlaat je pc, behalve een zoekvraag als hij online zoekt (uit te zetten).

## Onderdelen en dank
| Onderdeel | Waarvoor | Licentie |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | het venster | GPL v3 |
| [neuvoice](https://github.com/thelamapi/neuvoice) | de stem (tekst naar spraak) | OpenRAIL |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) / OpenAI Whisper | spraakherkenning | MIT |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | microfoon en luidspreker | MIT |
| [ONNX Runtime](https://onnxruntime.ai/) | rekent de stem uit | MIT |

DraveJavis is een eigen project, niet verbonden aan Marvel of Iron Man.

## Licentie
DraveJavis is vrije software onder de **GNU General Public License v3.0** (zie [LICENSE](LICENSE)).
Je mag hem gratis gebruiken, delen en aanpassen. Deel je een aangepaste versie, dan moet die ook onder de GPL-3.0
en met de broncode beschikbaar zijn. Copyright © 2026 Dravenlock (Roger & Claudio).

📖 Uitleg met alle commando's: **[DraveJavis-Snelgids.pdf](DraveJavis-Snelgids.pdf)**

---

## English

**DraveJavis** is a local, private voice assistant for Windows. Hold the microphone button (or **F2**) and talk,
or just type. It answers out loud with a neural voice (neuvoice), understands speech with faster-whisper, and thinks
with any local OpenAI-compatible model server (Llama app / llama.cpp, LM Studio, Ollama, Jan).
Built-in skills: time, date, timers, remembering facts, opening websites, and its own web search (DuckDuckGo) with source links. Dutch and English.

**Install:** Python 3.10–3.13 → run `Installeer-DraveJavis.bat` → start a local model server → run
`Start-DraveJavis.bat`. Models for voice and speech recognition are downloaded once on first use.

Made by **Dravenlock** (Roger & Claudio). Licensed under **GPL-3.0**. Donations welcome, never required.
