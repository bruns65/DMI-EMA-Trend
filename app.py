import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
from services import get_coinbase_candles, compute_dmi_and_ema

st.set_page_config(page_title="FX & Crypto Flow Pro", page_icon="⚡", layout="centered")

# --- CUSTOM CSS ---
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

# --- SESSIONS STATE ---
if "open_trades" not in st.session_state:
    st.session_state.open_trades = {}
if "closed_trades" not in st.session_state:
    st.session_state.closed_trades = []
if "last_alerts" not in st.session_state:
    st.session_state.last_alerts = {}

TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"
ALERT_COOLDOWN = 900 

def send_telegram_alert(message, asset_key):
    current_time = time.time()
    last_time = st.session_state.last_alerts.get(asset_key, 0)
    if current_time - last_time > ALERT_COOLDOWN:
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=3)
            st.session_state.last_alerts[asset_key] = current_time
        except:
            pass

# --- INTERFACE ---
tab_flux, tab_journal = st.tabs(["⚡ Moteur Flash", "📋 Journal Paper Trading"])

st.sidebar.header("🔄 Automatisation")
auto_refresh = st.sidebar.toggle("Rafraîchissement Auto (30s)", value=True)

st.sidebar.header("🎯 Risk Management")
sl_pct = st.sidebar.slider("Stop Loss (%)", 0.2, 5.0, 1.0, 0.1)
tp_pct = st.sidebar.slider("Take Profit (%)", 0.4, 10.0, 2.0, 0.1)

ticker_symbol = st.sidebar.selectbox("Actif à surveiller :", ["SOL", "BTC", "ETH"])

# Extraction des données
with st.spinner("Analyse du flux..."):
    df_1h = get_coinbase_candles(ticker_symbol, "1h")
    df_15m = get_coinbase_candles(ticker_symbol, "15m")
    df_5m = get_coinbase_candles(ticker_symbol, "5m")

    data_1h = compute_dmi_and_ema(df_1h, compute_ema=True)
    data_15m = compute_dmi_and_ema(df_15m)
    data_5m = compute_dmi_and_ema(df_5m)

# --- ENGINE DE SUIVI DES POSITIONS ---
if data_5m:
    current_price = data_5m["close"]
    
    if ticker_symbol in st.session_state.open_trades:
        trade = st.session_state.open_trades[ticker_symbol]
        entry = trade["entry"]
        side = trade["side"]
        
        perf = (entry - current_price) / entry if side == "SELL" else (current_price - entry) / entry
        
        # Traitement automatique du Breakeven à +1% de profit latent
        if perf >= 0.01 and not trade["has_be"]:
            st.session_state.open_trades[ticker_symbol]["has_be"] = True
            st.session_state.open_trades[ticker_symbol]["sl"] = entry
            send_telegram_alert(f"🛡️ *[PRECOCE] BREAKEVEN SELECTIONNÉ*\n• {ticker_symbol} ({side}) sécurisé à {entry}$. Risk = 0$.", f"{ticker_symbol}_BE")

        # Exécution des sorties
        hit_tp = (side == "SELL" and current_price <= trade["tp"]) or (side == "BUY" and current_price >= trade["tp"])
        hit_sl = (side == "SELL" and current_price >= trade["sl"]) or (side == "BUY" and current_price <= trade["sl"])
        
        if hit_tp or hit_sl:
            res = "🎯 TP ATTEINT" if hit_tp else ("🛡️ BE TOUCHÉ" if trade["has_be"] else "🔴 SL TOUCHÉ")
            pnl = "+40.00$" if hit_tp else ("0.00$" if trade["has_be"] else "-20.00$")
            
            st.session_state.closed_trades.append({
                "Date": datetime.now().strftime("%d/%m %H:%M"), "Actif": ticker_symbol,
                "Type": side, "Entrée": entry, "Sortie": current_price, "Résultat": res, "PnL": pnl
            })
            del st.session_state.open_trades[ticker_symbol]

