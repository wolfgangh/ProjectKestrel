# AGENTS.md — Project Kestrel

Anweisungen für Coding-Agenten (Cursor / Grok Build 4.6 und andere) in diesem Checkout.

README.md ist für Menschen. DEVELOPMENT.md ist die Packaging-/Architektur-Referenz.
Diese Datei steuert Agent-Verhalten: wie prüfen, was schon gelöst ist, was noch integriert
werden muss, was nicht angefasst wird.

Sprache: mit dem Nutzer Deutsch. Code, Branches, Commits, Dateinamen, PR-Titel Englisch.

---

## 1. Was dieses Projekt ist

Project Kestrel ist eine lokale Desktop-App für Vogelfotografen.

Sie gruppiert Bursts zu Szenen, erkennt und segmentiert Tiere, bewertet Schärfe/Blur/Rauschen
auf der Vogelmaske, taggt Arten, schreibt XMP/JPEG-Metadaten und hilft beim Culling.
Optional: Perch (Outing-Timeline) und Cloud Compute (Remote-GPU). Die Desktop-App muss
ohne Account und ohne Netz voll funktionieren.

Repo-Upstream: https://github.com/SanjaySoniLV/ProjectKestrel
Aktueller Release-Kontext: v(Dusky Grouse) und Folgezweige. Python 3.11, Lizenz AGPLv3
(Brand-Assets unter `assets/` sind NICHT AGPL).

Architektur in einem Satz: pywebview-Shell um Vanilla-JS/HTML/CSS, Python-Backend
exponiert die Klasse `Api` über die pywebview-Bridge. Kein SPA-Framework, kein PyQt,
kein separater Visualizer-Server.

---

## 2. Karte (lies diese Dateien zuerst)

```
analyzer/visualizer.py           # App-Einstieg: pywebview + lokaler HTTP-Server
analyzer/api_bridge.py           # Api — jeder JS↔Python-Call landet hier
analyzer/queue_manager.py        # Sequenzielle Ordner-Analyse-Queue
analyzer/settings_utils.py       # Atomare settings.json + Schema-Upgrade
analyzer/cli.py                  # Headless-Analyse
analyzer/metadata_writer.py      # XMP / JPEG-Embed
analyzer/editor_launch.py        # Externer Editor
analyzer/folder_inspector.py     # Leichtgewichtiges Ordner-Probing
analyzer/visualizer.html
analyzer/culling.html
analyzer/js/                     # UI-Logik (nicht eine einzige Riesen-JS annehmen)
analyzer/css/
analyzer/kestrel_analyzer/       # Pipeline, UI-frei
  pipeline.py
  database.py                    # kestrel_database.csv, Migration, Saves
  ratings.py
  similarity.py
  exposure_compensation.py
  raw_exif.py
  image_utils.py
  bird_catalog.py
  logging_utils.py
  validation.py
  config.py
  ml/                            # SpeciesNet, SAM-HQ, QualityClassifier, Provider
analyzer/cloud_compute_client.py
analyzer/perch_uploader.py
analyzer/auth_client.py
analyzer/log_redactor.py
analyzer/net_tls.py
analyzer/mac_sandbox.py
analyzer/tests/                  # pytest.ini liegt HIER
DEVELOPMENT.md
TODO.md
packaging/
```

Laufzeitartefakte im Fotoordner: verstecktes `.kestrel/`
(`export/`, `crop/`, `kestrel_database.csv`, scenedata, XMP, Fingerprints, Logs).
Analyse darf manuelle User-Daten nicht überschreiben.

---

## 3. Befehle

Desktop:

```bash
python analyzer/visualizer.py
```

Headless:

```bash
python analyzer/cli.py "PFAD" --no-gpu --parallel-prefetch 1
python analyzer/visualizer.py --cli "PFAD" --no-gpu
```

Tests (Working Directory = Repo-Root; `conftest.py` hängt `analyzer/` in sys.path):

