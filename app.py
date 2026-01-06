import streamlit as st
from openai import OpenAI
from gtts import gTTS
import os
from PyPDF2 import PdfReader

# 1. Konfiguracja i Styl
st.set_page_config(page_title="Synapse AI - Twoja Baza Wiedzy", page_icon="📚")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("📚 Synapse AI: Personalny Asystent")
st.markdown("---")

# 2. Panel boczny do wgrywania notatek
with st.sidebar:
    st.header("📂 Twoje Materiały")
    uploaded_file = st.file_uploader("Wgraj notatki (PDF lub TXT)", type=['pdf', 'txt'])
    
    if uploaded_file:
        st.success(f"Załadowano: {uploaded_file.name}")

# Funkcja do wyciągania tekstu z plików
def get_text_from_file(file):
    if file.type == "application/pdf":
        pdf_reader = PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    else:
        return str(file.read(), "utf-8")

# 3. Pole na pytanie
user_input = st.text_area("Wklej pytanie dotyczące Twoich materiałów:", height=100)

if user_input:
    if not uploaded_file:
        st.warning("⚠️ Najpierw wgraj swoje notatki w panelu po lewej stronie!")
    else:
        with st.spinner('Przeszukuję Twoje notatki...'):
            # Wyciągamy treść z wgranego pliku
            context_text = get_text_from_file(uploaded_file)
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Jesteś precyzyjnym asystentem nauki. Odpowiadaj WYŁĄCZNIE na podstawie dostarczonych notatek. Jeśli w notatkach nie ma odpowiedzi, powiedz: 'Niestety nie widzę tej informacji w Twoich materiałach'. OTO NOTATKI: {context_text[:15000]}"}, # Limit tekstu dla stabilności
                        {"role": "user", "content": user_input}
                    ]
                )
                
                odp = response.choices[0].message.content
                st.subheader("📝 Odpowiedź z Twoich notatek:")
                st.write(odp)

                # Lektor
                if st.button("🔊 Odsłuchaj"):
                    tts = gTTS(text=odp, lang='pl')
                    tts.save("voice.mp3")
                    st.audio("voice.mp3")
                
                st.caption(f"Źródło: Analiza pliku {uploaded_file.name}")

            except Exception as e:
                st.error(f"Błąd: {e}")
