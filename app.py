import streamlit as st
from openai import OpenAI
from github import Github
import os
import base64
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

# --- 2. KONFIGURACJA, CACHE I HISTORIA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

# Inicjalizacja historii i stanów
if "messages" not in st.session_state:
    st.session_state.messages = []
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

def get_premium_audio(text, voice):
    try:
        res = client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000])
        return res.content
    except: return None

# --- 3. PANEL BOCZNY ---
with st.sidebar:
    st.title("📂 Biblioteka")
    selected_voice = st.selectbox("🎙️ Lektor:", ["nova", "shimmer", "alloy", "onyx"])
    
    if st.button("🗑️ Wyczyść historię pytań"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    current_pdf_bytes, selected_file, text_map = None, "Brak", {}
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Plik:", ["Brak"] + files)
        
        if selected_file != "Brak":
            if st.session_state.last_file != selected_file:
                st.session_state.pdf_page = 0
                st.session_state.last_file = selected_file
            
            current_pdf_bytes = fetch_pdf_bytes(f"baza_wiedzy/{selected_cat}/{selected_file}")
            text_map = get_pdf_text_map(current_pdf_bytes)

# --- 4. GŁÓWNY UKŁAD ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("💬 Rozmowa z AI")
    
    # Wyświetlanie historii
    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "image" in msg:
                    st.image(msg["image"], width=200)
                if "source" in msg and msg["source"]:
                    with st.expander("📖 Źródło z notatek"):
                        st.write(msg["source"])

    st.markdown("---")
    st.write("➕ **Zadaj nowe pytanie:**")
    
    # Formy wejściowe
    pasted_img = st.file_uploader("Wklej obrazek (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="chat_up")
    audio_data = st.audio_input("🎤 Nagraj pytanie:")
    text_q = st.text_input("Lub wpisz pytanie:")

    # Przetwarzanie
    if st.button("Wyślij do AI"):
        voice_text = ""
        if audio_data:
            with st.spinner("Rozpoznawanie głosu..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    f.write(audio_data.getvalue())
                    f_path = f.name
                with open(f_path, "rb") as af:
                    voice_text = client.audio.transcriptions.create(model="whisper-1", file=af).text
                os.remove(f_path)

        final_q = text_q if text_q else voice_text
        if not final_q and pasted_img: final_q = "Przeanalizuj to zdjęcie."
        
        if final_q or pasted_img:
            with st.spinner("AI myśli..."):
                context = "\n".join([f"[ID:{i}]: {t}" for i, t in text_map.items() if t])
                
                content_list = [{"type": "text", "text": f"NOTATKI: {context[:12000]}\n\nZADANIE: {final_q}"}]
                if pasted_img:
                    b64 = base64.b64encode(pasted_img.getvalue()).decode()
                    content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

                res_raw = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Odpowiadaj konkretnie i krótko. Na końcu dodaj [ID:X] strony."},
                        {"role": "user", "content": content_list}
                    ]
                ).choices[0].message.content

                # Ekstrakcja strony i czyszczenie
                m = re.search(r"\[ID:(\d+)\]", res_raw)
                source_p = int(m.group(1)) if m else st.session_state.pdf_page
                if m: st.session_state.pdf_page = source_p
                
                clean_res = re.sub(r"\[ID:\d+\]", "", res_raw).strip()
                
                # Zapis do historii
                new_msg = {"role": "user", "content": final_q if final_q else "Obrazek"}
                if pasted_img: new_msg["image"] = pasted_img.getvalue()
                st.session_state.messages.append(new_msg)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": clean_res,
                    "source": text_map.get(source_p, "Brak tekstu na tej stronie.")
                })
                
                # Lektor dla nowej odpowiedzi
                audio = get_premium_audio(clean_res, selected_voice)
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
            if st.button("▶️ Czytaj stronę"):
                t = text_map.get(st.session_state.pdf_page, "")
                if t.strip():
                    st.audio(get_premium_audio(t, selected_voice), autoplay=True)
        with c3:
            if st.button("➡️") and st.session_state.pdf_page < len(text_map) - 1:
                st.session_state.pdf_page += 1; st.rerun()

        doc = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        pix = doc[st.session_state.pdf_page].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        st.image(pix.tobytes("png"), use_container_width=True)
        doc.close()
    else:
        st.info("Wybierz plik z biblioteki.")
