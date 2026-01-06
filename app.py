import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
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
if "last_file" not in st.session_state: st.session_state.last_file = ""

# --- 3. FUNKCJE Z OPTYMALIZACJĄ ---

@st.cache_data(show_spinner=False)
def fetch_pdf_from_github(path):
    return repo.get_contents(path).decoded_content

def render_page_with_marker(pdf_bytes, page_num, search_text=""):
    """Renderuje stronę i zaznacza tekst"""
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

def get_page_text(pdf_bytes, page_num):
    """Wyciąga tekst z konkretnej strony"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = doc[page_num].get_text()
    doc.close()
    return text

def get_full_context_with_pages(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    context = ""
    for i in range(len(doc)):
        context += f"\n--- STRONA {i} ---\n{doc[i].get_text()}"
    doc.close()
    return context

def analyze_and_locate(user_query, text_context):
    """AI znajduje odpowiedź, stronę i cytat"""
    system_prompt = (
        "Odpowiadaj na podstawie notatek. Na końcu odpowiedzi ZAWSZE podaj źródło: "
        "STRONA:X | CYTAT: 'fragment'. X to numer strony (od 0)."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": f"NOTATKI:\n{text_context[:15000]}\n\nPYTANIE: {user_query}"}]
    )
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
    selected_cat = st.selectbox("Przedmiot:", ["---"] + cats)
    
    full_library_text, current_pdf_bytes, selected_file = "", None, "Brak"
    
    if selected_cat != "---":
        files = [c.name for c in repo.get_contents(f"baza_wiedzy/{selected_cat}") if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Plik:", ["Brak"] + files)
        
        if selected_file != "Brak":
            if st.session_state.last_file != selected_file:
                st.session_state.pdf_page = 0
                st.session_state.last_file = selected_file
            
            current_pdf_bytes = fetch_pdf_from_github(f"baza_wiedzy/{selected_cat}/{selected_file}")
            full_library_text = get_full_context_with_pages(current_pdf_bytes)

        st.markdown("---")
        up_pdf = st.file_uploader("Dodaj PDF", type=['pdf'])
        if up_pdf and st.button("Wyślij"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.cache_data.clear()
            st.rerun()

# --- 5. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("❓ Pytanie do AI")
    pasted_img = st.file_uploader("Zrzut (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
    q = st.text_input("Twoje pytanie (AI samo znajdzie stronę):")

    if st.button("Zapytaj AI") or (pasted_img and q):
        with st.spinner("Szukam odpowiedzi i strony..."):
            raw_res = analyze_and_locate(q if q else "Przeanalizuj to", full_library_text)
            
            # Autostronicowanie na podstawie odpowiedzi AI
            try:
                page_match = re.search(r"STRONA:(\d+)", raw_res)
                quote_match = re.search(r"CYTAT: '(.*?)'", raw_res)
                if page_match: st.session_state.pdf_page = int(page_match.group(1))
                if quote_match: st.session_state.highlight_text = quote_match.group(1)
                
                clean_res = re.sub(r"STRONA:\d+ \| CYTAT: '.*?'", "", raw_res)
                st.info(f"📍 Źródło: Strona {st.session_state.pdf_page + 1}\n\n{clean_res}")
                
                gTTS(text=clean_res, lang='pl').save("ans.mp3")
                st.audio("ans.mp3", autoplay=True)
            except: st.info(raw_res)

with col2:
    if current_pdf_bytes:
        doc_temp = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        max_p = len(doc_temp)
        doc_temp.close()

        st.subheader(f"📖 Podgląd: Strona {st.session_state.pdf_page + 1} z {max_p}")
        
        # NAWIGACJA GŁOSOWA I STRONICOWANIE
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("⬅️ Poprzednia"): st.session_state.pdf_page -= 1; st.rerun()
        with c2:
            # NOWOŚĆ: TRYB AUDIOBOOKA (Auto-stronicowanie)
            if st.button("▶️ Czytaj i przejdź dalej"):
                txt = get_page_text(current_pdf_bytes, st.session_state.pdf_page)
                if txt.strip():
                    with st.spinner("Czytam stronę..."):
                        gTTS(text=txt, lang='pl').save("audiobook.mp3")
                        st.audio("audiobook.mp3", autoplay=True)
                        # Przełączamy na następną stronę, aby widok się zmienił
                        if st.session_state.pdf_page < max_p - 1:
                            st.session_state.pdf_page += 1
                else:
                    st.warning("Strona bez tekstu, skaczę dalej.")
                    if st.session_state.pdf_page < max_p - 1:
                        st.session_state.pdf_page += 1
                        st.rerun()
        with c3:
            if st.button("Następna ➡️"): st.session_state.pdf_page += 1; st.rerun()

        # Wyświetlanie strony z Markerem
        img = render_page_with_marker(current_pdf_bytes, st.session_state.pdf_page, st.session_state.highlight_text)
        st.image(img, use_container_width=True)
        
        # NOTATNIK
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
            st.success("Zapisano!")
    else:
        st.info("Wybierz plik z biblioteki.")
