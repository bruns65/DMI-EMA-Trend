import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Configuration de l'affichage mobile
st.set_page_config(page_title="FX & Crypto Flow", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e222d;
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #2f333e;
    }
    .buy-text { color: #00e676; font-weight: bold; }
    .sell-text { color: #ff5252; font-weight: bold; }
    .title-text { font-size: 18px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ FX & Crypto Flow")

# Sélection du marché
asset_type = st.radio("Type de marché :", ["Forex", "Crypto"], horizontal=True)

if asset_type == "Forex":
    fx_choice = st.selectbox("Paire Forex :", ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"])
    ticker_symbol = fx_choice
else:
    crypto_choice = st.selectbox("Crypto :", ["BTC-USD", "ETH-USD", "SOL-USD"])
    ticker_symbol = crypto_choice

adx_period = 14
adx_threshold = 20

# Formule mathématique native pour le DMI et l'EMA
def compute_dmi_and_ema(df, compute_ema=False):
    try:
        if compute_ema:
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['plus_dm'] = df['High'].diff()
        df['minus_dm'] = df['Low'].diff(-1)
        
        df['plus_dm'] = np.where((df['plus_dm'] > df['minus_dm']) & (df['plus_dm'] > 0), df['plus_dm'], 0)
        df['minus_dm'] = np.where((df['minus_dm'] > df['plus_dm']) & (df['minus_dm'] > 0), df['minus_dm'], 0)
        
        df['tr1'] = df['High'] - df['Low']
        df['tr2'] = abs(df['High'] - df['Close'].shift(1))
        df['tr3'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        df['TR_smooth'] = df['TR'].ewm(alpha=1/adx_period, adjust=False).mean()
        df['DM_plus_smooth'] = df['plus_dm'].ewm(alpha=1/adx_period, adjust=False).mean()
        df['DM_minus_smooth'] = df['minus_dm'].ewm(alpha=1/adx_period, adjust=False).mean()
        
        df['DI_plus'] = (df['DM_plus_smooth'] / df['TR_smooth']) * 100
        df['DI_minus'] = (df['DM_minus_smooth'] / df['TR_smooth']) * 100
        
        df['DX'] = (abs(df['DI_plus'] - df['DI_minus']) / (df['DI_plus'] + df['DI_minus'])) * 100
        df['ADX'] = df['DX'].ewm(alpha=1/adx_period, adjust=False).mean()
        
        res = {
            "close": df['Close'].iloc[-1],
            "DI+": round(df['DI_plus'].iloc[-1], 1),
            "DI-": round(df['DI_minus'].iloc[-1], 1),
            "ADX": round(df['ADX'].iloc[-1], 1)
        }
        if compute_ema:
            res["EMA_200"] = df['EMA_200'].iloc[-1]
        return res
    except:
        return None

# --- APPELS ALLÉGÉS POUR SÉCURISER L'API ---
with st.spinner("Analyse des flux financiers..."):
    # Graphique Macro 1H : Historique large pour l'EMA 200
    df_1h_raw = yf.Ticker(ticker_symbol).history(interval="1h", period="3mo")
    data_1h = compute_dmi_and_ema(df_1h_raw, compute_ema=True) if not df_1h_raw.empty else None

    # Graphique Intermédiaire 15m : Allégé à 2 jours
    df_15m_raw = yf.Ticker(ticker_symbol).history(interval="15m", period="2d")
    data_15m = compute_dmi_and_ema(df_15m_raw) if not df_15m_raw.empty else None

    # Graphique Chirurgical 5m : Allégé à 1 jour (suffisant pour un DMI 14)
    df_5m_raw = yf.Ticker(ticker_symbol).history(interval="5m", period="1d")
    data_5m = compute_dmi_and_ema(df_5m_raw) if not df_5m_raw.empty else None

# Affichage des résultats
if data_1h and data_15m and data_5m:
    is_macro_bull = data_1h["close"] > data_1h["EMA_200"]
    macro_status = "🟩 HAUSSIER (Prix > EMA200)" if is_macro_bull else "🟥 BAISSIER (Prix < EMA200)"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix en direct : **{round(data_5m['close'], 5)}**")
    st.write("---")
    
    tf_dashboard = [
        ("5 min (Signal)", data_5m),
        ("15 min (Intermédiaire)", data_15m),
        ("1H (Structure)", data_1h)
    ]
    
    for name, data in tf_dashboard:
        di_p, di_m, adx = data["DI+"], data["DI-"], data["ADX"]
        
        if di_p > di_m and adx > adx_threshold:
            signal_html = '<span class="buy-text">🚀 ACHAT ALIGNÉ</span>' if is_macro_bull else '<span class="buy-text">⚠️ ACHAT CONTRE-TENDANCE</span>'
        elif di_m > di_p and adx > adx_threshold:
            signal_html = '<span class="sell-text">💥 VENTE ALIGNÉE</span>' if not is_macro_bull else '<span class="sell-text">⚠️ VENTE CONTRE-TENDANCE</span>'
        else:
            signal_html = '<span style="color: #888;">⏳ Neutre / Compression</span>'
            
        st.markdown(f"""
            <div class="metric-card">
                <div class="title-text">{name}</div>
                <table style="width:100%; border:none; margin-top:5px; color: #e0e0e0;">
                    <tr>
                        <td><b>DI+ :</b> {di_p}</td>
                        <td><b>DI- :</b> {di_m}</td>
                        <td><b>ADX :</b> {adx}</td>
                    </tr>
                </table>
                <div style="margin-top: 8px;">{signal_html}</div>
            </div>
        """, unsafe_allow_html=True)
        
    if st.button("🔄 Actualiser le flux"):
        st.rerun()
else:
    st.error("Problème temporaire avec Yahoo Finance. Si nous sommes le week-end, bascule sur l'onglet 'Crypto' car les devises Forex ne cotent pas.")
