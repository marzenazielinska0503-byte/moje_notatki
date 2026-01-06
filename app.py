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

st.set_page_config(page_title="Inteligentna nauka", layout="wide")

# --- 3. FUNKCJE POMOCNICZE ---
def analyze_content(user_query, image_bytes=None, text_context=None):
    """Uniwersalna funkcja analizy: obraz lub tekst"""
    messages = []
    
    if image_bytes:
        base64_img = base64.b64encode(image_bytes).decode('utf-8')
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": user_query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]
        }]
        model_name = "gpt-4o"
    else:
        prompt = f"Użyj tych notatek jako źródła: {text_context[:15000]}\n\nPytanie: {user_query}" if text_context else user_query
        messages = [{"role": "user", "content": prompt}]
        model_name = "gpt-4o-mini"

    response = client.chat.completions.create(model=model_name, messages=messages)
    return response.choices[0].message.content

def get_categories():
    try:
        contents = repo.get_contents("baza_wiedzy")
        return [c.name for c in contents if c.type == "dir"]
    except: return []

def get_files_in_category(category):
    try:
        contents = repo.get_contents(f"baza_wiedzy/{category}")
        return [c.name for c in contents if c.name != ".keep"]
    except: return []

def download_and_read_pdf(category, filename):
    file_content = repo.get_contents(f"baza_wiedzy/{category}/{filename}")
    pdf_bytes = file_content.decoded_content
    pdf = PdfReader(BytesIO(pdf_bytes))
    return "".join([page.extract_text() for page in pdf.pages])

# --- 4. PANEL BOCZNY (TWOJA BIBLIOTEKA) ---
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
    cats = get_categories()
    selected_cat = st.selectbox("Wybierz przedmiot:", ["---"] + cats)
    
    library_context = ""
    if selected_cat != "---":
        files = get_files_in_category(selected_cat)
        selected_file = st.selectbox("Wybierz plik z bazy:", ["Brak / Nowy"] + files)
        
        if selected_file != "Brak / Nowy":
            with st.spinner("Wczytuję plik z bazy..."):
                library_context = download_and_read_pdf(selected_cat, selected_file)
                st.success(f"Wczytano: {selected_file}")

        st.markdown("---")
        st.subheader("📤 Dodaj nowy plik")
        up_pdf = st.file_uploader("Wgraj PDF", type=['pdf'])
        if up_pdf and st.button("Zapisz na GitHub"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.success("Zapisano!")
            st.rerun()

# --- 5. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")

# Obsługa schowka
pasted_file = st.file_uploader("Wklej zrzut ekranu (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
custom_question = st.text_input("Wpisz pytanie tekstowe:")

# LOGIKA ANALIZY (Poprawiona)
if st.button("Zapytaj AI") or pasted_file:
    # 1. Priorytet: Pytanie do obrazka ze schowka
    if pasted_file:
        query = custom_question if custom_question else "Rozwiąż zadanie ze zdjęcia."
        with st.spinner("Analizuję obrazek..."):
            wynik = analyze_content(query, image_bytes=pasted_file.getvalue())
    
    # 2. Pytanie tekstowe (do pliku z bazy lub ogólne)
    elif custom_question:
        with st.spinner("Przeszukuję bazę wiedzy..."):
            wynik = analyze_content(custom_question, text_context=library_context)
    
    else:
        st.warning("Wklej obrazek lub wpisz pytanie!")
        st.stop()

    # Wyświetlanie wyniku
    st.subheader("📝 Odpowiedź:")
    st.write(wynik)
    tts = gTTS(text=wynik, lang='pl')
    tts.save("voice.mp3")
    st.audio("voice.mp3")

elif not pasted_file and not custom_question:
    st.info("Wklej zrzut ekranu lub wybierz plik z bazy po lewej i wpisz pytanie.")
