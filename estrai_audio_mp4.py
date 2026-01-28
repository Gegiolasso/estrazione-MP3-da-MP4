#!/usr/bin/env python3
"""
Script per estrarre l'audio da file video (locali o da URL) e salvarlo in formato MP3.
Supporta file locali (via moviepy) e URL di video online (via yt-dlp).
Interfaccia grafica Tkinter.
"""

import tkinter as tk
from tkinter import filedialog
import os
import threading
import subprocess
import sys

# --- Configurazione ---
OUTPUT_DIR = r"C:\Users\Gege.ERREEMME22\Dropbox\documenti lavoro\AI\video e webinar\versione MP3"

# Profilo Chrome dedicato per Selenium (persistente tra le sessioni)
SELENIUM_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".selenium_profile")

# Domini di piattaforme video che yt-dlp gestisce direttamente (non serve Selenium)
VIDEO_PLATFORMS = (
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "twitch.tv", "facebook.com", "fb.watch", "instagram.com",
    "tiktok.com", "twitter.com", "x.com", "rumble.com",
    "bitchute.com", "odysee.com", "peertube.tv",
)

# Domini da cercare negli iframe per trovare video embedded
VIDEO_EMBED_HOSTS = (
    "player.vimeo.com", "vimeo.com",
    "youtube.com", "youtube-nocookie.com", "youtu.be",
    "fast.wistia.net", "fast.wistia.com",
    "dailymotion.com",
    "player.twitch.tv",
    "vidyard.com",
    "brightcove.net", "players.brightcove.net",
    "jwplatform.com", "cdn.jwplayer.com",
    "streamable.com",
    "loom.com",
    "bunny.net", "iframe.mediadelivery.net",
)


def is_url(text):
    """Determina se l'input è un URL."""
    return text.strip().startswith(("http://", "https://"))


def is_video_platform(url):
    """Controlla se l'URL appartiene a una piattaforma video nota (gestita direttamente da yt-dlp)."""
    from urllib.parse import urlparse
    hostname = urlparse(url.strip()).hostname or ""
    hostname = hostname.lower().removeprefix("www.")
    return any(hostname == domain or hostname.endswith("." + domain) for domain in VIDEO_PLATFORMS)


def _selenium_login_interattivo(url, status_callback):
    """Apre Chrome visibile con il profilo dedicato per il login manuale dell'utente."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import time

    os.makedirs(SELENIUM_PROFILE_DIR, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={SELENIUM_PROFILE_DIR}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")

    status_callback("Apertura Chrome per login manuale...")
    status_callback("Effettua il login nel sito, poi CHIUDI la finestra di Chrome.")
    driver = webdriver.Chrome(options=options)

    driver.get(url.strip())

    # Attendi che l'utente chiuda Chrome
    try:
        while True:
            try:
                _ = driver.title
                time.sleep(1)
            except Exception:
                break
    except Exception:
        pass

    status_callback("Login completato. Sessione salvata nel profilo dedicato.")


def estrai_url_video_da_pagina(url, status_callback):
    """Usa Selenium con profilo dedicato per aprire una pagina autenticata e cercare video embed."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import time

    os.makedirs(SELENIUM_PROFILE_DIR, exist_ok=True)

    # Prova prima in headless con il profilo salvato
    options = Options()
    options.add_argument(f"--user-data-dir={SELENIUM_PROFILE_DIR}")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")

    driver = None
    try:
        status_callback("Avvio Chrome con profilo Selenium...")
        driver = webdriver.Chrome(options=options)

        status_callback(f"Navigazione a: {url}")
        driver.get(url.strip())

        # Attendi caricamento JS e scroll per lazy loading
        time.sleep(8)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        page_title = driver.title
        status_callback(f"Pagina caricata: {page_title}")

        # Verifica se siamo finiti su una pagina di login
        current_url = driver.current_url.lower()
        if "login" in current_url or "sign_in" in current_url or "signin" in current_url:
            driver.quit()
            driver = None

            # Login interattivo necessario
            status_callback("Sessione non valida. Serve il login manuale (una tantum).")
            _selenium_login_interattivo(url, status_callback)

            # Riprova in headless dopo il login
            status_callback("Riprovo con la sessione appena creata...")
            driver = webdriver.Chrome(options=options)
            driver.get(url.strip())
            time.sleep(8)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            page_title = driver.title
            status_callback(f"Pagina caricata: {page_title}")

            current_url = driver.current_url.lower()
            if "login" in current_url or "sign_in" in current_url or "signin" in current_url:
                raise RuntimeError(
                    "Login non riuscito. Verifica le credenziali e riprova."
                )

        status_callback("Ricerca iframe/video nella pagina...")

        # 1. Cerca iframe con src contenente un host video noto
        video_url = _cerca_video_in_iframes(driver)
        if video_url:
            status_callback(f"Video trovato (iframe): {video_url}")
            return video_url

        # 2. Cerca tag <video> con src diretto
        video_url = _cerca_tag_video(driver)
        if video_url:
            status_callback(f"Video trovato (tag video): {video_url}")
            return video_url

        # 3. Entra negli iframe e cerca dentro (nested)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for i, iframe in enumerate(iframes):
            try:
                driver.switch_to.frame(iframe)
                status_callback(f"Esplorazione iframe #{i + 1}...")

                video_url = _cerca_video_in_iframes(driver)
                if video_url:
                    status_callback(f"Video trovato (iframe nested): {video_url}")
                    return video_url

                video_url = _cerca_tag_video(driver)
                if video_url:
                    status_callback(f"Video trovato (video nested): {video_url}")
                    return video_url

                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()

        raise RuntimeError("Nessun video trovato nella pagina. Controlla che l'URL contenga un video.")

    finally:
        if driver:
            driver.quit()


