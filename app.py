import streamlit as st
from openai import OpenAI
from github import Github
import os
import base64
import fitz  # PyMuPDF
import re
import tempfile
import json
import requests # Stabilne pobieranie

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

# --- 2. KONFIGURACJA I HISTORIA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

def save_history_to_github(history):
    path = "ustawienia/historia_czatu.json"
    content = json.dumps(history, ensure_ascii=False, indent=2)
    try:
        old_file = repo.get_contents(path)
        repo.update_file(path, "Update history", content, old_file.sha)
    except:
        repo.create_file(path, "Create history", content)

def load_history_from_github():
    try:
        content = repo.get_contents("ustawienia/historia_czatu.json").decoded_content
        return json.loads(content)
    except: return []

if "messages" not in st.session_state:
    st.session_state.messages = load_history_from_github()
if "pdf_page" not in st.session_state: st.session_state.pdf_page = 0
if "last_file" not in st.session_state: st.session_state.last_file = ""

@st.cache_data(show_spinner=False)
def fetch_pdf_bytes(path):
    """Pobiera PDF bez błędów AssertionError"""
    try:
        file_info = repo.get_contents(path)
        return requests.get(file_info.download_url).content
    except Exception as e:
        st.error(f"Błąd pobierania: {e}")
        return None

@st.cache_data(show_spinner=False)
def get_pdf_text_map(pdf_bytes):
    if not pdf_bytes: return {}
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_map = {i: page.get_text().strip() for i, page in enumerate(doc)}
    doc.close()
    return text_map

def get_premium_audio(text, voice, speed):
    try:
        res = client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000], speed=speed)
        return res.content
    except: return None

# --- 3. PANEL BOCZNY ---
with st.sidebar:
    st.title("📂 Zarządzanie")
    
    st.subheader("🆕 Nowy przedmiot")
    new_sub = st.text_input("Nazwa (np. Psychologia):")
    if st.button("Dodaj folder"):
        if new_sub:
            repo.create_file(f"baza_wiedzy/{new_sub}/.keep", "init", "")
            st.success("Dodano!")
            st.rerun()
    st.markdown("---")

    st.subheader("📜 Archiwum nauki")
    if st.session_state.messages:
        for i in range(len(st.session_state.messages)-1, 0, -1):
            msg = st.session_state.messages[i]
            if msg["role"] == "assistant":
                user_q = st.session_state.messages[i-1]
                with st.expander(f"💬 {user_q['content'][:25]}..."):
                    st.write(f"**P:** {user_msg['content']}")
                    st.write(f"**O:** {msg['content']}")

    st.markdown("---")
    st.subheader("🎙️ Ustawienia głosu")
    v_voice = st.selectbox("Lektor:", ["nova", "shimmer", "alloy", "onyx"])
    v_speed = st.slider("Szybkość:", 0.5, 2.0, 1.0, 0.1)
    
    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Wybierz przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, text_map = None, {}
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik:", ["Brak"] + files)
        if selected_file != "Brak":
            current_pdf_bytes = fetch_pdf_bytes(f"baza_wiedzy/{selected_cat}/{selected_file}")
            text_map = get_pdf_text_map(current_pdf_bytes)
            
        up_new = st.file_uploader("Dodaj PDF do kategorii", type=['pdf'])
        if up_new and st.button("Wyślij plik"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_new.name}", "add", up_new.getvalue())
            st.success("Zapisano!")

# --- 4. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("💬 Czat edukacyjny")
    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "source_text" in msg and msg["source_text"]:
                    with st.expander("📖 Zobacz tekst źródłowy"):
                        st.write(msg["source_text"])

    pasted_img = st.file_uploader("Wklej obraz (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
    audio_q = st.audio_input("🎤 Pytanie głosem:")
    text_q = st.chat_input("Zadaj pytanie...")
    
    if st.button("🚀 Wyślij do AI") or text_q:
        with st.spinner("Analizuję..."):
            v_text = ""
            if audio_q:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio_q.getvalue()); f_path = f.name
                v_text = client.audio.transcriptions.create(model="whisper-1", file=open(f_path, "rb")).text
            
            final_q = text_q if text_q else (v_text if v_text else "Rozwiąż zadanie ze zdjęcia.")
            ctx_text = "\n".join([f"[ID:{i}]: {t}" for i, t in text_map.items() if t])
            
            # --- POPRAWIONY SYSTEM PROMPT (Krótka odpowiedź + Opis) ---
            system_instruction = (
                "Jesteś ekspertem. Przy pytaniach testowych NA SAMEJ GÓRZE podaj krótką odpowiedź (np. 'Odpowiedź: A'). "
                "Poniżej dodaj nagłówek 'Wyjaśnienie:' i opisz dlaczego ta odpowiedź jest poprawna. "
                "IGNORUJ kolory zaznaczeń na zdjęciach. Zawsze na końcu dodaj [ID:X]."
            )

            msgs = [{"role": "system", "content": system_instruction},
                    {"role": "user", "content": [{"type": "text", "text": f"NOTATKI: {ctx_text[:12000]}\n\nPYTANIE: {final_q}"}]}]
            
            if pasted_img:
                b64 = base64.b64encode(pasted_img.getvalue()).decode()
                msgs[1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

            res = client.chat.completions.create(model="gpt-4o-mini", messages=msgs).choices[0].message.content
            m = re.search(r"\[ID:(\d+)\]", res)
            source_p = int(m.group(1)) if m else st.session_state.pdf_page
            if m: st.session_state.pdf_page = source_p
            
            clean_res = re.sub(r"\[ID:\d+\]", "", res).strip()
            st.session_state.messages.append({"role": "user", "content": final_q})
            st.session_state.messages.append({"role": "assistant", "content": clean_res, "source_text": text_map.get(source_p, "Analiza wizualna strony.")})
            save_history_to_github(st.session_state.messages)
            
            audio_ans = get_premium_audio(clean_res, v_voice, v_speed)
            if audio_ans: st.audio(audio_ans, autoplay=True)
            st.rerun()

with col2:
    if current_pdf_bytes:
        st.subheader(f"📖 Strona {st.session_state.pdf_page + 1}")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            if st.button("▶️ Czytaj"):
                st.audio(get_premium_audio(text_map.get(st.session_state.pdf_page, ""), v_voice, v_speed), autoplay=True)
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < len(text_map) - 1:
                st.session_state.pdf_page += 1; st.rerun()
        
        doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        pix = doc[st.session_state.pdf_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(pix.tobytes("png"), use_container_width=True)
        doc.close()
