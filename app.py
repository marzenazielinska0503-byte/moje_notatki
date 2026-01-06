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

# --- 2. KONFIGURACJA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

# Inicjalizacja stanów
if "pdf_page" not in st.session_state: st.session_state.pdf_page = 0
if "highlight_text" not in st.session_state: st.session_state.highlight_text = ""

# --- 3. FUNKCJE PREMIUM ---

def generate_premium_audio(text, voice_name):
    """Generuje dźwięk najwyższej jakości OpenAI TTS"""
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_name,
            input=text[:4000] # Bezpieczny limit znaków dla strony
        )
        return response.content
    except Exception as e:
        st.error(f"Błąd lektora: {e}")
        return None

@st.cache_data(show_spinner=False)
def fetch_pdf_from_github(path):
    return repo.get_contents(path).decoded_content

def render_page_with_marker(pdf_bytes, page_num, search_text=""):
    """Renderuje stronę i nakłada marker"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_num)
    if search_text:
        text_instances = page.search_for(search_text)
        for inst in text_instances:
            page.add_rect_annot(inst).set_colors(stroke=(1, 0, 0)) 
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes

# --- 4. PANEL BOCZNY ---
with st.sidebar:
    st.title("📂 Biblioteka")
    
    st.subheader("🎙️ Wybierz Lektora")
    selected_voice = st.selectbox("Głos:", ["nova", "shimmer", "alloy", "onyx", "fable"], help="Nova to głos kobiecy, Onyx to męski.")
    
    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    full_text, current_pdf_bytes, selected_file = "", None, "Brak"
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Plik PDF:", ["Brak"] + files)
        
        if selected_file != "Brak":
            current_pdf_bytes = fetch_pdf_from_github(f"baza_wiedzy/{selected_cat}/{selected_file}")
            # Przygotowanie tekstu dla AI z podziałem na strony
            doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
            full_text = "".join([f"\n[ID:{i}]\n{p.get_text()}" for i, p in enumerate(doc)])
            doc.close()

# --- 5. GŁÓWNY EKRAN (DWIE KOLUMNY) ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("❓ Zadaj pytanie AI")
    q = st.text_input("Wpisz pytanie (AI samo otworzy PDF na właściwej stronie):")

    if st.button("Zapytaj") or q:
        with st.spinner("Szukam odpowiedzi w Twoich notatkach..."):
            # AI zwraca odpowiedź i ID strony
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Odpowiadaj na podstawie notatek. Na końcu dodaj [ID:X] gdzie X to strona."},
                          {"role": "user", "content": f"NOTATKI: {full_text[:15000]}\n\nPYTANIE: {q}"}]
            ).choices[0].message.content
            
            # Automatyczny skok do strony źródłowej
            match = re.search(r"\[ID:(\d+)\]", res)
            if match: 
                st.session_state.pdf_page = int(match.group(1))
            
            clean_res = re.sub(r"\[ID:\d+\]", "", res)
            st.info(f"📍 Źródło: Strona {st.session_state.pdf_page + 1}\n\n{clean_res}")
            
            # Głos Premium dla odpowiedzi AI
            audio_ans = generate_premium_audio(clean_res, selected_voice)
            if audio_ans: st.audio(audio_ans, autoplay=True)

with col2:
    if current_pdf_bytes:
        doc_temp = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        max_p = len(doc_temp)
        
        st.subheader(f"📖 Podgląd: Strona {st.session_state.pdf_page + 1}")
        
        # 1. NAJPIERW WYŚWIETLAMY OBRAZ (Sync)
        img = render_page_with_marker(current_pdf_bytes, st.session_state.pdf_page)
        st.image(img, use_container_width=True)
        
        # 2. PANEL STEROWANIA AUDIOBOOKIEM
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️ Poprzednia"): 
                if st.session_state.pdf_page > 0:
                    st.session_state.pdf_page -= 1
                    st.rerun()
        with c2:
            # PRZYCISK CZYTANIA - czyta to co widoczne
            if st.button("▶️ Czytaj tę stronę"):
                txt = doc_temp[st.session_state.pdf_page].get_text()
                if txt.strip():
                    with st.spinner("Lektor czyta bieżącą stronę..."):
                        audio_p = generate_premium_audio(txt, selected_voice)
                        if audio_p: st.audio(audio_p, autoplay=True)
                else:
                    st.warning("Brak tekstu na tej stronie.")
        with c3:
            if st.button("Następna ➡️"):
                if st.session_state.pdf_page < max_p - 1:
                    st.session_state.pdf_page += 1
                    st.rerun()
        
        doc_temp.close()
        
        # 3. NOTATNIK
        st.markdown("---")
        notes_path = f"baza_wiedzy/{selected_cat}/{selected_file.replace('.pdf', '')}_notatki.txt"
        try: saved_notes = repo.get_contents(notes_path).decoded_content.decode()
        except: saved_notes = ""
        user_notes = st.text_area("📝 Notatki do tej strony:", value=saved_notes, height=150)
        if st.button("💾 Zapisz notatki"):
            try:
                old = repo.get_contents(notes_path)
                repo.update_file(notes_path, "update", user_notes, old.sha)
            except: repo.create_file(notes_path, "create", user_notes)
            st.success("Notatki zapisane!")
    else:
        st.info("Wybierz przedmiot i plik z biblioteki.")
