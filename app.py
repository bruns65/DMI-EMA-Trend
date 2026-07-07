import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

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

# Extraction propre de la Tendance de Fond (1H) avec EMA 200
def get_macro_trend(ticker):
    try:
        # Période passée à 3mo pour garantir plus de 200 bougies horaires
        df_1h = yf.Ticker(ticker).history(interval="1h", period="3mo")
        if df_1h.empty or len(df_1h) < 200:
            return None, None
            
        ema_200 = ta.ema(df_1h['Close'], length=200)
        dmi_1h = ta.adx(df_1h['High'], df_1h['Low'], df_1h['Close'], length=adx_period)
        
        return {
            "close": df_1h['Close'].iloc[-1],
            "EMA_200": ema_200.iloc[-1],
            "DI+": round(dmi_1h[f"DMP_{adx_period}"].iloc[-1], 1),
            "DI-": round(dmi_1h[f"DMN_{adx_period}"].iloc[-1], 1),
            "ADX": round(dmi_1h[f"ADX_{adx_period}"].iloc[-1], 1)
        }, df_1h['Close'].iloc[-1]
    except:
        return None, None

# Extraction chirurgicale des petites UT (5m et 15m) pour le DMI pur
def get_scalping_dmi(ticker, tf):
    try:
        df = yf.Ticker(ticker).history(interval=tf, period="5d")
        if df.empty or len(df) < adx_period:
            return None
        dmi = ta.adx(df['High'], df['Low'], df['Close'], length=adx_period)
        return {
            "DI+": round(dmi[f"DMP_{adx_period}"].iloc[-1], 1),
            "DI-": round(dmi[f"DMN_{adx_period}"].iloc[-1], 1),
            "ADX": round(dmi[f"ADX_{adx_period}"].iloc[-1], 1)
        }
    except:
        return None

# --- CRÉATION DE L'INTERFACE EN DIRECT ---
with st.spinner("Calcul des structures de flux..."):
    macro_data, current_price = get_macro_trend(ticker_symbol)
    data_15m = get_scalping_dmi(ticker_symbol, "15m")
    data_5m = get_scalping_dmi(ticker_symbol, "5m")

if macro_data and data_15m and data_5m:
    is_macro_bull = macro_data["close"] > macro_data["EMA_200"]
    macro_status = "🟩 HAUSSIER (Prix > EMA200)" if is_macro_bull else "🟥 BAISSIER (Prix < EMA200)"
    
    st.subheader(f"Tendance Macro 1H : {macro_status}")
    st.write(f"Prix en direct : **{round(current_price, 5)}**")
    st.write("---")
    
    tf_dashboard = [
        ("5 min (Signal)", data_5m),
        ("15 min (Intermédiaire)", data_15m),
        ("1H (Structure)", {"DI+": macro_data["DI+"], "DI-": macro_data["DI-"], "ADX": macro_data["ADX"]})
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
    st.error("Calcul impossible. Si nous sommes le week-end, assure-toi de sélectionner 'Crypto' car les marchés Forex sont fermés.")
