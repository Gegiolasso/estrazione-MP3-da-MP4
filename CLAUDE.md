# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Panoramica

Script Python con interfaccia grafica (Tkinter) per estrarre la traccia audio da file video e salvarla in formato MP3. Supporta due modalità:
- **File locali** — tramite `moviepy` (che internamente richiede `ffmpeg`)
- **URL di video online** — tramite `yt-dlp` (YouTube, Vimeo, ecc.)

L'output viene salvato in una cartella fissa configurabile nello script.

## Esecuzione

```bash
python estrai_audio_mp4.py
```

Oppure tramite il file batch `estrai_audio.bat` (nota: il percorso nel .bat punta a un path obsoleto senza la cartella "Codex e Claude Code").

## Dipendenze

- **moviepy** - `pip install moviepy` (per file video locali)
- **yt-dlp** - `pip install yt-dlp` (per download da URL)
- **ffmpeg** - deve essere installato e raggiungibile dal PATH (usato sia da moviepy che da yt-dlp)
- **selenium** - `pip install selenium` (per estrazione URL video da pagine autenticate; Selenium 4.6+ include Selenium Manager che scarica ChromeDriver automaticamente)
- **tkinter** - incluso nella distribuzione standard di Python
- **deno** (opzionale) - runtime JavaScript per yt-dlp; consigliato per evitare warning ma non indispensabile

### Aggiornamento yt-dlp

**Importante**: yt-dlp deve essere aggiornato frequentemente perché YouTube e altre piattaforme cambiano spesso le loro API. Se il download fallisce con errori 403 o simili:

```bash
pip install --upgrade yt-dlp
```

Questo risolve la maggior parte dei problemi di download. Il team di yt-dlp rilascia aggiornamenti frequenti per stare al passo con i cambiamenti delle piattaforme video.

## Configurazione

La cartella di output è definita come costante in cima allo script:
```python
OUTPUT_DIR = r"C:\Users\Gege.ERREEMME22\Dropbox\documenti lavoro\AI\video e webinar\versione MP3"
```

## Architettura

Singolo script (`estrai_audio_mp4.py`) con interfaccia grafica Tkinter:

1. `is_url(text)` — determina se l'input è un URL
2. `is_video_platform(url)` — controlla se l'URL è di una piattaforma video nota (YouTube, Vimeo, ecc.)
3. `_selenium_login_interattivo(url, status_callback)` — apre Chrome visibile per login manuale (una tantum)
4. `estrai_url_video_da_pagina(url, status_callback)` — usa Selenium con profilo dedicato per trovare video embed in pagine SPA autenticate
5. `_cerca_video_in_iframes(driver)` / `_cerca_tag_video(driver)` — helper per cercare video in iframe e tag `<video>`
6. `scarica_e_converti_da_url(url, output_dir, status_callback, use_cookies, referer)` — download e conversione via `yt-dlp`
7. `estrai_audio_da_file(file_video, output_dir, status_callback)` — estrazione audio via `moviepy.VideoFileClip`
8. `avvia_processo(input_text, status_callback, done_callback, use_cookies)` — orchestratore che sceglie il percorso giusto
9. `crea_gui()` — finestra Tkinter con campo input, pulsante sfoglia, area log e pulsante avvia

Il lavoro pesante viene eseguito in un thread separato per non bloccare la GUI. L'import di moviepy usa la sintassi diretta `from moviepy import VideoFileClip` (moviepy v2+).

## Cookie browser

La GUI include una checkbox **"Usa cookie da Chrome"**. Il comportamento dipende dal tipo di URL:
- **Piattaforma video nota** (YouTube, Vimeo, ecc.): yt-dlp usa `--cookies-from-browser chrome` per accedere a video che richiedono autenticazione
- **Pagina SPA/sito generico** (es. Circle.so): Selenium estrae l'URL del video embed, poi yt-dlp lo scarica **senza** cookie di Chrome (usa solo il `--referer`). I cookie Chrome v20 (App-Bound Encryption, Chrome 127+) non sono decifrabili da yt-dlp

## Estrazione automatica da pagine SPA (Selenium)

Quando la checkbox "Usa cookie da Chrome" è attiva e l'URL **non** è di una piattaforma video nota (YouTube, Vimeo, ecc.), lo script usa un **profilo Chrome dedicato** (`.selenium_profile/` nella cartella dello script):

1. Prova ad aprire la pagina in headless con il profilo dedicato
2. Se la pagina reindirizza al login (sessione assente o scaduta):
   - Apre Chrome **visibile** per il login manuale dell'utente (una tantum)
   - L'utente effettua il login e chiude Chrome
   - La sessione viene salvata nel profilo dedicato
3. Riprova in headless con la sessione salvata
4. Cerca iframe o tag `<video>` contenenti embed di piattaforme video note (Vimeo, Wistia, YouTube, ecc.)
5. Estrae l'URL reale del video embed
6. Passa l'URL a yt-dlp con il referer della pagina originale

**Nota tecnica**: Il profilo Chrome dell'utente non può essere usato direttamente da Selenium perché Chrome blocca il debug port sulla sua directory predefinita e i cookie v20 (App-Bound Encryption, Chrome 127+) non sono decifrabili dall'esterno. Il profilo dedicato risolve entrambi i problemi.

**Profilo dedicato**: Salvato in `.selenium_profile/` — può essere cancellato per forzare un nuovo login. Non interferisce con Chrome in uso.

Questo flusso è utile per piattaforme SPA come Circle.so dove il video è incorporato via JavaScript e yt-dlp non riesce a trovarlo direttamente.
