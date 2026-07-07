import time
import requests
from services import get_forex_candles, get_okx_candles, get_coinbase_candles, compute_dmi_and_ema

# --- CONFIGURATION STRICTE ---
TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"

# Actifs à surveiller en permanence (Tu peux en rajouter dans la liste)
CRYPTO_WATCHLIST = ["BTC", "ETH", "SOL"]
ADX_THRESHOLD = 20

# Système anti-spam : Évite d'envoyer 50 alertes d'affilée pour le même signal
# Clé: "ACTIF_DIRECTION", Valeur: timestamp de la dernière alerte
last_alerts = {}
ALERT_COOLDOWN = 900  # 15 minutes de silence minimum entre deux alertes identiques

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print(f"[-] Erreur envoi Telegram : {e}")

print("[+] Le Bot algorithmique FX & Crypto Flow est démarré...")
print("[+] Mode surveillance H24 actif. En attente d'alignement Triple Écran...")

# Boucle infinie permanente (Parfait pour Railway)
while True:
    try:
        for symbol in CRYPTO_WATCHLIST:
            # 1. Extraction des bougies via le module services (Source stable: Coinbase)
            df_1h = get_coinbase_candles(symbol, "1h")
            df_15m = get_coinbase_candles(symbol, "15m")
            df_5m = get_coinbase_candles(symbol, "5m")
            
            if df_1h is None or df_15m is None or df_5m is None:
                continue
                
            # 2. Calcul des indicateurs de flux
            data_1h = compute_dmi_and_ema(df_1h, adx_period=14, compute_ema=True)
            data_15m = compute_dmi_and_ema(df_15m, adx_period=14)
            data_5m = compute_dmi_and_ema(df_5m, adx_period=14)
            
            if not data_1h or not data_15m or not data_5m:
                continue
                
            current_price = data_5m["close"]
            is_macro_bull = current_price > data_1h["EMA_200"]
            
            # 3. Vérification des conditions strictes du Triple Écran
            buy_alignment = (
                (data_5m["DI+"] > data_5m["DI-"] and data_5m["ADX"] > ADX_THRESHOLD) and
                (data_15m["DI+"] > data_15m["DI-"] and data_15m["ADX"] > ADX_THRESHOLD) and
                (data_1h["DI+"] > data_1h["DI-"] and data_1h["ADX"] > ADX_THRESHOLD) and
                is_macro_bull
            )
            
            sell_alignment = (
                (data_5m["DI-"] > data_5m["DI+"] and data_5m["ADX"] > ADX_THRESHOLD) and
                (data_15m["DI-"] > data_15m["DI+"] and data_15m["ADX"] > ADX_THRESHOLD) and
                (data_1h["DI-"] > data_1h["DI+"] and data_1h["ADX"] > ADX_THRESHOLD) and
                not is_macro_bull
            )
            
            current_time = time.time()
            
            # 4. Traitement du signal d'Achat Aligné
            if buy_alignment:
                alert_key = f"{symbol}_BUY"
                # On vérifie si on n'a pas déjà envoyé cette alerte récemment
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    # Calcul par défaut (SL 1%, TP 2%) en attendant demain
                    sl_price = current_price * 0.99
                    tp_price = current_price * 1.02
                    
                    msg = (
                        f"🚀 *[BOT H24] TRIPLE ALIGNEMENT ACHAT*\n"
                        f"• Actif : {symbol}\n"
                        f"• Entrée : {round(current_price, 2)}\n\n"
                        f"🟢 *PLAN DE RISK MANAGEMENT :*\n"
                        f"🎯 TARGET TP : {round(tp_price, 2)}\n"
                        f"🛑 STOP LOSS : {round(sl_price, 2)}"
                    )
                    send_telegram_alert(msg)
                    last_alerts[alert_key] = current_time
                    print(f"[+] Alerte Achat envoyée pour {symbol}")
                    
            # 5. Traitement du signal de Vente Alignée
            elif sell_alignment:
                alert_key = f"{symbol}_SELL"
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    sl_price = current_price * 1.01
                    tp_price = current_price * 0.98
                    
                    msg = (
                        f"💥 *[BOT H24] TRIPLE ALIGNEMENT VENTE*\n"
                        f"• Actif : {symbol}\n"
                        f"• Entrée : {round(current_price, 2)}\n\n"
                        f"🔴 *PLAN DE RISK MANAGEMENT :*\n"
                        f"🎯 TARGET TP : {round(tp_price, 2)}\n"
                        f"🛑 STOP LOSS : {round(sl_price, 2)}"
                    )
                    send_telegram_alert(msg)
                    last_alerts[alert_key] = current_time
                    print(f"[+] Alerte Vente envoyée pour {symbol}")

    except Exception as error:
        # En cas de micro-coupure réseau ou de timeout API, le script ne crash pas, il passe au tour suivant
        print(f"[-] Erreur temporaire boucle bot : {error}")
        
    # Pause de 30 secondes avant la prochaine vérification complète de la watchlist
    time.sleep(30)