```bash
pytest analyzer/tests -m unit -q
pytest analyzer/tests/unit/test_database.py -v
PYTHONPATH=analyzer python -m unittest analyzer.tests.test_speciesnet_taxonomy -v
```

Models liegen unter `analyzer/models/` und kommen über Git LFS. Fehlen die Gewichte
(Pointer-Stubs ~130 Byte), keine Pipeline-Smoke-Tests erzwingen. Unit-Tests ohne
ONNX priorisieren.

Abhängigkeiten: `requirements-windows.txt` / `requirements-macos.txt` / `requirements.txt`.
`numpy==2.1.3` gepinnt halten. Nicht `opencv-python` und `opencv-python-headless`
parallel installieren.

---

## 4. Harte Regeln

1. Code lesen. Nicht raten. Datei:Zeile angeben.
2. Nichts ändern, bevor der Nutzer es explizit verlangt — Ausnahme: der Auftrag
   lautet ausdrücklich „integriere die PRs“ oder „implementiere Fix X“.
3. Keine Drive-by-Refactors, keine Repo-weiten Formats, keine Rename-Orgien.
4. Ein Branch = ein Fix + Tests. Keine Feature-Arbeit in einem Review-Branch.
5. `main` und `dev` sind verschiedene Baselines. Neue wolfgangh-PRs gegen
   SanjaySoniLV/ProjectKestrel zielen auf `dev`, nicht auf `main`. Nicht still
   die falsche Basis mergen.
6. Bestehende atomare I/O-Muster wiederverwenden
   (`tempfile` + `fsync` + `os.replace`, Locks in `settings_utils.py`).
   Kein `open(path, 'w')` auf persistente User-Daten.
7. `shutil.move` nicht für User-Dateien verwenden, wenn die Zieldatei existieren
   kann — auf POSIX überschreibt das still.
8. Exceptions nicht schlucken und danach Erfolg nach oben melden.
   Validierungsfehler dürfen weiche Fallback-Werte liefern;
   Infrastrukturfehler (ONNX-Session, Disk-full, Flush-Fehler) müssen propagieren.
9. Bridge-Pfade bleiben unter `KESTREL_ALLOWED_ROOT`. `open_url` nur http/https/mailto.
   XMP-Dateinamen ohne Separatoren, Laufwerksbuchstaben, UNC.
10. Brand-Namen und Logos unter `assets/` nicht umlizenzieren oder entfernen.
11. Findings-Format:
    - Titel
    - Severity S0 (Datenverlust/Korruption) / S1 (Crash, falsches Ranking, stille
      Falschmeldung) / S2 (Leak, UX-Stall, Plattformkante) / S3 (Hygiene)
    - Datei:Zeile
    - Repro
    - Impact
    - Fixrichtung
    - Testvorschlag
    - Status: `neu` | `abgedeckt durch #NNN, Integration ausstehend` | `Produktentscheidung`
12. Dieselbe Bugklasse darf nach analogem Muster an ANDEREN Stellen gesucht werden.
    Derselbe schon gepatchte Bug darf nicht als neues Finding erscheinen.

---

## 5. Gelöste Probleme — PRs existieren, Merge/Integration ausstehend

Diese Bugs sind fachlich gelöst. Nicht neu erfinden. Wenn `main` sie noch enthält:
Status „PR vorhanden, Implementierung ausstehend“ plus Nummer und Branch.

Autor der Cursor-Fixes: wolfgangh.
Upstream-Ziel: SanjaySoniLV/ProjectKestrel, Base immer `dev`.

### P1 Datenintegrität / Dateisystem

