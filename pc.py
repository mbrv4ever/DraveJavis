# -*- coding: utf-8 -*-
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
"""pc.py - DraveJavis bedient je pc, maar alleen met een vaste lijst VEILIGE acties.

Het taalmodel mag nooit zelf opdrachten typen. Het kiest hooguit welke actie je bedoelt
(ACTIE: naam | argument); deze module voert die uit op een gecontroleerde manier.
Riskante acties (afsluiten, herstarten, programma sluiten, opruimen) vragen eerst om bevestiging.
Windows. Op andere systemen werken alleen de veilige basisdingen.
"""
from __future__ import annotations

import difflib
import glob
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

WIN = sys.platform == "win32"
THUIS = os.path.expanduser("~")


FOLDERID = {
    "bureaublad": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "documenten": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "afbeeldingen": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "muziek": "{4BD8D571-6D19-48D3-BE97-422220080E43}", "video": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
}
_map_cache = {}


def _bekende_map(guid):
    """Vraag Windows waar een map echt staat (ook als die verplaatst is, of in OneDrive staat)."""
    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

    u = uuid.UUID(guid)
    g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    pad = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(pad)) != 0:
        return None
    uit = pad.value
    ctypes.windll.ole32.CoTaskMemFree(pad)
    return uit


def _map(naam):
    if naam in _map_cache:
        return _map_cache[naam]
    pad = None
    if WIN:
        try:
            pad = _bekende_map(FOLDERID[naam])
        except Exception:
            pad = None
    if not pad or not os.path.isdir(pad):
        eng = {"bureaublad": "Desktop", "documenten": "Documents", "downloads": "Downloads",
               "afbeeldingen": "Pictures", "muziek": "Music", "video": "Videos"}[naam]
        pad = os.path.join(THUIS, eng)
    _map_cache[naam] = pad
    return pad


MAPPEN = {
    "bureaublad": "bureaublad", "desktop": "bureaublad", "documenten": "documenten", "documents": "documenten",
    "mijn documenten": "documenten", "downloads": "downloads", "download": "downloads",
    "afbeeldingen": "afbeeldingen", "foto's": "afbeeldingen", "fotos": "afbeeldingen", "pictures": "afbeeldingen",
    "muziek": "muziek", "music": "muziek", "video's": "video", "videos": "video", "films": "video",
}

INGEBOUWD = {
    "kladblok": "notepad", "notepad": "notepad", "rekenmachine": "calc", "calculator": "calc",
    "verkenner": "explorer", "explorer": "explorer", "verkenner van windows": "explorer", "paint": "mspaint",
    "taakbeheer": "taskmgr", "task manager": "taskmgr", "instellingen": "ms-settings:", "settings": "ms-settings:",
    "configuratiescherm": "control", "control panel": "control", "knipprogramma": "snippingtool",
    "snipping tool": "snippingtool", "wordpad": "write", "kaarten": "bingmaps:", "camera": "microsoft.windows.camera:",
    "edge": "msedge", "microsoft edge": "msedge", "chrome": "chrome", "google chrome": "chrome", "firefox": "firefox",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "outlook": "outlook",
}

# Processen die DraveJavis nooit mag sluiten
BESCHERMD = {"explorer.exe", "csrss.exe", "winlogon.exe", "lsass.exe", "services.exe", "svchost.exe",
             "system", "smss.exe", "wininit.exe", "dwm.exe", "dravejavis.exe", "python.exe", "pythonw.exe",
             "taskmgr.exe", "sihost.exe", "fontdrvhost.exe", "ctfmon.exe", "searchhost.exe", "startmenuexperiencehost.exe"}


# ============================================================================ programma's
_snelkoppelingen = None
EXTRA_MAPPEN = []       # eigen mappen met programma's (instelling), daarin worden .exe-bestanden gezocht


def zet_extra_mappen(mappen):
    global EXTRA_MAPPEN, _snelkoppelingen
    EXTRA_MAPPEN = [m.strip() for m in mappen if m.strip()]
    _snelkoppelingen = None


