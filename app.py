import streamlit as st
from openai import OpenAI
from github import Github
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO
import fitz  # PyMuPDF
import re
import tempfile

# --- 1. LOGOWANIE ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔒 Prywatny Asystent")
    pwd = st.text_input("Hasło:", type="password")
    if st.button("Zaloguj"):
        if pwd in st.secrets["passwords"].values():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Błędne hasło!")
    st.stop()

# --- 2. KONFIGURACJA I SZYBKI CACHE ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

if "pdf_page" not in st.session_state: st.session_state.pdf_page = 0
if "last_file" not in st.session_state: st.session_state.last_file = ""

@st.cache_data(show_spinner=False)
def fetch_pdf_bytes(path):
    """Pobiera PDF z GitHuba tylko raz"""
    return repo.get_contents(path).decoded_content

@st.cache_data(show_spinner=False)
def get_pdf_text_map(pdf_bytes):
    """Błyskawicznie mapuje tekst na strony"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_map = {i: page.get_text() for i, page in enumerate(doc)}
    doc.close()
    return text_map

def get_premium_audio(text, voice):
    """Głos OpenAI Premium"""
    try:
        res = client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000])
        return res.content
    except: return None

# --- 3. PANEL BOCZNY ---
with st.sidebar:
    st.title("📂 Biblioteka")
    selected_voice = st.selectbox("🎙️ Lektor:", ["nova", "shimmer", "alloy", "onyx"])
    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, selected_file, text_map = None, "Brak", {}
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik:", ["Brak"] + files)
        
        if selected_file != "Brak":
            if st.session_state.last_file != selected_file:
                st.session_state.pdf_page = 0
                st.session_state.last_file = selected_file
            
            current_pdf_bytes = fetch_pdf_bytes(f"baza_wiedzy/{selected_cat}/{selected_file}")
            text_map = get_pdf_text_map(current_pdf_bytes)

# --- 4. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("❓ Zadaj pytanie")
    # Zrzut ekranu (Ctrl+V)
    pasted_img = st.file_uploader("Wklej obrazek (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="p_up")
    
    # Mikrofon
    audio_data = st.audio_input("🎤 Zadaj pytanie głosem:")
    voice_q = ""
    if audio_data:
        with st.spinner("Słucham..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_data.getvalue())
                f_path = f.name
            with open(f_path, "rb") as af:
                voice_q = client.audio.transcriptions.create(model="whisper-1", file=af).text
            os.remove(f_path)
            st.caption(f"Usłyszano: {voice_q}")

    text_q = st.text_input("Lub wpisz tutaj:")
    
    final_q = text_q if text_q else voice_q
    if not final_q and pasted_img: final_q = "Rozwiąż to zadanie i podaj tylko konkretną odpowiedź."

    if st.button("Zapytaj AI") or (pasted_img and not text_q and not voice_q):
        with st.spinner("Szybka analiza..."):
            context = "\n".join([f"[Strona {i}]: {t}" for i, t in text_map.items()])
            
            # Budowa wiadomości (Poprawione Vision)
            content = [{"type": "text", "text": f"KONTEKST: {context[:12000]}\n\nPYTANIE: {final_q}"}]
            if pasted_img:
                b64 = base64.b64encode(pasted_img.getvalue()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Bądź ultra-konkretny. Podaj tylko odpowiedź (np. 'A' lub 'Tak'). Na końcu dodaj [ID:X]"},
                    {"role": "user", "content": content}
                ]
            ).choices[0].message.content

            # Skok i wyświetlanie
            m = re.search(r"\[ID:(\d+)\]", res)
            if m: st.session_state.pdf_page = int(m.group(1))
            
            clean_res = re.sub(r"\[ID:\d+\]", "", res)
            st.success(clean_res)
            
            with st.expander("📖 Źródło informacji"):
                st.write(text_map.get(st.session_state.pdf_page, "Brak tekstu."))
            
            audio = get_premium_audio(clean_res, selected_voice)
            if audio: st.audio(audio, autoplay=True)

with col2:
    if current_pdf_bytes:
        max_p = len(text_map)
        st.subheader(f"📖 Podgląd: Strona {st.session_state.pdf_page + 1}")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            if st.button("▶️ Czytaj i następna"):
                t = text_map.get(st.session_state.pdf_page, "")
                if t.strip():
                    st.audio(get_premium_audio(t, selected_voice), autoplay=True)
                    if st.session_state.pdf_page < max_p - 1: st.session_state.pdf_page += 1
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < max_p - 1:
                st.session_state.pdf_page += 1; st.rerun()

        # Render obrazu strony
        doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        pix = doc[st.session_state.pdf_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(pix.tobytes("png"), use_container_width=True)
        doc.close()
    else:
        st.info("Wybierz dokument z biblioteki.")