| PR | Branch | Satz |
|----|--------|------|
| #120 | `cursor/fix-culling-move-safety-554a` | Reject-Move darf existierende Dateien nicht per `shutil.move` überschreiben. Neuer Contract: `(success, moved_files, error)`. |
| #121 | `cursor/fix-atomic-scenedata-writes-554a` | scenedata und UI-CSV atomar (`write_text_atomic` / `write_json_atomic`). Kein `open('w')` + `json.dump` auf Geschwister der DB. |
| #125 | `cursor/fix-atomic-backup-restore-554a` | DB/scenedata-Backups atomar restaurieren (`copy_file_atomic` + `os.replace`). |
| #124 | `cursor/fix-legacy-rating-migration-554a` | Manuelle 1–5-Ratings mit leerem `rating_origin` bei Migration behalten. Leeres Origin wie fehlende Spalte. |
| #128 | `cursor/fix-xmp-overwrite-fingerprint-554a` | Extern editierte Kestrel-XMPs nicht als intern überschreiben. SHA256 in `.kestrel/xmp_fingerprints.json`. Unveränderte Kestrel-Sidecars dürfen still geschrieben werden; fremd-editierte nur bei `overwrite_external=True`, sonst `skipped_conflicts`. |
| #130 | `cursor/fix-reject-filename-case-9b5c` | Reject/Undo der **Hauptdatei** case-insensitive über Directory-Index. Companions sind schon case-insensitive (historisch #98), Mains waren es nicht. |

Fork-zusätzlich, gegen Upstream spiegeln falls fehlend:

| Fork-PR | Branch | Satz |
|---------|--------|------|
| wolfgangh#15 | `cursor/fix-csv-atomic-flush-9b5c` | Flush-/fsync-Fehler im atomaren CSV-Save nicht schlucken. |

### P1 Pipeline / Queue / ML

| PR | Branch | Satz |
|----|--------|------|
| #122 | `cursor/fix-queue-error-and-decode-leak-554a` | Fatale Pipeline-Fehler nicht als `done`. `on_error`-Callback. Decode-Generator: `stop_event` + `try/finally`, keine Thread-Leaks bei Abbruch. |
| #123 | `cursor/fix-queue-robustness-554a` | Worker-Start unter Lock (kein TOCTOU). `use_gpu` auf wiederverwendete Pipeline propagieren. |
| #127 | `cursor/fix-quality-session-errors-554a` | `QualityClassifier.classify`: Input/Output-Validierung darf `-1.0` liefern. `session.run`-Fehler müssen propagieren, damit CPU-Fallback greifen kann. |

### P1 Logging / Frozen Builds

| PR | Branch | Satz |
|----|--------|------|
| #126 | `cursor/fix-faulthandler-windowed-554a` | PyInstaller `--windowed`: `sys.stdout`/`stderr` ist `None`. `_TeeStream.fileno()` darf faulthandler nicht killen — Fallback auf Log-FD. |
| #129 | `cursor/fix-utcnow-showwarning-recursion-9b5c` | Kein `datetime.utcnow`. `datetime.now(timezone.utc)`. `warnings.showwarning`-Hook re-entrant (thread-local Guard) + `RLock` auf Log-Writes. |

### P2 UI

| PR | Branch | Satz |
|----|--------|------|
| #118 | `cursor/fix-filmstrip-thumbnail-loading-554a` | Lazy-Loader darf detached `<img>` nach schnellem Szenenwechsel nicht weiterladen. Vor und nach IPC-Read `isConnected` prüfen. |
| #119 | `cursor/fix-bloburlcache-revoke-554a` | Blob-URL-Cache als LRU (max 512), `URL.revokeObjectURL` bei Eviction und `clear()`. |

### Dev-Env (optional, nicht Teil der Produktfixes)

| Fork-PR | Branch | Satz |
|---------|--------|------|
| wolfgangh#1 | `cursor/setup-dev-environment-554a` | Cloud-Agent-Setup (`.cursor/environment.json`, `install.sh`). Nur anfassen wenn der Nutzer Dev-Env will. |

---

## 6. Fremde offene PRs — Kontext, nicht „meine Fixes“