# ==========================================
#  ONGLET 1 : FILTRE DE SIGNAL D'ENTRÉE FLASH
# ==========================================
with tab_flux:
    st.title("⚡ Détecteur de Flux Flash")
    
    if data_1h and data_15m and data_5m:
        current_price = data_5m["close"]
        is_macro_bull = current_price > data_1h["EMA_200"]
        macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
        
        st.subheader(f"Tendance Macro 1H : {macro_status}")
        st.write(f"Prix actuel {ticker_symbol} : **{round(current_price, 2)} $**")
        st.caption(f"Dernier scan : {time.strftime('%H:%M:%S')}")
        
        # ----------------------------------------------------
        # 🔥 LES CONDITIONS CHIRURGICALES DE TON ÉCRAN 🔥
        # ----------------------------------------------------
        # La pente de l'ADX 15m doit être ascendante (l'ADX augmente)
        adx_is_growing_15m = data_15m["ADX"] > data_15m["ADX_prev"]
        
        # Condition LONG : Cross MM Haussier + Stoch RSI Surchauffé (>80) + Pente ADX en hausse + Macro Bull
        flash_long = (data_5m["EMA_10"] > data_5m["MA_10"]) and (data_5m["StochRSI_K"] >= 80.0) and adx_is_growing_15m and is_macro_bull
        
        # Condition SHORT : Cross MM Baissier + Stoch RSI Écrasé (<=10) + Pente ADX en hausse + Macro Bear
        flash_short = (data_5m["EMA_10"] < data_5m["MA_10"]) and (data_5m["StochRSI_K"] <= 10.0) and adx_is_growing_15m and not is_macro_bull
        # ----------------------------------------------------

        if is_macro_bull:
            sl_price = round(current_price * (1 - sl_pct / 100), 2)
            tp_price = round(current_price * (1 + tp_pct / 100), 2)
        else:
            sl_price = round(current_price * (1 + sl_pct / 100), 2)
            tp_price = round(current_price * (1 - tp_pct / 100), 2)

        # Enregistrement Automatique du Paper Trade
        if flash_long and ticker_symbol not in st.session_state.open_trades:
            st.session_state.open_trades[ticker_symbol] = {"side": "BUY", "entry": current_price, "tp": tp_price, "sl": sl_price, "time": time.strftime('%H:%M'), "has_be": False}
            send_telegram_alert(f"🚀 *[SIGNAL FLASH BUY]*\n• Actif : {ticker_symbol}\n• Entrée : {current_price}$\n🎯 TP : {tp_price}$\n🛑 SL : {sl_price}$", f"{ticker_symbol}_BUY")
        elif flash_short and ticker_symbol not in st.session_state.open_trades:
            st.session_state.open_trades[ticker_symbol] = {"side": "SELL", "entry": current_price, "tp": tp_price, "sl": sl_price, "time": time.strftime('%H:%M'), "has_be": False}
            send_telegram_alert(f"💥 *[SIGNAL FLASH SHORT]*\n• Actif : {ticker_symbol}\n• Entrée : {current_price}$\n🎯 TP : {tp_price}$\n🛑 SL : {sl_price}$", f"{ticker_symbol}_SELL")

        # Rendu Visuel des Cibles
        if flash_long or flash_short or (ticker_symbol in st.session_state.open_trades):
            st.markdown("### 🎯 Paramètres du Trade En Cours")
            st.markdown(f"""
                <div class="tp-card"><span style="color: #00e676; font-weight: bold;">🎯 TARGET TP :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{tp_price} $</span></div>
                <div class="sl-card"><span style="color: #ff5252; font-weight: bold;">🛑 STOP LOSS :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{sl_price} $</span></div>
            """, unsafe_allow_html=True)

        st.write("---")
        
        # Bloc d'état des sous-indicateurs à l'écran
        st.markdown("### 📊 État des Signaux Précoces (5 min)")
        st.write(f"• **Position Moyennes Mobiles (10) :** {'🟢 EMA > MA (Achat)' if data_5m['EMA_10'] > data_5m['MA_10'] else '🔴 EMA < MA (Vente)'}")
        st.write(f"• **Stoch RSI %K :** `{data_5m['StochRSI_K']}` (Recherché: >=80 pour Long, <=10 pour Short)")
        st.write(f"• **Dynamique ADX 15m :** {'📈 En Hausse (Force augmente)' if adx_is_growing_15m else '📉 En Baisse (Compression)'} | Valeur : `{data_15m['ADX']}`")

# ==========================================
#  ONGLET 2 : LE JOURNAL DE CONTROLE
# ==========================================
with tab_journal:
    st.title("📋 Tableau de Bord de Simulation")
    
    st.subheader("🌐 Position Active")
    if st.session_state.open_trades:
        open_data = []
        for k, v in st.session_state.open_trades.items():
            if data_5m and k == ticker_symbol:
                p_actuel = data_5m["close"]
                gain_lat = ((v["entry"] - p_actuel) / v["entry"]) * 2000 if v["side"] == "SELL" else ((p_actuel - v["entry"]) / v["entry"]) * 2000
                gain_text = f"{round(gain_lat, 2)} $"
            else:
                gain_text = "En attente..."
                
            open_data.append({
                "Heure": v["time"], "Actif": k, "Type": v["side"], "Entrée": v["entry"], "Objectif TP": v["tp"], 
                "Stop Loss": f"🛡️ BE ({v['sl']})" if v["has_be"] else v["sl"], "Profit Latent": gain_text
            })
        st.table(pd.DataFrame(open_data))
    else:
        st.info("Aucun ordre simulé actif. Le filtre rejette le bruit.")
        
    st.write("---")
    st.subheader("📚 Historique Clos")
    if st.session_state.closed_trades:
        st.table(pd.DataFrame(st.session_state.closed_trades))
    else:
        st.caption("Aucune position archivée pour le moment.")

if auto_refresh:
    time.sleep(30)
    st.rerun()
