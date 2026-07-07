import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

st.set_page_config(page_title="FX & Crypto Flow", page_icon="⚡", layout="centered")

st.title("⚡ Diagnostic FX & Crypto Flow")

# --- BLOC DE DIAGNOSTIC DE SÉCURITÉ ---
try:
    ticker_test = "BTC-USD"
    st.write("1. Connexion au serveur Yahoo Finance...")
    df_test = yf.Ticker(ticker_test).history(interval="1h", period="1mo")
    
    if df_test.empty:
        st.error("⚠️ Erreur : Yahoo Finance renvoie un tableau vide. Le serveur bloque peut-être les requêtes.")
    else:
        st.success(f"🟩 Connexion OK. {len(df_test)} lignes récupérées pour {ticker_test}.")
        
        st.write("2. Test des calculs mathématiques internes...")
        # Simulation rapide de l'EMA pour voir si numpy/pandas s'emmêlent
        df_test['EMA'] = df_test['Close'].ewm(span=200, adjust=False).mean()
        st.success(f"🟩 Calculs OK. Dernière EMA : {df_test['EMA'].iloc[-1]}")

except Exception as e:
    st.error("💥 CRASH DÉTECTÉ AU DÉMARRAGE 💥")
    st.markdown(f"**Type d'erreur :** `{str(e)}`")
    st.markdown("**Détails techniques complets (Traceback) :**")
    st.code(traceback.format_exc())

st.write("---")
st.info("Ce script sert à localiser l'élément précis qui fait disjoncter le serveur Streamlit Cloud. Regarde ce qui s'affiche sur ton écran et dis-moi.")