Nicht als erledigt verbuchen, nicht in wolfgangh-Branches nachbauen, es sei denn der Nutzer verlangt Rebase/Konfliktcheck.

- #117 Scene-Grid zeigt Accept/Reject/Unreviewed (Base oft `dev`)
- #116 Shift-Click-Anchor folgt Tastatur-Navigation (`dev`)
- #115 Done Culling nach früherem Cull nicht disable-n (`dev`)
- #114 Clean-Exit-Marker VOR Shutdown-Teardown (`dev`)
- #113 Alternate Keys 7/8/9 neben Z/X/C (`dev`)
- #112 Stale Species-Labels nach Scene-Split droppen (`dev`)
- #111 Linux ONNX-Provider + Queue false-positive completion
- #108 Unclean-Shutdown-False-Positive bei zweiter Instanz
- #107 Pillow 12.3.0 (Dependabot)

Diese PRs ändern Nachbarschaft. Vor dem Anfassen von Scene-Grid, Culling-Button-Enablement
oder Shutdown-Markern zuerst den jeweiligen Diff lesen.

---

## 7. Arbeitsmodi

Der Nutzer startet einen Modus, indem er den Namen nennt oder den Auftrag zitiert.
Nicht alle Modi in einer Session abarbeiten.

### Modus A — PR-Integration

Ziel: die Tabelle aus Abschnitt 5 in den aktuellen Arbeitsbaum bringen.

Reihenfolge:

1. I/O-Atomarität: #121, Fork-#15, #125
2. Culling-Dateisicherheit: #120, #130
3. Datenmodell: #124, #128
4. Queue/Pipeline: #122, #123, #127
5. Logging/Frozen: #129, #126
6. UI: #118, #119

Vorgehen:

- `git status`, `git branch -vv`, `git log --oneline -20`, Remotes prüfen.
- Pro Fix: schon im Tree? Dann nur Tests. Sonst Cherry-Pick vom `cursor/fix-…`-Branch
  oder den PR-Diff anwenden.
- Konflikte klein halten. Keine stillen Verhaltensänderungen außerhalb des PR-Scopes.
- Nach jedem Fix die PR-eigenen Tests plus eine knappe Nachbar-Regression.

Deliverable: Tabelle `PR | integriert | Commit | Tests | Restkonflikte`.

### Modus B — Bestandsaufnahme (read-only)

Laufzeitpfade, Datenflüsse, Trust Boundaries, Plattform-Matrix, Coverage- grob.
Mermaid erlaubt. Keine Patches.

### Modus C — Datenintegrität, neue Löcher derselben Klasse (read-only bis Auftrag)

Suche Geschwister, nicht die schon geschlossenen Bugs:

- weitere nicht-atomare Writes (`open('w')`, `to_csv`, `json.dump`, `Path.write_text`,
  `shutil.copy`, `shutil.move`)
- weitere Restore/Backup-Pfade
- Clear-Analysis, Re-Analyse, Undo/Restore
- CSV-Lesen während Analyse
- weitere Ratings-Migrationskanten (NaN, `"None"`, fehlende Spalten)
- weitere XMP/JPEG-Overwrite-Pfade
- Case-Sensitivity außerhalb Reject-Mains (Editor, Folder-Inspector, RAW+JPG,
  Sample-Sets, Cloud-Job-State)
- Windows vs POSIX overwrite-Semantik
- `mac_sandbox.py` Bookmarks

### Modus D — Pipeline / Queue / ML (read-only bis Auftrag)

Nicht neu reporten: #122 #123 #127.

