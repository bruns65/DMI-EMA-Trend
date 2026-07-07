import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Crypto Flow Pro", page_icon="⚡", layout="centered")

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

st.title("⚡ Crypto Flow Direct (API)")

# Sélection de la source et de l'actif
api_source = st.radio("Source de flux :", ["Hyperliquid (Perps)", "Binance (Spot)"], horizontal=True)
crypto_choice = st.selectbox("Actif :", ["BTC", "ETH", "SOL"])

adx_period = 14
adx_threshold = 20

# --- EXTRACTION DIRECTE VIA API BINANCE (Sans yfinance) ---
def get_binance_candles(symbol, interval, limit=250):
    try:
        pair = f"{symbol}USDT"
        url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=4).json()
        
        # Formatage en DataFrame propre
        df = pd.DataFrame(res, columns=[
            'Time', 'Open', 'High', 'Low', 'Close', 'Volume', 
            'CloseTime', 'AssetVolume', 'Trades', 'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
        ])
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        return df
    except:
        return None

# --- EXTRACTION DIRECTE VIA API HYPERLIQUID ---
def get_hyperliquid_candles(symbol, interval, limit=250):
    try:
        # Conversion des intervalles pour Hyperliquid
        hl_intervals = {"5m": "5m", "15m": "15m", "1h": "1h"}
        hl_interval = hl_intervals.get(interval, "1h")
        
        url = "https://api.hyperliquid.xyz/info"
        headers = {"Content-Type": "application/json"}
        
        # Calcul du timestamp de départ pour avoir assez de bougies
        now_ms = int(time.time() * 1000) if 'time' in globals() else 1719792000000
        # Estimation large du recul nécessaire selon l'UT
        duration_ms = limit * 60 * 1000 if interval == "5m" else limit * 15 * 60 * 1000 if interval == "15m" else limit * 60 * 60 * 1000
        start_time = now_ms - duration_ms

        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": hl_interval,
                "startTime": start_time
            }
        }
        
        res = requests.post(url, json=payload, headers=headers, timeout=4).json()
        
        # Inversion car HL renvoie du plus récent au plus ancien
        df = pd.DataFrame(res)[::-1].reset_index(drop=True)
        df = df.rename(columns={'h': 'High', 'l': 'Low', 'c': 'Close'})
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        return df
    except:
        return None

# --- INDICATEURS MATHÉMATIQUES ---
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

# --- CHARGEMENT ---
data_1h, data_15m, data_5m = None, None, None

with st.spinner("Connexion directe aux carnets d'ordres..."):
    if api_source == "Binance (Spot)":
        df_1h = get_binance_candles(crypto_choice, "1h", limit=250)
        df_15m = get_binance_candles(crypto_choice, "15m", limit=50)
        df_5m = get_binance_candles(crypto_choice, "5m", limit=30)
    else:
        df_1h = get_hyperliquid_candles(crypto_choice, "1h", limit=250)
        df_15m = get_hyperliquid_candles(crypto_choice, "15m", limit=50)
        df_5m = get_hyperliquid_candles(crypto_choice, "5m", limit=30)

    if df_1h is not None and df_15m is not None and df_5m is not None:
        data_1h = compute_dmi_and_ema(df_1h, compute_ema=True)
        data_15m = compute_dmi_and_ema(df_15m)
        data_5m = compute_dmi_and_ema(df_5m)

# --- AFFICHAGE ---
if data_1h and data_15m and data_5m:
    st.caption(f"🟩 Connecté en direct à l'API officielle de {api_source}")
    
    is_macro_bull = data_1h["close"] > data_1h["EMA_200"]
    macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix {crypto_choice} en temps réel : **{round(data_5m['close'], 2)} $**")
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
else:
    st.error("Impossible de joindre l'API d'échange. Vérifie ton réseau.")

if st.button("🔄 Rafraîchir les cours"):
    st.rerun()
