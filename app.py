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

# Inicjalizacja stanu strony PDF
if "pdf_page" not in st.session_state:
    st.session_state.pdf_page = 0

# --- 3. FUNKCJE POMOCNICZE ---

def display_single_page(pdf_bytes, page_num):
    """Renderuje tylko jedną wybraną stronę PDF jako obraz"""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        # Zabezpieczenie zakresu stron
        page_num = max(0, min(page_num, total_pages - 1))
        
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Skalowanie x2 dla ostrości
        img_data = pix.tobytes("png")
        
        st.image(img_data, caption=f"Strona {page_num + 1} z {total_pages}", use_container_width=True)
        return total_pages
    except Exception as e:
        st.error(f"Błąd podglądu strony: {e}")
        return 0

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
            # Reset strony przy zmianie pliku
            if "last_file" not in st.session_state or st.session_state.last_file != selected_file:
                st.session_state.pdf_page = 0
                st.session_state.last_file = selected_file
            
            file_data = repo.get_contents(f"baza_wiedzy/{selected_cat}/{selected_file}")
            current_pdf_bytes = file_data.decoded_content
            pdf = PdfReader(BytesIO(current_pdf_bytes))
            library_context = "".join([page.extract_text() for page in pdf.pages])

        st.markdown("---")
        up_pdf = st.file_uploader("Dodaj PDF", type=['pdf'])
        if up_pdf and st.button("Wyślij"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.success("Zapisano!")
            st.rerun()

# --- 5. UKŁAD DWUKOLUMNOWY ---
st.title("🧠 Inteligentna nauka")
col1, col2 = st.columns([1, 1.2]) # Prawa kolumna nieco szersza dla PDF

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
        
        # --- NAWIGACJA STRONAMI ---
        # Tworzymy 3 kolumny dla przycisków sterowania
        p1, p2, p3 = st.columns([1, 2, 1])
        
        # Tymczasowo otwieramy dokument, by znać liczbę stron
        doc_temp = fitz.open(stream=current_pdf_bytes, filetype="pdf")
        max_p = len(doc_temp)
        doc_temp.close()

        with p1:
            if st.button("⬅️ Poprzednia"):
                if st.session_state.pdf_page > 0:
                    st.session_state.pdf_page -= 1
                    st.rerun()
        
        with p2:
            # Suwak do szybkiego skakania po stronach
            st.session_state.pdf_page = st.slider("Idź do strony:", 0, max_p-1, st.session_state.pdf_page, format="Str. %d")
            
        with p3:
            if st.button("Następna ➡️"):
                if st.session_state.pdf_page < max_p - 1:
                    st.session_state.pdf_page += 1
                    st.rerun()

        st.markdown("---")
        
        # Wyświetlanie tylko aktualnej strony
        display_single_page(current_pdf_bytes, st.session_state.pdf_page)
        
        st.markdown("---")
        st.subheader("📝 Twoje notatki")
        saved_text = get_saved_notes(selected_cat, selected_file)
        user_notes = st.text_area("Twoje uwagi do tego pliku:", value=saved_text, height=200)
        
        if st.button("Zapisz notatki"):
            notes_path = f"baza_wiedzy/{selected_cat}/{selected_file.replace('.pdf', '')}_notatki.txt"
            try:
                old = repo.get_contents(notes_path)
                repo.update_file(notes_path, "update", user_notes, old.sha)
            except:
                repo.create_file(notes_path, "create", user_notes)
            st.success("Notatki zapisane!")
    else:
        st.info("Wybierz plik z biblioteki po lewej.")
