import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# 1. Configuration de l'affichage mobile
st.set_page_config(page_title="FX & Crypto Flow MTF", page_icon="⚡", layout="centered")

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

# 2. Sélections des actifs
asset_type = st.radio("Type de marché :", ["Forex", "Crypto"], horizontal=True)

if asset_type == "Forex":
    fx_choice = st.selectbox("Paire Forex :", ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "EURGBP=X"])
    ticker_symbol = fx_choice
else:
    crypto_choice = st.selectbox("Crypto :", ["BTC-USD", "ETH-USD", "SOL-USD"])
    ticker_symbol = crypto_choice

adx_period = 14
ema_trend_period = 200
adx_threshold = 20

tf_map = {
    "5 min (Signal)": "5m",
    "15 min (Intermédiaire)": "15m",
    "1H (Fond)": "1h"
}

# 3. Fonction d'extraction et calcul ultra-sécurisée
def fetch_yfinance_data(ticker, timeframe):
    try:
        period = "5d" if timeframe in ["5m", "15m"] else "1mo"
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(interval=timeframe, period=period)
        
        if df.empty or len(df) < ema_trend_period:
            return None
            
        # Calcul sécurisé du DMI et de l'EMA
        dmi = df.ta.adx(length=adx_period)
        ema = df.ta.ema(length=ema_trend_period)
        
        if dmi is None or ema is None:
            return None
            
        return {
            "close": df['Close'].iloc[-1],
            "EMA": ema.iloc[-1],
            "ADX": round(dmi[f"ADX_{adx_period}"].iloc[-1], 1),
            "DI+": round(dmi[f"DMP_{adx_period}"].iloc[-1], 1),
            "DI-": round(dmi[f"DMN_{adx_period}"].iloc[-1], 1)
        }
    except Exception as e:
        return None

# --- CALCULS ET INTERFACE ---
with st.spinner("Analyse des flux en cours..."):
    data_1h = fetch_yfinance_data(ticker_symbol, "1h")
    data_15m = fetch_yfinance_data(ticker_symbol, "15m")
    data_5m = fetch_yfinance_data(ticker_symbol, "5m")

if data_1h and data_15m and data_5m:
    is_macro_bull = data_1h["close"] > data_1h["EMA"]
    macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix actuel : **{round(data_5m['close'], 5)}**")
    st.write("---")
    
    for name, tf_code in tf_map.items():
        data = data_5m if "5 min" in name else (data_15m if "15 min" in name else data_1h)
        di_p, di_m, adx = data["DI+"], data["DI-"], data["ADX"]
        
        if di_p > di_m and adx > adx_threshold:
            signal_html = '<span class="buy-text">🚀 ACHAT ALIGNÉ</span>' if is_macro_bull else '<span class="buy-text">⚠️ ACHAT CONTRE-TENDANCE</span>'
        elif di_m > di_p and adx > adx_threshold:
            signal_html = '<span class="sell-text">💥 VENTE ALIGNÉE</span>' if not is_macro_bull else '<span class="sell-