def _cerca_video_in_iframes(driver):
    """Cerca iframe con src contenente un host video noto."""
    from selenium.webdriver.common.by import By
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if not src:
            continue
        src_lower = src.lower()
        for host in VIDEO_EMBED_HOSTS:
            if host in src_lower:
                # Normalizza URL
                if src.startswith("//"):
                    src = "https:" + src
                return src
    return None


def _cerca_tag_video(driver):
    """Cerca tag <video> con src diretto o <source>."""
    from selenium.webdriver.common.by import By
    videos = driver.find_elements(By.TAG_NAME, "video")
    for video in videos:
        src = video.get_attribute("src") or ""
        if src and src.startswith("http"):
            return src
        sources = video.find_elements(By.TAG_NAME, "source")
        for source in sources:
            src = source.get_attribute("src") or ""
            if src and src.startswith("http"):
                return src
    return None


def scarica_e_converti_da_url(url, output_dir, status_callback, use_cookies=False, referer=None):
    """Scarica un video da URL e lo converte in MP3 usando yt-dlp."""
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_template,
    ]

    if use_cookies:
        cmd += ["--cookies-from-browser", "chrome"]

    if referer:
        cmd += ["--referer", referer]

    cmd.append(url.strip())

    status_callback(f"Avvio download e conversione (cookies={'sì' if use_cookies else 'no'}, referer={'sì' if referer else 'no'})...")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for line in process.stdout:
        line = line.strip()
        if line:
            status_callback(line)

    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"yt-dlp terminato con codice {process.returncode}")

    status_callback("Conversione completata!")


def estrai_audio_da_file(file_video, output_dir, status_callback):
    """Estrae l'audio da un file video locale e lo salva come MP3."""
    from moviepy import VideoFileClip

    os.makedirs(output_dir, exist_ok=True)

    nome_base = os.path.splitext(os.path.basename(file_video))[0]
    file_mp3 = os.path.join(output_dir, f"{nome_base}.mp3")

    status_callback(f"Caricamento video: {os.path.basename(file_video)}")
    video = VideoFileClip(file_video)

    status_callback("Estrazione audio in corso...")
    video.audio.write_audiofile(file_mp3, logger=None)
    video.close()

    status_callback(f"Audio salvato: {file_mp3}")
    return file_mp3


def avvia_processo(input_text, status_callback, done_callback, use_cookies=False):
    """Orchestratore: decide se usare yt-dlp o moviepy in base all'input."""
    try:
        input_text = input_text.strip()
        if not input_text:
            status_callback("ERRORE: Nessun input fornito.")
            done_callback(False)
            return

        if is_url(input_text):
            status_callback(f"Rilevato URL: {input_text}")

            download_url = input_text
            referer = None

            # Se i cookie sono attivi e l'URL non è una piattaforma video nota,
            # usa Selenium per estrarre l'URL reale del video dalla pagina
            if use_cookies and not is_video_platform(input_text):
                status_callback("URL non riconosciuto come piattaforma video. Tentativo estrazione con Selenium...")
                try:
                    video_url = estrai_url_video_da_pagina(input_text, status_callback)
                    referer = input_text
                    download_url = video_url
                    # L'URL estratto è su un dominio diverso (es. Vimeo):
                    # i cookie di Chrome non servono, basta il referer.
                    # Inoltre --cookies-from-browser chrome fallisce con DPAPI v20.
                    use_cookies = False
                    status_callback(f"URL video estratto: {video_url}")
                except RuntimeError as e:
                    status_callback(f"ERRORE Selenium: {e}")
                    done_callback(False)
                    return

            scarica_e_converti_da_url(download_url, OUTPUT_DIR, status_callback,
                                     use_cookies=use_cookies, referer=referer)
        else:
            if not os.path.isfile(input_text):
                status_callback(f"ERRORE: File non trovato: {input_text}")
                done_callback(False)
                return
            status_callback(f"Rilevato file locale: {input_text}")
            estrai_audio_da_file(input_text, OUTPUT_DIR, status_callback)

        status_callback(f"\nFile MP3 salvato in:\n{OUTPUT_DIR}")
        done_callback(True)

    except Exception as e:
        status_callback(f"ERRORE: {e}")
        done_callback(False)


