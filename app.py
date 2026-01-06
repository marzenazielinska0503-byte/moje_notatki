import streamlit as st
from openai import OpenAI
from github import Github
import os
import base64
import fitz  # PyMuPDF
import re
import tempfile
import json

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

# --- 2. KONFIGURACJA I TRWAŁA HISTORIA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

def save_history_to_github(history):
    path = "ustawienia/historia_czatu.json"
    content = json.dumps(history, ensure_ascii=False, indent=2)
    try:
        old_file = repo.get_contents(path)
        repo.update_file(path, "Update chat history", content, old_file.sha)
    except:
        repo.create_file(path, "Create chat history", content)

def load_history_from_github():
    try:
        content = repo.get_contents("ustawienia/historia_czatu.json").decoded_content
        return json.loads(content)
    except:
        return []

# Inicjalizacja stanów
if "messages" not in st.session_state:
    st.session_state.messages = load_history_from_github()
if "pdf_page" not in st.session_state: st.session_state.pdf_page = 0
if "last_file" not in st.session_state: st.session_state.last_file = ""

@st.cache_data(show_spinner=False)
def fetch_pdf_bytes(path):
    return repo.get_contents(path).decoded_content

@st.cache_data(show_spinner=False)
def get_pdf_text_map(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_map = {i: page.get_text().strip() for i, page in enumerate(doc)}
    doc.close()
    return text_map

def get_premium_audio(text, voice, speed):
    try:
        res = client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000], speed=speed)
        return res.content
    except: return None

# --- 3. PANEL BOCZNY (HISTORIA I USTAWIENIA) ---
with st.sidebar:
    st.title("📂 Zarządzanie")
    
    st.subheader("📜 Historia (ostatnie 10)")
    for m in reversed(st.session_state.messages[-10:]):
        if m["role"] == "user":
            st.caption(f"❓ {m['content'][:40]}...")

    if st.button("🗑️ Wyczyść historię"):
        st.session_state.messages = []
        save_history_to_github([])
        st.rerun()

    st.markdown("---")
    st.subheader("🎙️ Ustawienia głosu")
    selected_voice = st.selectbox("Lektor:", ["nova", "shimmer", "alloy", "onyx"])
    voice_speed = st.slider("Szybkość:", 0.5, 2.0, 1.0, 0.1)
    
    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_file_cat = st.selectbox("Otwórz przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, selected_file, text_map = None, "Brak", {}
    if selected_file_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_file_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik:", ["Brak"] + files)
        if selected_file != "Brak":
            current_pdf_bytes = fetch_pdf_bytes(f"baza_wiedzy/{selected_file_cat}/{selected_file}")
            text_map = get_pdf_text_map(current_pdf_bytes)

    st.markdown("---")
    up_file = st.file_uploader("Dodaj nowy PDF do bazy", type=['pdf'])
    if up_file and st.button("Wyślij plik"):
        repo.create_file(f"baza_wiedzy/{selected_file_cat}/{up_file.name}", "Add doc", up_file.getvalue())
        st.success("Dodano!")

# --- 4. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("💬 Czat edukacyjny")
    
    # Okno czatu
    chat_box = st.container(height=450)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "source_text" in msg and msg["source_text"]:
                    with st.expander("📖 Zobacz tekst źródłowy"):
                        st.write(msg["source_text"])

    st.markdown("---")
    # Wejścia danych
    pasted_img = st.file_uploader("Wklej obrazek (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
    audio_input = st.audio_input("🎤 Zadaj pytanie głosem:")
    text_q = st.chat_input("Wpisz pytanie tutaj...")

    if text_q or audio_input or pasted_img:
        with st.spinner("Przetwarzanie..."):
            # Obsługa głosu
            voice_text = ""
            if audio_input:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio_input.getvalue())
                    f_path = f.name
                with open(f_path, "rb") as af:
                    voice_text = client.audio.transcriptions.create(model="whisper-1", file=af).text
                os.remove(f_path)

            final_q = text_q if text_q else (voice_text if voice_text else "Rozwiąż zadanie.")
            
            # Kontekst i analiza
            context = "\n".join([f"[Strona {i}]: {t}" for i, t in text_map.items() if t])
            content_list = [{"type": "text", "text": f"NOTATKI: {context[:12000]}\n\nZADANIE: {final_q}"}]
            
            if pasted_img:
                b64 = base64.b64encode(pasted_img.getvalue()).decode()
                content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

            res_raw = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Jesteś ekspertem. Odpowiadaj BARDZO konkretnie (tylko poprawna litera lub krótkie wyjaśnienie). IGNORUJ zaznaczenia kolorami na obrazkach. Na końcu dodaj [ID:X]."},
                    {"role": "user", "content": content_list}
                ]
            ).choices[0].message.content

            # Skok do strony i zapis
            m = re.search(r"\[ID:(\d+)\]", res_raw)
            source_p = int(m.group(1)) if m else st.session_state.pdf_page
            if m: st.session_state.pdf_page = source_p
            
            clean_res = re.sub(r"\[ID:\d+\]", "", res_raw).strip()
            
            # Zapis do sesji i GitHub
            st.session_state.messages.append({"role": "user", "content": final_q})
            st.session_state.messages.append({
                "role": "assistant", 
                "content": clean_res,
                "source_text": text_map.get(source_p, "Brak tekstu na tej stronie.")
            })
            save_history_to_github(st.session_state.messages)
            
            # Lektor
            audio = get_premium_audio(clean_res, selected_voice, voice_speed)
            if audio: st.audio(audio, autoplay=True)
            st.rerun()

with col2:
    if current_pdf_bytes:
        st.subheader(f"📖 Podgląd: Strona {st.session_state.pdf_page + 1}")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            if st.button("▶️ Czytaj"):
                t = text_map.get(st.session_state.pdf_page, "")
                if t.strip():
                    st.audio(get_premium_audio(t, selected_voice, voice_speed), autoplay=True)
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < len(text_map) - 1:
                st.session_state.pdf_page += 1; st.rerun()

        doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        pix = doc[st.session_state.pdf_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(pix.tobytes("png"), use_container_width=True)
        doc.close()
    else:
        st.info("Wybierz plik po lewej stronie.")
