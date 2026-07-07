import sys
import traceback

# On force un affichage immédiat dans la console Streamlit
print(">>> [LOG URGENCE] Initialisation du script app.py...", flush=True)

try:
    import streamlit as st
    print(">>> [LOG URGENCE] Module 'streamlit' chargé avec succès.", flush=True)
    
    st.title("🛠️ Mode Diagnostic FX & Crypto Flow")
    st.write("Vérification des composants système en cours...")

    # Étape 1 : Test d'import des bibliothèques de calcul
    print(">>> [LOG URGENCE] Tentative de chargement de numpy...", flush=True)
    import numpy as np
    st.success("🟩 Étape 1 : Module 'numpy' OK.")
    print(">>> [LOG URGENCE] Numpy OK.", flush=True)

    # Étape 2 : Test d'import de pandas
    print(">>> [LOG URGENCE] Tentative de chargement de pandas...", flush=True)
    import pandas as pd
    st.success("🟩 Étape 2 : Module 'pandas' OK.")
    print(">>> [LOG URGENCE] Pandas OK.", flush=True)

    # Étape 3 : Test d'import de yfinance
    print(">>> [LOG URGENCE] Tentative de chargement de yfinance...", flush=True)
    import yfinance as yf
    st.success("🟩 Étape 3 : Module 'yfinance' OK.")
    print(">>> [LOG URGENCE] yfinance OK. Tous les modules système sont opérationnels !", flush=True)

    st.balloons()
    st.info("Tous les modules sont chargés. Si tu vois cet écran, le système de base fonctionne. Nous allons pouvoir réinjecter la logique de trading.")

except Exception as e:
    print(f">>> [LOG URGENCE] !!! CRASH INTERNE DÉTECTÉ !!! Erreur: {str(e)}", flush=True)
    st.error("💥 Erreur critique d'initialisation")
    st.code(traceback.format_exc())