def _alle_snelkoppelingen():
    global _snelkoppelingen
    if _snelkoppelingen is not None:
        return _snelkoppelingen
    plekken = []
    if WIN:
        plekken += [os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                    _map("bureaublad"), os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")]
    gevonden = {}
    for p in plekken:
        for f in glob.glob(os.path.join(p, "**", "*.lnk"), recursive=True) + glob.glob(os.path.join(p, "*.url")):
            naam = os.path.splitext(os.path.basename(f))[0]
            laag = naam.lower()
            if any(w in laag for w in ("uninstall", "verwijder", "readme", "help", "documentation", "website")):
                continue
            gevonden.setdefault(laag, f)
    for wortel in EXTRA_MAPPEN:
        if not os.path.isdir(wortel):
            continue
        for map_, submappen, bestanden in os.walk(wortel):
            submappen[:] = [d for d in submappen if d.lower() not in ("_internal", "build", "__pycache__", ".venv",
                                                                     "venv", "node_modules", ".git")
                            and not d.startswith(("_", "."))]
            if map_.count(os.sep) - wortel.count(os.sep) >= 4:
                submappen[:] = []
            for b in bestanden:
                if b.lower().endswith(".exe") and not b.lower().startswith(("unins", "setup", "install")):
                    gevonden.setdefault(os.path.splitext(b)[0].lower(), os.path.join(map_, b))
    _snelkoppelingen = gevonden
    return gevonden


def zoek_programma(naam):
    naam = naam.lower().strip().rstrip(".")
    if naam in INGEBOUWD:
        return naam, INGEBOUWD[naam]
    lijst = _alle_snelkoppelingen()
    if naam in lijst:
        return naam, lijst[naam]
    zonder = naam.replace(" ", "")
    for k in lijst:
        if k.replace(" ", "") == zonder:
            return k, lijst[k]
    bevat = [k for k in lijst if naam in k or zonder in k.replace(" ", "")]
    if bevat:
        k = min(bevat, key=len)
        return k, lijst[k]
    return None, None


def lijkt_op(naam):
    """Programmanamen die erop lijken (voor 'bedoel je...?')."""
    naam = naam.lower().strip()
    return difflib.get_close_matches(naam, list(_alle_snelkoppelingen()) + list(INGEBOUWD), n=3, cutoff=0.55)


def open_programma(naam):
    gevonden, doel = zoek_programma(naam)
    if not doel:
        bijna = lijkt_op(naam)
        if bijna:
            return False, "Ik kan '%s' niet vinden. Bedoel je misschien: %s?" % (naam, ", ".join(b.title() for b in bijna))
        return False, "Ik kan geen programma vinden dat '%s' heet." % naam
    try:
        if WIN:
            os.startfile(doel)
        else:
            subprocess.Popen([doel])
        return True, "Ik start %s." % gevonden.title() if gevonden else "Ik start het programma."
    except Exception as e:
        return False, "Starten lukte niet: %s" % e


def open_map(naam):
    sl = MAPPEN.get(naam.lower().strip())
    if naam.lower().strip() in ("temp", "tijdelijke bestanden", "%temp%"):
        pad = os.environ.get("TEMP", THUIS)
    elif sl:
        pad = _map(sl)
    elif os.path.isdir(naam):
        pad = naam
    else:
        return False, "Die map ken ik niet. Ik ken: bureaublad, documenten, downloads, afbeeldingen, muziek en video's."
    try:
        os.startfile(pad) if WIN else subprocess.Popen(["xdg-open", pad])
        return True, "Ik open je map %s." % naam
    except Exception as e:
        return False, "Openen lukte niet: %s" % e


def zoek_proces(naam):
    """Draaiende programma's die op de naam lijken (alleen gewone programma's, nooit systeemprocessen)."""
    if psutil is None:
        return []
    naam = naam.lower().strip()
    uit = {}
    for p in psutil.process_iter(["name", "username"]):
        try:
            pn = (p.info["name"] or "").lower()
            if pn in BESCHERMD or not pn.endswith(".exe") and WIN:
                continue
            kort = pn[:-4] if pn.endswith(".exe") else pn
            if naam in kort or difflib.SequenceMatcher(None, naam, kort).ratio() > 0.75:
                uit.setdefault(pn, []).append(p)
        except Exception:
            continue
    return list(uit.items())


def sluit_programma(procesnaam):
    if psutil is None:
        return False, "Daarvoor mis ik het onderdeel psutil."
    n = 0
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() == procesnaam and procesnaam not in BESCHERMD:
                p.terminate()
                n += 1
        except Exception:
            continue
    return (n > 0), ("Ik heb %s gesloten." % procesnaam[:-4] if n else "Het programma draaide al niet meer.")


# ============================================================================ geluid en media
VK = dict(stil=0xAD, zachter=0xAE, harder=0xAF, volgende=0xB0, vorige=0xB1, stop=0xB2, pauze=0xB3)


def toets(soort, keer=1):
    if not WIN:
        return False
    try:
        import ctypes
        for _ in range(keer):
            ctypes.windll.user32.keybd_event(VK[soort], 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK[soort], 0, 2, 0)
            time.sleep(0.02)
        return True
    except Exception:
        return False


def geluid(soort):
    zinnen = {"harder": "Harder.", "zachter": "Zachter.", "stil": "Het geluid staat aan of uit.",
              "pauze": "Afspelen of pauzeren.", "volgende": "Volgende nummer.", "vorige": "Vorige nummer.",
              "stop": "Gestopt."}
    keer = 5 if soort in ("harder", "zachter") else 1      # 5 stapjes = ongeveer 10 procent
    return toets(soort, keer), zinnen.get(soort, "Gedaan.")


# ============================================================================ pc-gezondheid
def gezondheid():
    if psutil is None:
        return False, "Daarvoor mis ik het onderdeel psutil."
    cpu = psutil.cpu_percent(interval=0.6)
    vm = psutil.virtual_memory()
    zinnen = ["De processor werkt op %d procent." % round(cpu),
              ("Het geheugen is voor %d procent in gebruik: %.1f van de %.0f gigabyte." % (
                  round(vm.percent), vm.used / 2 ** 30, vm.total / 2 ** 30)).replace(".", ",", 1).replace(",", ".", 0)]
    for d in psutil.disk_partitions(all=False):
        if WIN and ("cdrom" in d.opts or not d.fstype):
            continue
        try:
            u = psutil.disk_usage(d.mountpoint)
        except Exception:
            continue
        if u.total < 2 ** 30:
            continue
        zinnen.append("Schijf %s heeft nog %.0f gigabyte vrij (%d procent)." % (
            d.device.rstrip("\\:") if WIN else d.mountpoint, u.free / 2 ** 30, round(100 - u.percent)))
    try:
        op = time.time() - psutil.boot_time()
        uur = int(op // 3600)
        zinnen.append("De pc staat %s aan." % ("%d uur" % uur if uur < 48 else "%d dagen" % (uur // 24)))
    except Exception:
        pass
    try:
        b = psutil.sensors_battery()
        if b:
            zinnen.append("De accu is %d procent%s." % (b.percent, " en laadt op" if b.power_plugged else ""))
    except Exception:
        pass
    zwaar = []
    try:
        for p in sorted(psutil.process_iter(["name", "memory_info"]), key=lambda p: p.info["memory_info"].rss
                        if p.info.get("memory_info") else 0, reverse=True)[:3]:
            zwaar.append("%s (%d MB)" % (p.info["name"].replace(".exe", ""), p.info["memory_info"].rss // 2 ** 20))
        zinnen.append("De grootste geheugengebruikers zijn: %s." % ", ".join(zwaar))
    except Exception:
        pass
    zinnen.append("De temperatuur kan Windows mij helaas niet betrouwbaar geven.")
    return True, " ".join(zinnen)


# ============================================================================ bestanden zoeken
def zoek_bestanden(naam, max_n=8, max_sec=6.0):
    naam = naam.lower().strip().strip('"')
    if not naam:
        return []
    begin = time.time()
    plekken = [_map(m) for m in ("bureaublad", "documenten", "downloads", "afbeeldingen", "muziek", "video")]
    gevonden = []
    for wortel in dict.fromkeys(plekken):
        if not os.path.isdir(wortel):
            continue
        for map_, submappen, bestanden in os.walk(wortel):
            submappen[:] = [s for s in submappen if not s.startswith((".", "$", "node_modules", "__pycache__", "venv", ".venv"))]
            if map_.count(os.sep) - wortel.count(os.sep) > 6:
                submappen[:] = []
            for b in bestanden:
                if naam in b.lower():
                    p = os.path.join(map_, b)
                    try:
                        gevonden.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
            if time.time() - begin > max_sec:
                break
    gevonden.sort(reverse=True)
    return [p for _, p in gevonden[:max_n]]


def open_bestand(pad):
    try:
        os.startfile(pad) if WIN else subprocess.Popen(["xdg-open", pad])
        return True, "Ik open %s." % os.path.basename(pad)
    except Exception as e:
        return False, "Openen lukte niet: %s" % e


# ============================================================================ scherm en stroom
def vergrendel():
    if not WIN:
        return False, "Dat kan alleen op Windows."
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return True, "De pc is vergrendeld."


def afsluiten(herstart=False):
    if not WIN:
        return False, "Dat kan alleen op Windows."
    subprocess.Popen(["shutdown", "/r" if herstart else "/s", "/t", "60"], creationflags=0x08000000)
    return True, ("De pc %s over een minuut. Zeg 'annuleer afsluiten' als je je bedenkt." %
                  ("herstart" if herstart else "gaat uit"))


def annuleer_afsluiten():
    if not WIN:
        return False, "Dat kan alleen op Windows."
    subprocess.Popen(["shutdown", "/a"], creationflags=0x08000000)
    return True, "Afsluiten geannuleerd."


# ============================================================================ opruimen
def _grootte(pad):
    totaal = 0
    for map_, _, bestanden in os.walk(pad):
        for b in bestanden:
            try:
                totaal += os.path.getsize(os.path.join(map_, b))
            except OSError:
                pass
    return totaal


def opruim_plan():
    """Wat er opgeruimd kan worden (alleen tijdelijke bestanden ouder dan een dag)."""
    plekken = [os.environ.get("TEMP", "")]
    if WIN:
        plekken.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\INetCache"))
        plekken.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps"))
    plekken = [p for p in dict.fromkeys(plekken) if p and os.path.isdir(p)]
    grootte = sum(_grootte(p) for p in plekken)
    return plekken, grootte


def opruimen(plekken, prullenbak=True):
    grens = time.time() - 24 * 3600
    vrij = 0
    for wortel in plekken:
        for naam in os.listdir(wortel):
            p = os.path.join(wortel, naam)
            try:
                if os.path.getmtime(p) > grens:
                    continue            # recent: kan nog in gebruik zijn
                g = _grootte(p) if os.path.isdir(p) else os.path.getsize(p)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                vrij += g
            except Exception:
                continue                # in gebruik of geen toegang: overslaan
    bak = ""
    if prullenbak and WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)   # geen vragen, geen geluid
            bak = " De prullenbak is geleegd."
        except Exception:
            pass
    return True, "Opgeruimd: %.0f MB aan tijdelijke bestanden.%s" % (vrij / 2 ** 20, bak)


# ============================================================================ herkennen
ACTIES = {
    "open_programma": "een programma starten (argument: naam)",
    "sluit_programma": "een programma afsluiten (argument: naam)",
    "open_map": "een map openen: bureaublad, documenten, downloads, afbeeldingen, muziek, video's",
    "geluid": "harder, zachter, stil, pauze, volgende, vorige",
    "gezondheid": "hoe het met de pc gaat (processor, geheugen, schijven)",
    "zoek_bestand": "een bestand op de pc zoeken (argument: (deel van) de naam)",
    "schermafbeelding": "een schermafbeelding maken",
    "vergrendel": "de pc vergrendelen",
    "afsluiten": "de pc afsluiten", "herstarten": "de pc herstarten",
    "annuleer_afsluiten": "afsluiten of herstarten annuleren",
    "opruimen": "tijdelijke bestanden opruimen en de prullenbak legen",
}
RISKANT = {"sluit_programma", "afsluiten", "herstarten", "opruimen"}

PC_WOORDEN = re.compile(r"\b(pc|computer|laptop|geheugen|ram|werkgeheugen|processor|cpu|schijf|schijven|opslag|"
                        r"ruimte|traag|langzaam|vastlopen|loopt vast|warm|ventilator|memory|disk|storage|slow)\b", re.I)


def over_pc(tekst):
    """Gaat de vraag over de pc zelf? Dan geven we het taalmodel echte metingen mee (zodat het niets verzint)."""
    return bool(PC_WOORDEN.search(tekst or ""))


def herken(tekst):
    """Vaste zinnen herkennen (NL/EN). Geeft (actie, argument) of None."""
    t = tekst.lower().strip().rstrip("?!. ")
    regels = [
        (r"^(annuleer|stop|cancel) (het )?(afsluiten|herstarten|shutdown|restart)", "annuleer_afsluiten"),
        (r"\b(sluit|zet) (de )?(pc|computer) af\b|\b(pc|computer) uit(zetten)?\b|\bshut ?down\b", "afsluiten"),
        (r"\b(herstart|start opnieuw op|reboot|restart)\b", "herstarten"),
        (r"\b(vergrendel|lock)( (de|het))? ?(pc|computer|scherm|screen)?\b", "vergrendel"),
        (r"\b(schermafbeelding|screenshot|schermafdruk)\b", "schermafbeelding"),
        (r"\b(hoe gaat het met (de|mijn) (pc|computer|laptop)|hoe staat (de|mijn) (pc|computer|laptop) ervoor|"
         r"(status|toestand|gezondheid) van (de|mijn) (pc|computer|laptop)|(pc|computer|systeem)[- ]?(status|controle|check|"
         r"gezondheid)|hoe druk is (de|mijn) (pc|computer|processor)|hoeveel (vrije )?(schijf)?ruimte|hoeveel (vrij )?"
         r"geheugen|computer status|system status|how is my (pc|computer))\b", "gezondheid"),
        (r"\b(ruim|maak) (de |mijn )?(tijdelijke bestanden|temp|pc|computer|prullenbak)\b.*\b(op|leeg|schoon)\b|"
         r"\b(leeg de prullenbak|clean ?up|opruimen)\b", "opruimen"),
        (r"^(harder|louder)$|\b(volume omhoog|(geluid|volume|muziek) (wat |een beetje )?harder|volume up)\b",
         "geluid:harder"),
        (r"^(zachter|quieter)$|\b(volume omlaag|(geluid|volume|muziek) (wat |een beetje )?zachter|volume down)\b",
         "geluid:zachter"),
        (r"\b(demp|geluid uit|mute|unmute|geluid aan)\b", "geluid:stil"),
        (r"\b(volgende nummer|volgend liedje|next (song|track))\b", "geluid:volgende"),
        (r"\b(vorige nummer|vorig liedje|previous (song|track))\b", "geluid:vorige"),
        (r"^(pauze|pauzeer|play|pause)$|\b(pauzeer|speel|hervat|stop) (de |het )?(muziek|nummer|liedje|film|video)\b|"
         r"\bga verder met de muziek\b", "geluid:pauze"),
    ]
    for patroon, actie in regels:
        if re.search(patroon, t):
            if ":" in actie:
                a, arg = actie.split(":")
                return a, arg
            return actie, ""
    m = re.match(r"^(zoek|vind|find|search for) (het |de |mijn |naar )?(bestand|document|file|foto|map)( naar)?\s+(.+)$", t)
    if m:
        return "zoek_bestand", m.group(5)
    m = re.match(r"^(open|toon|laat .* zien) (mijn |de )?(map )?(bureaublad|desktop|documenten|documents|downloads?|"
                 r"afbeeldingen|foto'?s|pictures|muziek|music|video'?s|films|temp)( map)?$", t)
    if m:
        return "open_map", m.group(4)
    m = re.match(r"^(sluit|stop|beëindig|close|quit)\s+(het programma\s+)?(.+)$", t)
    if m and m.group(3) not in ("af",):
        return "sluit_programma", m.group(3)
    m = re.match(r"^(start|open|begin)\s+(het programma\s+|de app\s+)?(.+)$", t)
    if m:
        naam = m.group(3)
        # websites laat vaardigheden.py doen
        if "." in naam or naam in ("youtube", "google", "wikipedia", "gmail", "github", "nos", "buienradar",
                                    "facebook", "netflix", "weer", "maps", "kaart"):
            return None
        return "open_programma", naam
    return None
