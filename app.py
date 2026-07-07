import streamlit as st
import requests
import time
from services import get_forex_candles, get_okx_candles, get_coinbase_candles, compute_dmi_and_ema

st.set_page_config(page_title="FX & Crypto Flow Pro", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
    .metric-card { background-color: #1e222d; padding: 12px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #2f333e; }
    .tp-card { background-color: #14241c; padding: 10px; border-radius: 8px; border: 1px solid #00e676; margin-top: 5px; }
    .sl-card { background-color: #2a1919; padding: 10px; border-radius: 8px; border: 1px solid #ff5252; margin-top: 5px; }
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

# --- GESTION DU RAFRAÎCHISSEMENT AUTO EN ARRIÈRE-PLAN ---
st.sidebar.header("🔄 Automatisation")
auto_refresh = st.sidebar.toggle("Rafraîchissement Auto (30s)", value=True)

# Sélection du Marché
asset_type = st.radio("Type de marché :", ["Crypto", "Forex"], horizontal=True)

# --- GESTION DU RISQUE ---
st.sidebar.header("🎯 Gestion du Risque")
if asset_type == "Crypto":
    sl_pct = st.sidebar.slider("Stop Loss Crypto (%)", 0.2, 5.0, 1.0, 0.1)
    tp_pct = st.sidebar.slider("Take Profit Crypto (%)", 0.4, 10.0, 2.0, 0.1)
else:
    sl_pips = st.sidebar.slider("Stop Loss Forex (Pips)", 5, 100, 15, 5)
    tp_pips = st.sidebar.slider("Take Profit Forex (Pips)", 10, 200, 30, 5)

if asset_type == "Forex":
    fx_choice = st.selectbox("Paire Forex :", ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"])
    ticker_symbol = fx_choice
else:
    api_source = st.radio("Source Crypto :", ["Coinbase (Spot)", "OKX (Spot/Perps)"], horizontal=True)
    crypto_choice = st.selectbox("Actif Crypto :", ["BTC", "ETH", "SOL"])
    ticker_symbol = crypto_choice

adx_period = 14
adx_threshold = 20

# Récupération via le module Services
data_1h, data_15m, data_5m = None, None, None
with st.spinner("Synchronisation des flux..."):
    if asset_type == "Forex":
        df_1h = get_forex_candles(ticker_symbol)
        df_15m = get_forex_candles(ticker_symbol)
        df_5m = get_forex_candles(ticker_symbol)
    else:
        src = get_coinbase_candles if api_source == "Coinbase (Spot)" else get_okx_candles
        df_1h = src(ticker_symbol, "1h")
        df_15m = src(ticker_symbol, "15m")
        df_5m = src(ticker_symbol, "5m")

    data_1h = compute_dmi_and_ema(df_1h, adx_period, compute_ema=True)
    data_15m = compute_dmi_and_ema(df_15m, adx_period)
    data_5m = compute_dmi_and_ema(df_5m, adx_period)

# Affichage des structures
if data_1h and data_15m and data_5m:
    current_price = data_5m["close"]
    is_macro_bull = current_price > data_1h["EMA_200"]
    macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix actuel : **{round(current_price, 5 if asset_type == 'Forex' else 2)}**")
    
    # Horodatage de la dernière mise à jour pour le suivi sur ton smartphone
    st.caption(f"Dernière mise à jour du flux : {time.strftime('%H:%M:%S')}")
    st.write("---")
    
    buy_alignment = (data_5m["DI+"] > data_5m["DI-"] and data_5m["ADX"] > adx_threshold) and (data_15m["DI+"] > data_15m["DI-"] and data_15m["ADX"] > adx_threshold) and (data_1h["DI+"] > data_1h["DI-"] and data_1h["ADX"] > adx_threshold) and is_macro_bull
    sell_alignment = (data_5m["DI-"] > data_5m["DI+"] and data_5m["ADX"] > adx_threshold) and (data_15m["DI-"] > data_15m["DI+"] and data_15m["ADX"] > adx_threshold) and (data_1h["DI-"] > data_1h["DI+"] and data_1h["ADX"] > adx_threshold) and not is_macro_bull

    tp_price, sl_price = 0.0, 0.0
    
    if buy_alignment:
        if asset_type == "Crypto":
            sl_price = current_price * (1 - sl_pct / 100)
            tp_price = current_price * (1 + tp_pct / 100)
        else:
            pip_unit = 0.01 if "JPY" in ticker_symbol else 0.0001
            sl_price = current_price - (sl_pips * pip_unit)
            tp_price = current_price + (tp_pips * pip_unit)
            
        msg = f"🚀 *TRIPLE ALIGNEMENT ACHAT*\n• Actif : {ticker_symbol}\n• Entrée : {round(current_price, 5 if asset_type == 'Forex' else 2)}\n\n🟢 *PLAN :*\n🎯 TP : {round(tp_price, 5 if asset_type == 'Forex' else 2)}\n🛑 SL : {round(sl_price, 5 if asset_type == 'Forex' else 2)}"
        send_telegram_alert(msg)

    elif sell_alignment:
        if asset_type == "Crypto":
            sl_price = current_price * (1 + sl_pct / 100)
            tp_price = current_price * (1 - tp_pct / 100)
        else:
            pip_unit = 0.01 if "JPY" in ticker_symbol else 0.0001
            sl_price = current_price + (sl_pips * pip_unit)
            tp_price = current_price - (tp_pips * pip_unit)
            
        msg = f"💥 *TRIPLE ALIGNEMENT VENTE*\n• Actif : {ticker_symbol}\n• Entrée : {round(current_price, 5 if asset_type == 'Forex' else 2)}\n\n🔴 *PLAN :*\n🎯 TP : {round(tp_price, 5 if asset_type == 'Forex' else 2)}\n🛑 SL : {round(sl_price, 5 if asset_type == 'Forex' else 2)}"
        send_telegram_alert(msg)

    if buy_alignment or sell_alignment:
        st.markdown("### 🎯 Plan de Trade Calculé")
        st.markdown(f"""
            <div class="tp-card"><span style="color: #00e676; font-weight: bold;">🎯 TAKE PROFIT :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{round(tp_price, 5 if asset_type == 'Forex' else 2)}</span></div>
            <div class="sl-card"><span style="color: #ff5252; font-weight: bold;">🛑 STOP LOSS :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{round(sl_price, 5 if asset_type == 'Forex' else 2)}</span></div>
        """, unsafe_allow_html=True)
        st.write("---")

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
else:
    st.info("Sélectionne une source pour lancer l'analyse du flux.")

# Bouton d'actualisation manuelle traditionnel
if st.button("🔄 Actualiser manuellement"):
    st.rerun()

# --- BLOC D'INJECTION POUR LE REFRESH EN ARRIÈRE-PLAN (30 SECONDES) ---
if auto_refresh:
    time.sleep(30)
    st.rerun()