def crea_gui():
    """Crea e avvia l'interfaccia grafica."""
    root = tk.Tk()
    root.title("Estrattore Audio → MP3")
    root.geometry("700x480")
    root.resizable(True, True)

    # --- Input ---
    frame_input = tk.LabelFrame(root, text="Input (URL o percorso file)", padx=10, pady=5)
    frame_input.pack(fill="x", padx=10, pady=(10, 5))

    entry_input = tk.Entry(frame_input, font=("Segoe UI", 10))
    entry_input.pack(side="left", fill="x", expand=True, pady=5)

    def sfoglia():
        file_path = filedialog.askopenfilename(
            title="Seleziona un file video",
            filetypes=[
                ("File video", "*.mp4 *.mkv *.avi *.mov *.webm *.flv"),
                ("Tutti i file", "*.*"),
            ],
        )
        if file_path:
            entry_input.delete(0, tk.END)
            entry_input.insert(0, file_path)

    btn_sfoglia = tk.Button(frame_input, text="Sfoglia...", command=sfoglia)
    btn_sfoglia.pack(side="right", padx=(5, 0), pady=5)

    # --- Output info ---
    frame_output = tk.LabelFrame(root, text="Cartella di output", padx=10, pady=5)
    frame_output.pack(fill="x", padx=10, pady=5)

    lbl_output = tk.Label(frame_output, text=OUTPUT_DIR, font=("Segoe UI", 9), anchor="w", fg="#555555")
    lbl_output.pack(fill="x", pady=2)

    # --- Opzione cookie ---
    use_cookies_var = tk.BooleanVar(value=False)
    chk_cookies = tk.Checkbutton(root, text="Usa cookie da Chrome (per piattaforme con login)",
                                  variable=use_cookies_var, font=("Segoe UI", 9))
    chk_cookies.pack(padx=10, pady=(5, 0), anchor="w")

    # --- Pulsante avvia ---
    btn_avvia = tk.Button(root, text="Avvia estrazione", font=("Segoe UI", 11, "bold"),
                          bg="#4CAF50", fg="white", height=1)
    btn_avvia.pack(padx=10, pady=5, fill="x")

    # --- Area log ---
    frame_log = tk.LabelFrame(root, text="Stato", padx=10, pady=5)
    frame_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    text_log = tk.Text(frame_log, font=("Consolas", 9), state="disabled", wrap="word")
    scrollbar = tk.Scrollbar(frame_log, command=text_log.yview)
    text_log.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    text_log.pack(fill="both", expand=True)

    def log(messaggio):
        """Aggiunge un messaggio all'area di log (thread-safe)."""
        def _update():
            text_log.configure(state="normal")
            text_log.insert("end", messaggio + "\n")
            text_log.see("end")
            text_log.configure(state="disabled")
        root.after(0, _update)

    def on_done(successo):
        """Callback di fine processo (thread-safe)."""
        def _update():
            btn_avvia.configure(state="normal")
            entry_input.configure(state="normal")
            btn_sfoglia.configure(state="normal")
            if successo:
                log("\n--- Operazione completata con successo ---")
            else:
                log("\n--- Operazione terminata con errori ---")
        root.after(0, _update)

    def avvia():
        input_text = entry_input.get()
        use_cookies = use_cookies_var.get()
        # Pulisci log
        text_log.configure(state="normal")
        text_log.delete("1.0", "end")
        text_log.configure(state="disabled")
        # Disabilita controlli durante l'elaborazione
        btn_avvia.configure(state="disabled")
        entry_input.configure(state="disabled")
        btn_sfoglia.configure(state="disabled")
        # Avvia in thread separato
        t = threading.Thread(target=avvia_processo, args=(input_text, log, on_done, use_cookies), daemon=True)
        t.start()

    btn_avvia.configure(command=avvia)

    # Permetti invio con Enter
    entry_input.bind("<Return>", lambda e: avvia())

    root.mainloop()


if __name__ == "__main__":
    crea_gui()
