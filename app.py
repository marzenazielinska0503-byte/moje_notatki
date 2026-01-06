import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO

# --- 1. ZABEZPIECZENIE HASŁEM ---
# Sprawdza, czy użytkownik jest zalogowany
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔒 Prywatny Asystent")
    pwd = st.text_input("Podaj swoje indywidualne hasło:", type="password")
    if st.button("Zaloguj"):
        # Pobiera listę haseł z bezpiecznej sekcji Secrets
        if pwd in st.secrets["passwords"].values():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Błędne hasło!")
    st.stop()

# --- 2. KONFIGURACJA I POŁĄCZENIA ---
# Inicjalizacja klientów OpenAI i GitHub przy użyciu Tokenów
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
g = Github(st.secrets["GITHUB_TOKEN"])
repo = g.get_repo("marzenazielinska0503-byte/moje_notatki")

st.set_page_config(page_title="Inteligentna nauka", layout="wide")

# --- 3. FUNKCJE POMOCNICZE ---

def display_pdf_preview(pdf_bytes, file_name):
    """Wyświetla podgląd PDF i dodaje przycisk pobierania jako plan awaryjny"""
    try:
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        # Zastosowanie tagu embed dla lepszej kompatybilności z przeglądarkami
        pdf_display = f'''
            <embed src="data:application/pdf;base64,{base64_pdf}#toolbar=0&navpanes=0&scrollbar=0" 
            width="100%" height="800" type="application/pdf">
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        st.info("💡 Jeśli powyższy podgląd się nie ładuje, użyj przycisku poniżej:")
        st.download_button(
            label="📥 Otwórz / Pobierz ten plik PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Nie udało się wygenerować podglądu: {e}")

def analyze_content(user_query, image_bytes=None, text_context=None):
    """Przesyła dane do odpowiedniego modelu AI (Vision lub Text)"""
    if image_bytes:
        # Obsługa zrzutów ekranu (Wizja AI)
        base64_img = base64.b64encode(image_bytes).decode('utf-8')
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": user_query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
    else:
        # Analiza tekstu z dokumentu
        prompt = f"Użyj tych notatek jako źródła: {text_context[:15000]}\n\nPytanie: {user_query}" if text_context else user_query
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def get_categories():
    """Pobiera foldery z repozytorium GitHub"""
    try:
        contents = repo.get_contents("baza_wiedzy")
        return [c.name for c in contents if c.type == "dir"]
    except: return []

def get_files_in_category(category):
    """Listuje pliki w konkretnym folderze"""
    try:
        contents = repo.get_contents(f"baza_wiedzy/{category}")
        return [c.name for c in contents if c.name != ".keep"]
    except: return []

# --- 4. PANEL BOCZNY (ZARZĄDZANIE BIBLIOTEKĄ) ---
with st.sidebar:
    st.title("📂 Biblioteka")
    
    st.subheader("🆕 Nowa kategoria")
    new_cat = st.text_input("Nazwa przedmiotu:")
    if st.button("Utwórz"):
        if new_cat:
            # Tworzy folder na GitHubie
            repo.create_file(f"baza_wiedzy/{new_cat}/.keep", "init", "")
            st.rerun()

    st.markdown("---")
    
    cats = get_categories()
    selected_cat = st.selectbox("Wybierz przedmiot:", ["---"] + cats)
    
    library_context = ""
    current_pdf_bytes = None
    
    if selected_cat != "---":
        files = get_files_in_category(selected_cat)
        selected_file = st.selectbox("Wybierz plik z bazy:", ["Brak / Nowy"] + files)
        
        if selected_file != "Brak / Nowy":
            with st.spinner("Wczytywanie z bazy..."):
                file_data = repo.get_contents(f"baza_wiedzy/{selected_cat}/{selected_file}")
                current_pdf_bytes = file_data.decoded_content
                # Czytanie tekstu dla AI
                pdf = PdfReader(BytesIO(current_pdf_bytes))
                library_context = "".join([page.extract_text() for page in pdf.pages])
                st.success(f"Wczytano: {selected_file}")

        st.markdown("---")
        st.subheader("📤 Dodaj nowy PDF")
        up_pdf = st.file_uploader("Zapisz plik w tej kategorii", type=['pdf'])
        if up_pdf and st.button("Zapisz na stałe"):
            repo.create_file(f"baza_wiedzy/{selected_cat}/{up_pdf.name}", "add", up_pdf.getvalue())
            st.success("Plik zapisany na GitHubie!")
            st.rerun()

# --- 5. GŁÓWNY EKRAN ---
st.title("🧠 Inteligentna nauka")

tab_pytania, tab_podglad = st.tabs(["❓ Zadaj pytanie", "📖 Podgląd dokumentu"])

with tab_pytania:
    # Obsługa wklejania obrazów ze schowka (Ctrl+V)
    pasted_file = st.file_uploader("Wklej zrzut ekranu (Ctrl+V):", type=['png', 'jpg', 'jpeg'], key="main_up")
    custom_question = st.text_input("Wpisz pytanie do notatek lub ogólne:")

    if st.button("Zapytaj AI") or pasted_file:
        with st.spinner("Analizuję..."):
            if pasted_file:
                query = custom_question if custom_question else "Rozwiąż to zadanie ze zdjęcia."
                wynik = analyze_content(query, image_bytes=pasted_file.getvalue())
            elif custom_question:
                wynik = analyze_content(custom_question, text_context=library_context)
            else:
                st.warning("Podaj pytanie lub wklej obrazek!")
                st.stop()

            st.subheader("📝 Odpowiedź:")
            st.write(wynik)
            
            # Synteza mowy (Lektor)
            try:
                tts = gTTS(text=wynik, lang='pl')
                tts.save("voice.mp3")
                st.audio("voice.mp3")
            except: pass

with tab_podglad:
    if current_pdf_bytes:
        st.subheader(f"Przeglądasz: {selected_file}")
        display_pdf_preview(current_pdf_bytes, selected_file)
    else:
        st.info("Wybierz plik z biblioteki po lewej stronie, aby otworzyć podgląd.")
