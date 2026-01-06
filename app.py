import streamlit as st
from openai import OpenAI
from github import Github
from gtts import gTTS
import os
import base64
from PyPDF2 import PdfReader
from io import BytesIO

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

# --- 3. FUNKCJE POMOCNICZE ---

def get_saved_notes(category, original_file):
    """Pobiera zapisane notatki tekstowe z GitHuba"""
    notes_path = f"baza_wiedzy/{category}/{original_file.replace('.pdf', '')}_notatki.txt"
    try:
        return repo.get_contents(notes_path).decoded_content.decode()
    except:
        return ""

def display_pdf_robust(pdf_bytes, file_name):
    """Najstabilniejsza metoda wyświetlania PDF w Streamlit"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    # Link "ratunkowy" do otwarcia w nowej karcie
    st.markdown(f'<a href="data:application/pdf;base64,{base64_pdf}" target="_blank" style="text-decoration:none;"><button style="width:100%; border-radius:5px; background-color:#4CAF50; color:white; padding:10px; border:none; cursor:pointer;">📂 Otwórz PDF w pełnym oknie (jeśli podgląd poniżej jest pusty)</button></a>', unsafe_allow_html=True)
    
    # Ramka podglądu
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.components.v1.html(pdf_display, height=800)

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
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("❓ Zadaj pytanie AI")
    pasted_file = st.file_uploader("Zrzut ekranu (Ctrl+V):", type=['png', 'jpg', 'jpeg'])
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
        st.subheader(f"📖 {selected_file}")
        display_pdf_robust(current_pdf_bytes, selected_file)
        
        st.markdown("---")
        st.subheader("📝 Twoje notatki do tego pliku")
        
        # Wczytujemy notatki z bazy
        saved_text = get_saved_notes(selected_cat, selected_file)
        user_notes = st.text_area("Pisz tutaj (zostaną zapisane na stałe):", value=saved_text, height=250)
        
        if st.button("Zapisz notatki na GitHubie"):
            notes_path = f"baza_wiedzy/{selected_cat}/{selected_file.replace('.pdf', '')}_notatki.txt"
            try:
                old = repo.get_contents(notes_path)
                repo.update_file(notes_path, "update notes", user_notes, old.sha)
            except:
                repo.create_file(notes_path, "create notes", user_notes)
            st.success("Notatki zapisane!")
    else:
        st.info("Wybierz plik z biblioteki po lewej.")
