import streamlit as st
from gtts import gTTS
import os

st.set_page_config(page_title="Synapse AI - Nauka", page_icon="📚")

st.title("🧠 Synapse AI: Twój Asystent Nauki")
st.markdown("---")

# 1. Pole tekstowe reagujące na wklejenie
user_input = st.text_area("Wklej pytanie lub fragment tekstu ze schowka:", 
                          placeholder="Np. Kiedy odbył się chrzest Polski?",
                          height=150)

def play_audio(text):
    tts = gTTS(text=text, lang='pl')
    tts.save("speech.mp3")
    st.audio("speech.mp3")

# 2. Automatyczna akcja
if user_input:
    with st.spinner('AI analizuje materiały...'):
        # Przykładowa logika (później połączymy to z Twoją bazą)
        odpowiedz = "Przykładowa odpowiedź wygenerowana na podstawie Twoich notatek."
        zrodlo = "Notatki z Historii, Rozdział 2, strona 4"

        st.subheader("📝 Odpowiedź:")
        st.write(odpowiedz)
        
        if st.button("🔊 Odsłuchaj odpowiedź"):
            play_audio(odpowiedz)

        with st.expander("🔍 Zobacz źródło informacji"):
            st.info(f"Źródło: {zrodlo}")
else:
    st.info("Wklej tekst, aby uzyskać automatyczną odpowiedź.")
