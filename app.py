import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO
import fitz  # PyMuPDF
from PIL import Image

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

# --- 3. FUNKCJE Z OPTYMALIZACJĄ (CACHING) ---

@st.cache_data(show_spinner=False)
def fetch_pdf_from_github(path):
    """Pobiera plik raz i trzyma go w szybkiej pamięci cache"""
    file_data = repo.get_contents(path)
    return file_data.decoded_content

@st.cache_data(show_spinner=False)
def render_page_cached(pdf_bytes, page_num):
    """Zapamiętuje wyrenderowane obrazy stron, by nie robić tego dwa razy"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    return pix.tobytes("png")

def get_saved_notes(category, original_file):
    notes_path = f"baza_wiedzy/{category}/{original_file.replace('.pdf', '')}_notatki.txt"
    try:
        return repo.get_contents(notes_path).decoded_content.decode()
    except: return ""

def analyze_content(user_query, image_bytes=None, text_context=None):
    if image_bytes:
        base64_img = base64.b64encode(image_bytes).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [{"type": "text", "text": user_query}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}]}]
        )
    else:
        prompt = f"Źródło: {text_context[:15000]}\n\nPytanie: {user_query}" if text_context else user_query
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

# --- 4. PANEL BOCZNY ---
with st.sidebar:
    st.title("📂 Biblioteka")
    new_cat = st.text_input("Nowa kategoria:")
    if st.button("Utwórz"):
        if new_cat:
            repo.create_file(f"baza_wiedzy/{new_cat}/.keep", "init", "")
            st.rerun()

    st.markdown("---")
    cats = [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    selected_cat = st.selectbox("Wybierz przedmiot:", ["---"] + cats)
    
    library_context, current_pdf_bytes, selected_file = "", None, "Brak"
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik:", ["Brak"] + files)
        
        if selected_file != "Brak":
            # Szybkie pobieranie z cache
            path = f"baza_wiedzy/{selected_cat}/{selected_file}"
            current_pdf_bytes = fetch_pdf_from_github(path)
            
            pdf = PdfReader(BytesIO(current_pdf_bytes))
            library_context = "".join([page.extract_text() for page in pdf.pages])

        st.markdown("---")
        up_pdf = st.file_uploader("Dodaj PDF", type=['pdf'])
        if up_pdf and st.button("Wyślij"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.cache_data.clear() # Czyścimy cache po dodaniu nowego pliku
            st.success("Zapisano!")
            st.rerun()

# --- 5. UKŁAD DWUKOLUMNOWY ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.2])

if "pdf_page" not in st.session_state:
    st.session_state.pdf_page = 0

with col1:
    st.subheader("❓ Zadaj pytanie AI")
    pasted_file = st.file_uploader("Zrzut ekranu (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="main_uploader")
    q = st.text_input("Twoje pytanie:")

    if st.button("Zapytaj") or pasted_file:
        with st.spinner("Myślę..."):
            res = analyze_content(q if q else "Rozwiąż to.", pasted_file.getvalue() if pasted_file else None, library_context)
            st.info(res)
            try:
                tts = gTTS(text=res, lang='pl')
                tts.save("v.mp3")
                st.audio("v.mp3")
            except: pass

with col2:
    if current_pdf_bytes:
        st.subheader(f"📖 Podgląd: {selected_file}")
        
        # Nawigacja
        doc_temp = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        max_p = len(doc_temp)
        doc_temp.close()

        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("⬅️ Poprzednia") and st.session_state.pdf_page > 0:
                st.session_state.pdf_page -= 1
                st.rerun()
        with p2:
            st.session_state.pdf_page = st.slider("Strona:", 0, max_p-1, st.session_state.pdf_page)
        with p3:
            if st.button("Następna ➡️") and st.session_state.pdf_page < max_p - 1:
                st.session_state.pdf_page += 1
                st.rerun()

        # Wyświetlanie zoptymalizowane
        img_bytes = render_page_cached(current_pdf_bytes, st.session_state.pdf_page)
        st.image(img_bytes, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📝 Twoje notatki")
        saved_text = get_saved_notes(selected_cat, selected_file)
        user_notes = st.text_area("Twoje uwagi:", value=saved_text, height=150)
        
        if st.button("Zapisz notatki"):
            notes_path = f"baza_wiedzy/{selected_cat}/{selected_file.replace('.pdf', '')}_notatki.txt"
            try:
                old = repo.get_contents(notes_path)
                repo.update_file(notes_path, "update", user_notes, old.sha)
            except:
                repo.create_file(notes_path, "create", user_notes)
            st.success("Zapisano!")
    else:
        st.info("Wybierz plik z biblioteki.")