Suchen: geschluckte Exceptions mit Erfolgsmeldung, GPU→CPU-Fallback und Provider
(Linux/#111), Generatoren ohne Cancel bei Quit, Scene-Split/Merge-Labels (#112),
manuelle Ratings vs Auto vs Culling-Cutoff, Exposure-Compensation Fail-open/closed,
Prefetch/Masken-Memory.

### Modus E — UI / Bridge (read-only bis Auftrag)

Nicht neu reporten: #118 #119.

Suchen: weitere ungebundene Caches, stale Promises nach Szenenwechsel, Bridge-Teilfehler
als UI-Erfolg (neuer Move-Contract aus #120), Shortcut-Kollisionen, XSS über Dateinamen
und Species-Labels, Event-Wiring nach Dialog-Reopen.
Immer die konkrete JS-Datei nennen.

### Modus F — Security / Privacy / Packaging (read-only bis Auftrag)

Baseline: `analyzer/tests/test_security_*.py` und `analyzer/tests/security/`.

Path-Jail, Symlinks, Mapped Drives, UNC, `open_url`, Editor-Pfade, XMP-Namen,
`log_redactor.py`, Token-Storage in Auth/OAuth/Cloud/Perch, TLS (`net_tls.py`),
weitere None-stdio-Stellen, Entitlements vs Dev-Run.

Datei-/Ordnernamen in Crash-Reports sind eine dokumentierte Produktentscheidung
(TODO.md / Terms) — kein Finding, außer Secrets/Tokens/Auth-Header landen mit.

### Modus G — Tests / CI (read-only bis Auftrag)

Decken die neuen PR-Tests Crash-während-Write und Negativfälle ab?
Welche Pfade sind nur manuell belegt?
Welche Tests brauchen LFS-Models und werden still skipped?
Maximal 8–12 neue Testvorschläge, je Arrange/Act/Assert in wenigen Zeilen.

### Modus H — Abschluss

A. Integrationsstatus der eigenen PRs
B. Restliche S0/S1, die NICHT durch Abschnitt 5 abgedeckt sind (max 15)
C. Kurze S2-Liste
D. Produktentscheidungen / bewusst ignoriert
E. Nächste Arbeitspakete, jeweils ein Branch
F. Was nicht angefasst wurde (Weights, Perch-Server, Signing-Secrets)

---

## 8. Testkonventionen für neue Fixes

- Testdateien unter `analyzer/tests/unit/` oder dem bestehenden Modulordner.
- Marker aus `analyzer/tests/pytest.ini` respektieren (`unit`, `integration`, `e2e`,
  `compat`, `ui`).
- Keine echten Vogel-RAWs oder Model-Gewichte committen.
- Filesystem-Tests isoliert in `tmp_path`. Case-Sensitivity explizit testen
  (`IMG_2265.JPG` vs `.jpg`) — das ist auf Linux und case-sensitive APFS echt.
- Atomare Write-Tests: simulierte Fehlschläge müssen die vorherige Datei unangetastet lassen.
- Queue-Tests: Concurrency am Lock, nicht „einmal enqueue und hoffen“.

---

## 9. Nicht anfassen (ohne expliziten Auftrag)

- ONNX-/SpeciesNet-Gewichte und Retraining
- Perch-Backend, Cloudflare-Worker, Store-Listings
- Signing/Notarization-Secrets, App-Store-Preis, Telemetrie-Policy
- `assets/` Branding
- Abhängigkeits-Bumps außer dem konkreten Fix
- Großflächiges Portieren von `dev` nach `main`

---

## 10. Session-Start-Checkliste für den Agenten

Bevor du Code schreibst oder einen Review-Roman lieferst:

1. Arbeitsbaum und Branch nennen.
2. Sagen, welche PRs aus Abschnitt 5 schon im Tree sind und welche nicht.
3. Den angeforderten Modus (A–H) bestätigen.
4. Wenn der Nutzer „prüfe das Projekt in aller Tiefe“ sagt und keinen Modus nennt:
   zuerst Modus A vorschlagen, nicht sofort Modus C–F parallel.

Wenn ein vorgeschlagener Patch einen Bug aus Abschnitt 5 „nochmal löst“:
ablehnen, den existierenden Branch/PR nennen, Integration anbieten.
