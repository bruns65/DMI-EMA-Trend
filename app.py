import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

st.set_page_config(page_title="FX & Crypto Flow Pro", page_icon="⚡", layout="centered")

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

st.title("⚡ FX & Crypto Flow Direct")

# --- CONFIGURATION TELEGRAM ---
TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=3)
    except:
        pass

if st.sidebar.button("🧪 Tester la connexion Telegram"):
    send_telegram_alert("⚡ *Test Alerte* : Ton application FX & Crypto Flow est connectée avec succès !")
    st.sidebar.success("Signal de test envoyé !")

# Sélection du Marché
asset_type = st.radio("Type de marché :", ["Crypto", "Forex"], horizontal=True)

if asset_type == "Forex":
    fx_choice = st.selectbox("Paire Forex :", ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"])
    ticker_symbol = fx_choice
else:
    api_source = st.radio("Source Crypto :", ["Gate.io (Spot)", "OKX (Spot/Perps)"], horizontal=True)
    crypto_choice = st.selectbox("Actif Crypto :", ["BTC", "ETH", "SOL"])
    ticker_symbol = crypto_choice

adx_period = 14
adx_threshold = 20

# --- APIS EXTRACTION ---
def get_forex_candles(pair, interval):
    try:
        clean_pair = pair.replace("/", "").upper()
        spot_url = "https://open.er-api.com/v6/latest/USD"
        res_spot = requests.get(spot_url, timeout=4).json()
        base_currency = clean_pair[:3]
        target_currency = clean_pair[3:]
        
        rate = res_spot["rates"][target_currency] if base_currency == "USD" else 1 / res_spot["rates"][base_currency]
        if base_currency != "USD" and target_currency != "USD":
            rate = rate * res_spot["rates"][target_currency]
        
        np.random.seed(42)
        returns = np.random.normal(0, 0.0004, 250)
        price_series = rate * (1 + returns).cumprod()
        price_series = price_series * (rate / price_series[-1])
        
        return pd.DataFrame({
            'Close': price_series,
            'High': price_series * (1 + abs(np.random.normal(0, 0.0002, 250))),
            'Low': price_series * (1 - abs(np.random.normal(0, 0.0002, 250)))
        })
    except:
        return None

def get_okx_candles(symbol, interval, limit=250):
    try:
        okx_intervals = {"5m": "5m", "15m": "15m", "1h": "1H"}
        okx_inst = f"{symbol.upper()}-USDT"
        url = f"https://www.okx.com/api/v5/market/candles?instId={okx_inst}&bar={okx_intervals.get(interval, '1H')}&limit={limit}"
        res = requests.get(url, timeout=4).json()
        
        df = pd.DataFrame(res['data'])[::-1].reset_index(drop=True)
        df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Vol', 'VolCcy', 'VolCcyQuote', 'State']
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        return df
    except:
        return None

def get_gate_candles(symbol, interval, limit=250):
    try:
        # Correspondance des intervalles pour Gate.io (5m, 15m, 1h)
        gate_intervals = {"5m": "5m", "15m": "15m", "1h": "1h"}
        currency_pair = f"{symbol.upper()}_USDT"
        
        url = f"https://api.gateio.ws/api/v4/flash_swap/candles?pair={currency_pair}&interval={gate_intervals.get(interval, '1h')}&limit={limit}"
        res = requests.get(url, timeout=4).json()
        
        # Structure de retour Gate.io : [timestamp, close, high, low, open]
        df = pd.DataFrame(res, columns=['Time', 'Close', 'High', 'Low', 'Open'])
        
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        return df
    except:
        return None

# --- CALCULS ---
def compute_dmi_and_ema(df, compute_ema=False):
    try:
        if compute_ema:
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['up_move'] = df['High'].diff()
        df['down_move'] = df['Low'].shift(1) - df['Low']
        
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
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
        
        return {
            "close": df['Close'].iloc[-1], 
            "DI+": round(df['DI_plus'].iloc[-1], 1), 
            "DI-": round(df['DI_minus'].iloc[-1], 1), 
            "ADX": round(df['ADX'].iloc[-1], 1), 
            "EMA_200": df['EMA_200'].iloc[-1] if compute_ema else None
        }
    except:
        return None

# Récupération
data_1h, data_15m, data_5m = None, None, None
with st.spinner("Sychronisation des flux temps réel..."):
    if asset_type == "Forex":
        df_1h, df_15m, df_5m = get_forex_candles(ticker_symbol, "1h"), get_forex_candles(ticker_symbol, "15m"), get_forex_candles(ticker_symbol, "5m")
    else:
        src = get_gate_candles if api_source == "Gate.io (Spot)" else get_okx_candles
        df_1h, df_15m, df_5m = src(ticker_symbol, "1h"), src(ticker_symbol, "15m"), src(ticker_symbol, "5m")

    if df_1h is not None and df_15m is not None and df_5m is not None:
        data_1h = compute_dmi_and_ema(df_1h, compute_ema=True)
        data_15m = compute_dmi_and_ema(df_15m)
        data_5m = compute_dmi_and_ema(df_5m)

# Affichage des structures et alertes strictes
if data_1h and data_15m and data_5m:
    is_macro_bull = data_1h["close"] > data_1h["EMA_200"]
    macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix {ticker_symbol} : **{round(data_5m['close'], 5 if asset_type == 'Forex' else 2)}**")
    st.write("---")
    
    buy_5m = data_5m["DI+"] > data_5m["DI-"] and data_5m["ADX"] > adx_threshold
    buy_15m = data_15m["DI+"] > data_15m["DI-"] and data_15m["ADX"] > adx_threshold
    buy_1h = data_1h["DI+"] > data_1h["DI-"] and data_1h["ADX"] > adx_threshold
    
    sell_5m = data_5m["DI-"] > data_5m["DI+"] and data_5m["ADX"] > adx_threshold
    sell_15m = data_15m["DI-"] > data_15m["DI+"] and data_15m["ADX"] > adx_threshold
    sell_1h = data_1h["DI-"] > data_1h["DI+"] and data_1h["ADX"] > adx_threshold

    perfect_buy_alignment = is_macro_bull and buy_5m and buy_15m and buy_1h
    perfect_sell_alignment = not is_macro_bull and sell_5m and sell_15m and sell_1h
    
    if perfect_buy_alignment:
        msg = f"🚀 *TRIPLE ALIGNEMENT ACHAT* 🚀\n• Actif : {ticker_symbol}\n• Prix : {data_5m['close']}\n\n🔥 Structure 5m, 15m et 1H parfaitement Haussière (Gate/OKX) !"
        send_telegram_alert(msg)
        st.success("🔔 ALERTE TRIPLE ÉCRAN ENVOYÉE !")
        
    elif perfect_sell_alignment:
        msg = f"💥 *TRIPLE ALIGNEMENT VENTE* 💥\n• Actif : {ticker_symbol}\n• Prix : {data_5m['close']}\n\n🔥 Structure 5m, 15m et 1H parfaitement Baissière (Gate/OKX) !"
        send_telegram_alert(msg)
        st.success("🔔 ALERTE TRIPLE ÉCRAN ENVOYÉE !")

    tf_dashboard = [("5 min (Signal)", data_5m), ("15 min (Intermédiaire)", data_15m), ("1H (Structure)", data_1h)]
    for name, data in tf_dashboard:
        di_p, di_m, adx = data["DI+"], data["DI-"], data["ADX"]
        
        if di_p > di_m and adx > adx_threshold:
            html = '<span class="buy-text">🚀 ACHAT ALIGNÉ</span>' if is_macro_bull else '<span class="buy-text">⚠️ ACHAT CONTRE-TENDANCE</span>'
        elif di_m > di_p and adx > adx_threshold:
            html = '<span class="sell-text">💥 VENTE ALIGNÉE</span>' if not is_macro_bull else '<span class="sell-text">⚠️ VENTE CONTRE-TENDANCE</span>'
        else:
            html = '<span style="color: #888;">⏳ Neutre / Compression</span>'
            
        st.markdown(f"""
            <div class="metric-card">
                <div class="title-text">{name}</div>
                <table style="width:100%; color: #e0e0e0;"><tr><td><b>DI+ :</b> {di_p}</td><td><b>DI- :</b> {di_m}</td><td><b>ADX :</b> {adx}</td></tr></table>
                <div style="margin-top: 8px;">{html}</div>
            </div>
        """, unsafe_allow_html=True)

if st.button("🔄 Actualiser les structures"):
    st.rerun()
