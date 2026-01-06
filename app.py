import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
from PyPDF2 import PdfReader
import base64
from io import BytesIO

# 1. Inicjalizacja Klientów
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo_name = "marzenazielinska0503-byte/moje_notatki"
repo = g.get_repo(repo_name)

st.set_page_config(page_title="Synapse AI - Biblioteka Wiedzy", layout="wide")

# 2. Funkcje GitHuba (Trwały zapis)
def get_categories():
    try:
        contents = repo.get_contents("baza_wiedzy")
        return [c.name for c in contents if c.type == "dir"]
    except:
        return []

def save_to_github(file_bytes, category, file_name):
    path = f"baza_wiedzy/{category}/{file_name}"
    content = base64.b64encode(file_bytes).decode()
    try:
        repo.create_file(path, f"Dodano notatkę: {file_name}", base64.b64decode(content))
        return True
    except:
        return False

# 3. Interfejs - Panel Boczny (Zarządzanie)
with st.sidebar:
    st.title("📂 Twoja Biblioteka")
    
    # Tworzenie nowej kategorii
    new_cat = st.text_input("Dodaj nową kategorię (np. Geografia):")
    if st.button("Utwórz kategorię"):
        repo.create_file(f"baza_wiedzy/{new_cat}/.keep", "Inicjalizacja kategorii", "")
        st.rerun()

    st.markdown("---")
    categories = get_categories()
    selected_cat = st.selectbox("Wybierz kategorię do nauki:", ["Wszystkie"] + categories)
    
    st.markdown("---")
    st.subheader("📤 Dodaj nowe notatki")
    uploaded_file = st.file_uploader("Wgraj PDF lub ZDJĘCIE notatek", type=['pdf', 'png', 'jpg', 'jpeg'])
    
    if uploaded_file and selected_cat != "Wszystkie":
        if st.button(f"Zapisz w {selected_cat} na stałe"):
            if save_to_github(uploaded_file.getvalue(), selected_cat, uploaded_file.name):
                st.success("Zapisano na GitHubie!")
                st.rerun()

# 4. Funkcja czytania PDF i Zdjęć (Wizja AI)
def analyze_content(user_query, file_data):
    # Jeśli to PDF (tekstowy)
    if file_data.name.endswith('.pdf'):
        pdf = PdfReader(file_data)
        text = "".join([page.extract_text() for page in pdf.pages])
        if text.strip(): # Jeśli ma tekst (OCR niepotrzebny)
            prompt = f"Oto notatki: {text[:15000]}\n\nPytanie: {user_query}"
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    
    # Jeśli to zdjęcie lub skan PDF bez tekstu (Wizja AI)
    # Dla zdjęć wysyłamy obraz bezpośrednio do modelu GPT-4o
    st.info("To skan lub zdjęcie. Uruchamiam wzrok AI...")
    base64_image = base64.b64encode(file_data.getvalue()).decode('utf-8')
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Przeczytaj te notatki i odpowiedz na pytanie: {user_query}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
            }
        ],
    )
    return response.choices[0].message.content

# 5. Główny Ekran
st.title("🧠 Synapse AI")
st.write(f"Aktualna kategoria: **{selected_cat}**")

question = st.text_input("Zadaj pytanie do swoich notatek:")

if question:
    if uploaded_file:
        with st.spinner("Analizuję Twoje materiały..."):
            odp = analyze_content(question, uploaded_file)
            st.subheader("📝 Odpowiedź:")
            st.write(odp)
            
            # Lektor
            tts = gTTS(text=odp, lang='pl')
            tts.save("speech.mp3")
            st.audio("speech.mp3")
            st.caption(f"Źródło: Twoje notatki w {selected_cat}")
    else:
        st.warning("Wgraj plik lub wybierz coś z biblioteki, aby AI mogło odpowiedzieć.")
