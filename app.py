import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
import base64
from PyPDF2 import PdfReader

# --- 1. ZABEZPIECZENIE HASŁEM ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔒 Prywatny Asystent Synapse AI")
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

st.set_page_config(page_title="Synapse AI - Automat", layout="wide")

# --- 3. FUNKCJE POMOCNICZE ---
def analyze_image_vision(image_bytes, user_query="Rozwiąż to zadanie lub odpowiedz na pytanie ze zdjęcia."):
    """Funkcja obsługująca Vision AI dla zrzutów ekranu"""
    base64_img = base64.b64encode(image_bytes).decode('utf-8')
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": user_query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]
        }]
    )
    return response.choices[0].message.content

def get_categories():
    try:
        return [c.name for c in repo.get_contents("baza_wiedzy") if c.type == "dir"]
    except: return []

# --- 4. PANEL BOCZNY (BIBLIOTEKA PDF) ---
with st.sidebar:
    st.header("📂 Biblioteka PDF")
    cats = get_categories()
    selected_cat = st.selectbox("Wybierz przedmiot:", cats if cats else ["Brak kategorii"])
    
    st.markdown("---")
    st.subheader("➕ Dodaj PDF do bazy")
    new_pdf = st.file_uploader("Wgraj PDF na stałe", type=['pdf'])
    if new_pdf and st.button("Zapisz w bazie"):
        path = f"baza_wiedzy/{selected_cat}/{new_pdf.name}"
        repo.create_file(path, f"Dodano PDF: {new_pdf.name}", new_pdf.getvalue())
        st.success("PDF dodany do bazy danych!")

# --- 5. GŁÓWNY EKRAN (AUTOMAT ZE SCHOWKA) ---
st.title("🧠 Synapse AI: Tryb Automatyczny")
st.write("Wklej zrzut ekranu (Ctrl+V) poniżej, aby od razu uzyskać odpowiedź.")

# Pole wgrywania obsługuje wklejanie ze schowka
pasted_file = st.file_uploader("Wklej obrazek ze schowka lub przeciągnij plik:", type=['png', 'jpg', 'jpeg'])
custom_question = st.text_input("Dodatkowe pytanie (opcjonalnie):", placeholder="Możesz zostawić puste dla automatu")

# --- MAGIA AUTOMATU ---
if pasted_file:
    # Program reaguje natychmiast po pojawieniu się pliku
    with st.spinner("AI analizuje Twój zrzut ekranu..."):
        # Jeśli pole tekstowe jest puste, AI samo domyśla się, że ma rozwiązać zadanie
        query = custom_question if custom_question else "To jest zrzut ekranu z pytaniem/zadaniem. Rozwiąż je precyzyjnie po polsku."
        
        try:
            wynik = analyze_image_vision(pasted_file.getvalue(), query)
            
            st.subheader("📝 Rozwiązanie:")
            st.write(wynik)
            
            # Automatyczny lektor
            tts = gTTS(text=wynik, lang='pl')
            tts.save("voice.mp3")
            st.audio("voice.mp3")
            
        except Exception as e:
            st.error(f"Błąd analizy: {e}")

elif not pasted_file and not custom_question:
    st.info("Czekam na Twój zrzut ekranu ze schowka...")
