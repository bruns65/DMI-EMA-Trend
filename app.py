import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
from services import get_forex_candles, get_okx_candles, get_coinbase_candles, compute_dmi_and_ema

st.set_page_config(page_title="FX & Crypto Flow Pro", page_icon="⚡", layout="centered")

# --- STYLE CSS REVISITÉ ---
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

# --- INITIALISATION DE LA MÉMOIRE INTERNE (PAPER TRADING & ANTI-SPAM) ---
if "open_trades" not in st.session_state:
    st.session_state.open_trades = {}  # Format: { "SOL": {"side": "SELL", "entry": 78.07, "tp": 76.51, "sl": 78.85, "time": "08:47", "has_be": False} }
if "closed_trades" not in st.session_state:
    st.session_state.closed_trades = []
if "last_alerts" not in st.session_state:
    st.session_state.last_alerts = {}  # Anti-spam Telegram

# --- CONFIGURATION TELEGRAM ---
TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"
ALERT_COOLDOWN = 900  # 15 minutes (900 secondes) de silence après une alerte

def send_telegram_alert(message, asset_key):
    """ Envoie l'alerte uniquement si le délai de cooldown est expiré """
    current_time = time.time()
    last_time = st.session_state.last_alerts.get(asset_key, 0)
    
    if current_time - last_time > ALERT_COOLDOWN:
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=3)
            st.session_state.last_alerts[asset_key] = current_time  # Verrouillage du cooldown
        except:
            pass

# --- NAVIGATION ONGLES ---
tab_flux, tab_journal = st.tabs(["⚡ Flux & Signaux", "📋 Journal de Paper Trading"])

# --- CONFIGURATION SIDEBAR ---
st.sidebar.header("🔄 Automatisation")
auto_refresh = st.sidebar.toggle("Rafraîchissement Auto (30s)", value=True)

st.sidebar.header("🎯 Gestion du Risque")
sl_pct = st.sidebar.slider("Stop Loss Crypto (%)", 0.2, 5.0, 1.0, 0.1)
tp_pct = st.sidebar.slider("Take Profit Crypto (%)", 0.4, 10.0, 2.0, 0.1)

# Configuration actifs fixes (Mode simplifié)
ticker_symbol = st.sidebar.selectbox("Actif à analyser :", ["SOL", "BTC", "ETH"])
api_source = "Coinbase (Spot)"
adx_period = 14
adx_threshold = 20

# --- MOTEUR DE FLUX INTERNE ---
with st.spinner("Mise à jour des carnets..."):
    df_1h = get_coinbase_candles(ticker_symbol, "1h")
    df_15m = get_coinbase_candles(ticker_symbol, "15m")
    df_5m = get_coinbase_candles(ticker_symbol, "5m")

    data_1h = compute_dmi_and_ema(df_1h, adx_period, compute_ema=True)
    data_15m = compute_dmi_and_ema(df_15m, adx_period)
    data_5m = compute_dmi_and_ema(df_5m, adx_period)

# --- REFRESH DES TRADES EN COURS (SUIVI DES COMPTES SIMULÉS) ---
if data_5m:
    current_price = data_5m["close"]
    
    # Si l'actif sélectionné est actuellement en position ouverte, on gère son évolution
    if ticker_symbol in st.session_state.open_trades:
        trade = st.session_state.open_trades[ticker_symbol]
        entry = trade["entry"]
        side = trade["side"]
        
        # 1. Calcul de la performance
        perf = (entry - current_price) / entry if side == "SELL" else (current_price - entry) / entry
        
        # 2. Gestion du Breakeven automatique (dès +1% de hausse)
        if perf >= 0.01 and not trade["has_be"]:
            st.session_state.open_trades[ticker_symbol]["has_be"] = True
            if side == "SELL":
                st.session_state.open_trades[ticker_symbol]["sl"] = entry  # SL ramené à l'entrée
            else:
                st.session_state.open_trades[ticker_symbol]["sl"] = entry
            send_telegram_alert(f"🛡️ *[PAPER] BREAKEVEN APPLIQUÉ*\n• {ticker_symbol} ({side}) sécurisé à {entry}$. Risk = 0$.", f"{ticker_symbol}_BE")

        # 3. Vérification des conditions de sortie (TP ou SL touché)
        hit_tp = (side == "SELL" and current_price <= trade["tp"]) or (side == "BUY" and current_price >= trade["tp"])
        hit_sl = (side == "SELL" and current_price >= trade["sl"]) or (side == "BUY" and current_price <= trade["sl"])
        
        if hit_tp or hit_sl:
            resultat = "🎯 TP TOUCHÉ" if hit_tp else ("🛡️ BE TOUCHÉ" if trade["has_be"] else "🔴 SL TOUCHÉ")
            pnl_final = "+40.00$" if hit_tp else ("0.00$" if trade["has_be"] else "-20.00$")
            
            # Archiver dans le journal clos
            st.session_state.closed_trades.append({
                "Date": datetime.now().strftime("%d/%m %H:%M"),
                "Actif": ticker_symbol,
                "Type": side,
                "Entrée": entry,
                "Sortie": current_price,
                "Résultat": resultat,
                "Gain/Perte": pnl_final
            })
            # Supprimer des positions ouvertes
            del st.session_state.open_trades[ticker_symbol]

