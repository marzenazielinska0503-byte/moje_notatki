import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO

# --- 1. ZABEZPIECZENIE HASŁEM ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔒 Prywatny Asystent")
    pwd = st.text_input("Podaj swoje indywidualne hasło:", type="password")
    if st.button("Zaloguj"):
        if pwd in st.secrets["passwords"].values():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Błędne hasło!")
    st.stop()

# --- 2. KONFIGURACJA I POŁĄCZENIA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")

# Ustawienie szerokiego układu
st.set_page_config(page_title="Inteligentna nauka", layout="wide")

# --- 3. FUNKCJE POMOCNICZE ---

def save_notes_to_github(category, original_file, notes_content):
    """Zapisuje notatki tekstowe powiązane z PDF-em na GitHubie"""
    notes_file_name = f"{original_file.replace('.pdf', '')}_notatki.txt"
    path = f"baza_wiedzy/{category}/{notes_file_name}"
    try:
        # Sprawdź czy plik już istnieje, aby go zaktualizować
        contents = repo.get_contents(path)
        repo.update_file(path, f"Aktualizacja notatek do {original_file}", notes_content, contents.sha)
    except:
        # Jeśli nie istnieje, utwórz nowy
        repo.create_file(path, f"Tworzenie notatek do {original_file}", notes_content)
    return True

def display_pdf_preview(pdf_bytes):
    """Wyświetla PDF w kolumnie"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    # Zwiększamy wysokość do 1000px dla lepszej czytelności
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="1000" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

def analyze_content(user_query, image_bytes=None, text_context=None):
    if image_bytes:
        base64_img = base64.b64encode(image_bytes).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [{"type": "text", "text": user_query}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}]}]
        )
    else:
        prompt = f"Notatki: {text_context[:15000]}\n\nPytanie: {user_query}" if text_context else user_query
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

# --- 4. PANEL BOCZNY (BIBLIOTEKA) ---
with st.sidebar:
    st.title("📂 Biblioteka")
    
    # Tworzenie kategorii
    st.subheader("🆕 Nowa kategoria")
    new_cat = st.text_input("Nazwa przedmiotu:")
    if st.button("Utwórz"):
        if new_cat:
            repo.create_file(f"baza_wiedzy/{new_cat}/.keep", "init", "")
            st.rerun()

    st.markdown("---")
    
    # Wybór kategorii i PLIKU
    contents = repo.get_contents("baza_wiedzy")
    cats = [c.name for c in contents if c.type == "dir"]
    selected_cat = st.selectbox("Wybierz przedmiot:", ["---"] + cats)
    
    library_context = ""
    current_pdf_bytes = None
    
    if selected_cat != "---":
        f_contents = repo.get_contents(f"baza_wiedzy/{selected_cat}")
        files = [c.name for c in f_contents if c.name.endswith('.pdf')]
        selected_file = st.selectbox("Wybierz plik z bazy:", ["Brak"] + files)
        
        if selected_file != "Brak":
            with st.spinner("Pobieranie dokumentu..."):
                file_data = repo.get_contents(f"baza_wiedzy/{selected_cat}/{selected_file}")
                current_pdf_bytes = file_data.decoded_content
                pdf = PdfReader(BytesIO(current_pdf_bytes))
                library_context = "".join([page.extract_text() for page in pdf.pages])

        st.markdown("---")
        st.subheader("📤 Dodaj PDF")
        up_pdf = st.file_uploader("Wgraj plik", type=['pdf'])
        if up_pdf and st.button("Wyślij na GitHub"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.success("Zapisano!")
            st.rerun()

# --- 5. GŁÓWNY UKŁAD (DWIE KOLUMNY) ---
st.title("🧠 Inteligentna nauka")

col1, col2 = st.columns([1, 1]) # Podział ekranu 50/50

with col1:
    st.subheader("❓ Pytania do AI")
    pasted_file = st.file_uploader("Zrzut ekranu (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
    custom_question = st.text_input("Twoje pytanie:")

    if st.button("Zapytaj") or pasted_file:
        with st.spinner("Analizuję..."):
            if pasted_file:
                query = custom_question if custom_question else "Rozwiąż to zadanie."
                wynik = analyze_content(query, image_bytes=pasted_file.getvalue())
            else:
                wynik = analyze_content(custom_question, text_context=library_context)
            
            st.info(wynik)
            # Lektor
            tts = gTTS(text=wynik, lang='pl')
            tts.save("voice.mp3")
            st.audio("voice.mp3")

with col2:
    if current_pdf_bytes:
        st.subheader(f"📖 Podgląd: {selected_file}")
        display_pdf_preview(current_pdf_bytes)
        
        # SEKCJA NOTATEK
        st.markdown("---")
        st.subheader("📝 Twój Notatnik")
        user_notes = st.text_area("Zapisz ważne punkty lub własne uwagi do tego PDF:", height=200)
        if st.button("Zapisz te notatki na GitHubie"):
            if save_notes_to_github(selected_cat, selected_file, user_notes):
                st.success("Notatki zostały bezpiecznie zapisane obok pliku PDF!")
    else:
        st.info("Wybierz plik z biblioteki, aby go wyświetlić.")
