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

# Inicjalizacja
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

# --- 3. PANEL BOCZNY (HISTORIA I ZARZĄDZANIE) ---
with st.sidebar:
    st.title("📂 Biblioteka i Historia")
    
    # TRWAŁA HISTORIA
    st.subheader("📜 Historia Twoich pytań")
    if st.session_state.messages:
        for m in reversed(st.session_state.messages):
            if m["role"] == "user":
                with st.expander(f"❓ {m['content'][:30]}..."):
                    st.write(m['content'])
    
    if st.button("🗑️ Wyczyść historię na GitHubie"):
        st.session_state.messages = []
        save_history_to_github([])
        st.rerun()

    st.markdown("---")
    st.subheader("🎙️ Ustawienia Lektora")
    v_voice = st.selectbox("Głos:", ["nova", "shimmer", "alloy", "onyx"])
    v_speed = st.slider("Szybkość czytania:", 0.5, 2.0, 1.0, 0.1)
    
    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, selected_file, text_map = None, "Brak", {}
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik:", ["Brak"] + files)
        if selected_file != "Brak":
            current_pdf_bytes = fetch_pdf_bytes(f"baza_wiedzy/{selected_cat}/{selected_file}")
            text_map = get_pdf_text_map(current_pdf_bytes)

    # DODAWANIE DOKUMENTÓW
    st.markdown("---")
    up_new = st.file_uploader("Dodaj nowy PDF do tej kategorii", type=['pdf'])
    if up_new and st.button("Wyślij do bazy"):
        repo.create_file(f"baza_wiedzy/{selected_cat}/{up_new.name}", "Add doc", up_new.getvalue())
        st.success("Plik zapisany!")

# --- 4. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("💬 Czat (Pytanie po pytaniu)")
    
    # Wyświetlanie czatu
    chat_display = st.container(height=400)
    with chat_display:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "source_info" in msg and msg["source_info"]:
                    with st.expander("📖 Zobacz tekst źródłowy"):
                        st.write(msg["source_info"])

    st.markdown("---")
    # FORMULARZ ZAPYTANIA (Zapobiega automatycznym pętlom)
    pasted_img = st.file_uploader("Wklej obrazek (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="img_up")
    audio_q = st.audio_input("🎤 Nagraj pytanie:")
    text_q = st.chat_input("Napisz pytanie i naciśnij Enter...")
    
    # Przycisk wysyłania dla głosu i obrazka
    process_btn = st.button("🚀 Wyślij zapytanie do AI")

    if text_q or process_btn:
        if not text_q and not audio_q and not pasted_img:
            st.warning("Najpierw podaj pytanie, nagraj głos lub wklej obrazek!")
        else:
            with st.spinner("Analiza w toku..."):
                # Rozpoznawanie mowy
                v_text = ""
                if audio_q:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                        f.write(audio_q.getvalue()); f_path = f.name
                    with open(f_path, "rb") as af:
                        v_text = client.audio.transcriptions.create(model="whisper-1", file=af).text
                    os.remove(f_path)

                final_q = text_q if text_q else (v_text if v_text else "Rozwiąż zadanie konkretnie.")
                
                # Budowa kontekstu
                ctx = "\n".join([f"[STRONA {i}]: {t}" for i, t in text_map.items() if t])
                msgs = [{"role": "system", "content": "Jesteś precyzyjnym asystentem. Odpowiadaj BARDZO konkretnie (tylko litera odpowiedzi lub 1 zdanie). IGNORUJ zaznaczenia kolorami na zdjęciach. Zawsze dodaj na końcu [ID:X]."},
                        {"role": "user", "content": [{"type": "text", "text": f"NOTATKI: {ctx[:12000]}\n\nPYTANIE: {final_q}"}]}]
                
                if pasted_img:
                    b64 = base64.b64encode(pasted_img.getvalue()).decode()
                    msgs[1]["content"].append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

                res_raw = client.chat.completions.create(model="gpt-4o-mini", messages=msgs).choices[0].message.content
                
                # Nawigacja i czyszczenie
                m = re.search(r"\[ID:(\d+)\]", res_raw)
                source_p = int(m.group(1)) if m else st.session_state.pdf_page
                if m: st.session_state.pdf_page = source_p
                
                clean_res = re.sub(r"\[ID:\d+\]", "", res_raw).strip()
                
                # Zapis historii
                st.session_state.messages.append({"role": "user", "content": final_q})
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": clean_res,
                    "source_info": text_map.get(source_p, "To jest skan PDF – brak tekstu do wyświetlenia (AI przeanalizowało stronę wizualnie).")
                })
                save_history_to_github(st.session_state.messages)
                
                # Lektor Premium
                audio_ans = get_premium_audio(clean_res, v_voice, v_speed)
                if audio_ans: st.audio(audio_ans, autoplay=True)
                st.rerun()

with col2:
    if current_pdf_bytes:
        st.subheader(f"📖 Podgląd: Strona {st.session_state.pdf_page + 1}")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            if st.button("▶️ Czytaj stronę"):
                t = text_map.get(st.session_state.pdf_page, "")
                if t.strip():
                    st.audio(get_premium_audio(t, v_voice, v_speed), autoplay=True)
                else: st.warning("To jest skan – brak tekstu do czytania.")
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < len(text_map) - 1:
                st.session_state.pdf_page += 1; st.rerun()

        doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        pix = doc[st.session_state.pdf_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(pix.tobytes("png"), use_container_width=True)
        doc.close()
