import streamlit as st
from openai import OpenAI
from github import Github
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO
import fitz  # PyMuPDF
import re

# --- 1. LOGOWANIE ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔒 Prywatny Asystent")
    pwd = st.text_input("Podaj hasło:", type="password")
    if st.button("Zaloguj"):
        if pwd in st.secrets["passwords"].values():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Błędne hasło!")
    st.stop()

# --- 2. KONFIGURACJA I CACHE ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

if "pdf_page" not in st.session_state: st.session_state.pdf_page = 0
if "last_file" not in st.session_state: st.session_state.last_file = ""

@st.cache_data(show_spinner=False)
def fetch_pdf_cached(path):
    return repo.get_contents(path).decoded_content

@st.cache_data(show_spinner=False)
def render_page_img(pdf_bytes, page_num):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    return pix.tobytes("png")

def get_premium_audio(text, voice):
    """Lektor OpenAI Premium"""
    response = client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000])
    return response.content

# --- 3. PANEL BOCZNY (USTAWIENIA) ---
with st.sidebar:
    st.title("📂 Biblioteka")
    selected_voice = st.selectbox("🎙️ Wybierz głos:", ["nova", "shimmer", "alloy", "onyx"])
    st.markdown("---")
    
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, selected_file, full_text_with_pages = None, "Brak", {}
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Plik:", ["Brak"] + files)
        
        if selected_file != "Brak":
            if st.session_state.last_file != selected_file:
                st.session_state.pdf_page = 0
                st.session_state.last_file = selected_file
            
            path = f"baza_wiedzy/{selected_cat}/{selected_file}"
            current_pdf_bytes = fetch_pdf_cached(path)
            
            # Szybkie czytanie tekstu
            doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
            for i, p in enumerate(doc):
                full_text_with_pages[i] = p.get_text()
            doc.close()

# --- 4. GŁÓWNY EKRAN (UKŁAD) ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("❓ Zadaj pytanie")
    # PRZYWRÓCONE: Wklejanie ze schowka (Ctrl+V)
    pasted_img = st.file_uploader("Wklej obrazek (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="paste_up")
    q = st.text_input("Wpisz pytanie (AI odpowie konkretnie):")

    if st.button("Zapytaj AI") or (pasted_img and not q):
        with st.spinner("Szukam konkretnej odpowiedzi..."):
            context_string = "\n".join([f"[Strona {i}]: {t}" for i, t in full_text_with_pages.items()])
            
            # Prompt wymuszający konkretną odpowiedź
            messages = [
                {"role": "system", "content": "Jesteś precyzyjnym asystentem. Odpowiadaj bardzo krótko (np. 'Odpowiedź A' lub 'B, bo...'). Nie używaj zbędnych słów. Podaj numer strony w formacie [ID:X]."},
                {"role": "user", "content": f"KONTEKST: {context_string[:15000]}\n\nPYTANIE: {q if q else 'Rozwiąż zadanie ze zdjęcia'}"}
            ]
            
            res = client.chat.completions.create(model="gpt-4o-mini", messages=messages).choices[0].message.content
            
            # Logika skoku do strony
            match = re.search(r"\[ID:(\d+)\]", res)
            if match: st.session_state.pdf_page = int(match.group(1))
            
            clean_res = re.sub(r"\[ID:\d+\]", "", res)
            st.success(clean_res)
            
            # OSOBNA IKONA ŹRÓDŁA
            with st.expander("📖 Zobacz treść źródłową"):
                st.write(full_text_with_pages.get(st.session_state.pdf_page, "Nie znaleziono tekstu."))
            
            st.audio(get_premium_audio(clean_res, selected_voice), autoplay=True)

with col2:
    if current_pdf_bytes:
        max_p = len(full_text_with_pages)
        st.subheader(f"📖 Strona {st.session_state.pdf_page + 1} z {max_p}")
        
        # NAWIGACJA + AUTOMATYCZNE STRONICOWANIE
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("⬅️") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            # PRZYCISK AUDIOBOOKA ZE STRONICOWANIEM
            if st.button("▶️ Czytaj i przejdź do następnej"):
                txt = full_text_with_pages.get(st.session_state.pdf_page, "")
                if txt.strip():
                    audio = get_premium_audio(txt, selected_voice)
                    st.audio(audio, autoplay=True)
                    # Automatyczny skok po kliknięciu
                    if st.session_state.pdf_page < max_p - 1:
                        st.session_state.pdf_page += 1
                else: st.warning("Pusta strona.")
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < max_p - 1:
                st.session_state.pdf_page += 1; st.rerun()

        # Wyświetlanie strony PDF jako obraz
        st.image(render_page_img(current_pdf_bytes, st.session_state.pdf_page), use_container_width=True)
        
        # Notatnik pod PDF
        st.markdown("---")
        notes_path = f"baza_wiedzy/{selected_cat}/{selected_file.replace('.pdf', '')}_notatki.txt"
        try: saved_notes = repo.get_contents(notes_path).decoded_content.decode()
        except: saved_notes = ""
        user_notes = st.text_area("📝 Notatki do tej strony:", value=saved_notes, height=100)
        if st.button("💾 Zapisz"):
            try:
                old = repo.get_contents(notes_path)
                repo.update_file(notes_path, "up", user_notes, old.sha)
            except: repo.create_file(notes_path, "cr", user_notes)
            st.success("Zapisano!")
    else:
        st.info("Wybierz plik z biblioteki.")