# ==========================================================
#  ONGLET 1 : INTERFACE DE SURVEILLANCE DES FLUX
# ==========================================================
with tab_flux:
    st.title("⚡ FX & Crypto Flow Direct")
    
    if data_1h and data_15m and data_5m:
        current_price = data_5m["close"]
        is_macro_bull = current_price > data_1h["EMA_200"]
        macro_status = "🟩 HAUSSIER" if is_macro_bull else "🟥 BAISSIER"
        
        st.subheader(f"Tendance Macro 1H : {macro_status}")
        st.write(f"Prix actuel de {ticker_symbol} : **{round(current_price, 2)} $**")
        st.caption(f"Dernière mise à jour : {time.strftime('%H:%M:%S')}")
        st.write("---")
        
        # Algorithme d'alignement Triple Écran
        buy_alignment = (data_5m["DI+"] > data_5m["DI-"] and data_5m["ADX"] > adx_threshold) and (data_15m["DI+"] > data_15m["DI-"] and data_15m["ADX"] > adx_threshold) and (data_1h["DI+"] > data_1h["DI-"] and data_1h["ADX"] > adx_threshold) and is_macro_bull
        sell_alignment = (data_5m["DI-"] > data_5m["DI+"] and data_5m["ADX"] > adx_threshold) and (data_15m["DI-"] > data_15m["DI+"] and data_15m["ADX"] > adx_threshold) and (data_1h["DI-"] > data_1h["DI+"] and data_1h["ADX"] > adx_threshold) and not is_macro_bull

        # Calcul des cibles théoriques
        if is_macro_bull:
            sl_price = round(current_price * (1 - sl_pct / 100), 2)
            tp_price = round(current_price * (1 + tp_pct / 100), 2)
        else:
            sl_price = round(current_price * (1 + sl_pct / 100), 2)
            tp_price = round(current_price * (1 - tp_pct / 100), 2)

        # Déclenchement automatique du Paper Trade et envoi Telegram (Une seule fois grâce au cooldown)
        if buy_alignment and ticker_symbol not in st.session_state.open_trades:
            st.session_state.open_trades[ticker_symbol] = {"side": "BUY", "entry": current_price, "tp": tp_price, "sl": sl_price, "time": time.strftime('%H:%M'), "has_be": False}
            msg = f"🚀 *TRIPLE ALIGNEMENT ACHAT*\n• Actif : {ticker_symbol}\n• Entrée : {current_price}\n\n🟢 *PLAN :*\n🎯 TP : {tp_price}\n🛑 SL : {sl_price}"
            send_telegram_alert(msg, f"{ticker_symbol}_BUY")

        elif sell_alignment and ticker_symbol not in st.session_state.open_trades:
            st.session_state.open_trades[ticker_symbol] = {"side": "SELL", "entry": current_price, "tp": tp_price, "sl": sl_price, "time": time.strftime('%H:%M'), "has_be": False}
            msg = f"💥 *TRIPLE ALIGNEMENT VENTE*\n• Actif : {ticker_symbol}\n• Entrée : {current_price}\n\n🔴 *PLAN :*\n🎯 TP : {tp_price}\n🛑 SL : {sl_price}"
            send_telegram_alert(msg, f"{ticker_symbol}_SELL")

        # Affichage du Plan Actif à l'écran
        if buy_alignment or sell_alignment or (ticker_symbol in st.session_state.open_trades):
            st.markdown("### 🎯 Plan de Trade Détecté / Actif")
            st.markdown(f"""
                <div class="tp-card"><span style="color: #00e676; font-weight: bold;">🎯 TAKE PROFIT :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{tp_price} $</span></div>
                <div class="sl-card"><span style="color: #ff5252; font-weight: bold;">🛑 STOP LOSS :</span> <span style="font-size: 18px; color: #fff; font-weight: bold;">{sl_price} $</span></div>
            """, unsafe_allow_html=True)
            st.write("---")

        # Rendu des boîtes de Timeframes
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

# ==========================================================
#  ONGLET 2 : JOURNAL DE PAPER TRADING (ORDRES SIMULÉS)
# ==========================================================
with tab_journal:
    st.title("📋 Journal des Trades Simulés (Risque 0$)")
    
    st.subheader("🌐 Position Actuellement Ouverte")
    if st.session_state.open_trades:
        open_data = []
        for k, v in st.session_state.open_trades.items():
            # Recalcul des gains latents en direct à l'écran
            if data_5m and k == ticker_symbol:
                p_actuel = data_5m["close"]
                gain_lat = ((v["entry"] - p_actuel) / v["entry"]) * 2000 if v["side"] == "SELL" else ((p_actuel - v["entry"]) / v["entry"]) * 2000
                gain_text = f"{round(gain_lat, 2)} $"
            else:
                gain_text = "Calcul au prochain refresh..."
                
            open_data.append({
                "Heure": v["time"], "Actif": k, "Type": v["side"], 
                "Prix Entrée": v["entry"], "Objectif TP": v["tp"], 
                "Stop Loss": f"🛡️ BE ({v['sl']})" if v["has_be"] else v["sl"],
                "Profit Latent": gain_text
            })
        st.table(pd.DataFrame(open_data))
    else:
        st.info("Aucun trade actif pour le moment. Le système attend un alignement parfait.")
        
    st.write("---")
    st.subheader("📚 Historique des Trades Clôturés")
    if st.session_state.closed_trades:
        st.table(pd.DataFrame(st.session_state.closed_trades))
    else:
        st.caption("L'historique est vide. Les trades terminés s'afficheront ici automatiquement.")

# --- COMMANDE REFRESH ---
if auto_refresh:
    time.sleep(30)
    st.rerun()
