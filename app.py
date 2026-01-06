import streamlit as st
from openai import OpenAI
from gtts import gTTS
import os

# 1. Konfiguracja strony
st.set_page_config(page_title="Synapse AI - Nauka", page_icon="🧠")

# 2. Połączenie z OpenAI przy użyciu klucza z Twoich "Secrets"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🧠 Synapse AI: Twój Asystent Nauki")
st.markdown("---")

# 3. Pole tekstowe - automatycznie wyzwala akcję po wklejeniu
user_input = st.text_area("Wklej pytanie lub fragment tekstu ze schowka:", 
                          placeholder="Np. Kiedy odbył się chrzest Polski?",
                          height=150)

# Funkcja lektora
def play_audio(text):
    tts = gTTS(text=text, lang='pl')
    tts.save("speech.mp3")
    st.audio("speech.mp3")

# 4. Automatyczna reakcja na tekst
if user_input:
    with st.spinner('Trwa analiza Twojego zapytania...'):
        try:
            # Zapytanie do AI
            response = client.chat.completions.create(
                model="gpt-4o-mini", # Najszybszy i najtańszy model
                messages=[
                    {"role": "system", "content": "Jesteś pomocnym asystentem nauki. Odpowiadaj konkretnie po polsku. Na końcu odpowiedzi zawsze dodaj sekcję 'ŹRÓDŁO', wskazując na ogólną wiedzę historyczną lub naukową, chyba że w pytaniu podano inaczej."},
                    {"role": "user", "content": user_input}
                ]
            )
            
            pelna_odpowiedz = response.choices[0].message.content

            # Rozdzielenie odpowiedzi od źródła (dla ładnego wyglądu)
            if "ŹRÓDŁO" in pelna_odpowiedz:
                tekst_odp, tekst_zrodlo = pelna_odpowiedz.split("ŹRÓDŁO", 1)
            else:
                tekst_odp, tekst_zrodlo = pelna_odpowiedz, "Wiedza ogólna AI"

            st.subheader("📝 Odpowiedź:")
            st.write(tekst_odp)
            
            # Przycisk lektora
            if st.button("🔊 Odsłuchaj odpowiedź"):
                play_audio(tekst_odp)

            # Sekcja źródła w rozwijanym pasku
            with st.expander("🔍 Zobacz źródło informacji"):
                st.info(tekst_zrodlo.strip(": "))

        except Exception as e:
            st.error(f"Wystąpił błąd: {e}")
            st.info("Upewnij się, że Twój klucz API jest poprawnie dodany w Settings -> Secrets.")

else:
    st.info("Program czeka na wklejenie tekstu. Nie musisz nic klikać – odpowiedź pojawi się sama.")
