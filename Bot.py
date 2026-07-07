import time
import requests
from eth_account import Account
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from services import get_forex_candles, get_okx_candles, get_coinbase_candles, compute_dmi_and_ema

# ==========================================
#  🔴 CONFIGURATION STRICTE & SÉCURISÉE
# ==========================================
# Identifiants Telegram
TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"

# Identifiants de trading Hyperliquid (À migrer en variables d'environnement sur Railway !)
ACCOUNT_ADDRESS = "VOTRE_ADRESSE_DE_PORTEFEUILLE_ICI"
# Recommandation : Utilisez une clé d'un "API Agent" généré sur Hyperliquid plutôt que votre clé privée principale
API_SECRET_KEY = "VOTRE_CLE_PRIVEE_OU_CLE_AGENT_ICI"

# Paramètres de Risk Management
RISK_PER_TRADE_USD = 20.0  # Risque strict de 1% sur un capital de 2000$
SL_PCT_CRYPTO = 0.01       # Distance du Stop Loss par défaut : 1% (0.01)
TP_PCT_CRYPTO = 0.02       # Distance du Take Profit par défaut : 2% (0.02)

# Watchlist et paramètres algorithmiques
CRYPTO_WATCHLIST = ["BTC", "ETH", "SOL"]
ADX_THRESHOLD = 20
ALERT_COOLDOWN = 900       # 15 minutes de silence pour éviter le spam
last_alerts = {}

# Initialisation des modules Hyperliquid (Mainnet)
try:
    account = Account.from_key(API_SECRET_KEY)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    print(f"[+] Connexion Hyperliquid validée pour l'adresse : {account.address}")
except Exception as e:
    print(f"[-] Échec de l'initialisation Hyperliquid : {e}")

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=3)
    except Exception as e:
        print(f"[-] Erreur Telegram : {e}")

def execute_hyperliquid_trade(symbol, side, current_price):
    """
    Calcule la taille de position dynamique, ouvre un ordre au marché,
    puis place immédiatement le TP et le SL associés.
    """
    try:
        print(f"[+ Action] Tentative d'ouverture de position {side} sur {symbol}...")
        
        # 1. Calcul de la taille de lot dynamique (Position Sizing)
        # Formule : Taille du contrat = Risque en $ / Écart du SL en $
        sl_distance_usd = current_price * SL_PCT_CRYPTO
        position_size_token = RISK_PER_TRADE_USD / sl_distance_usd
        
        # Arrondir la taille du lot selon les spécifications d'Hyperliquid (ex: BTC accepte 5 décimales, SOL moins)
        # Par sécurité pour l'implémentation, on utilise un arrondi standard à 3 décimales adaptées aux majeures
        position_size_token = round(position_size_token, 3)
        
        if position_size_token <= 0:
            print("[-] Taille de lot calculée trop faible.")
            return False

        # 2. Envoi de l'ordre principal au marché (Market Order)
        is_buy = (side == "BUY")
        market_order_result = exchange.market_open(symbol, is_buy, position_size_token, slippage=0.01)
        
        if market_order_result["status"] != "ok":
            print(f"[-] Échec de l'ordre Market : {market_order_result}")
            return False
            
        print(f"[+] Ordre Market exécuté avec succès : {side} {position_size_token} {symbol}")

        # 3. Calcul des prix exacts pour les ordres de protection
        if is_buy:
            sl_price = round(current_price * (1 - SL_PCT_CRYPTO), 2)
            tp_price = round(current_price * (1 + TP_PCT_CRYPTO), 2)
        else:
            sl_price = round(current_price * (1 + SL_PCT_CRYPTO), 2)
            tp_price = round(current_price * (1 - TP_PCT_CRYPTO), 2)

        # 4. Placement du Stop Loss (Ordre de type Trigger / Stop Market)
        # Sur Hyperliquid perps, pour fermer un achat, le SL doit être un ordre de vente (is_buy = False)
        exchange.order(symbol, not is_buy, position_size_token, sl_price, {"trigger": {"isMarket": True, "triggerPx": sl_price, "tpsl": "sl"}})
        print(f"[+] Ordre de protection STOP LOSS placé à : {sl_price}")

        # 5. Placement du Take Profit (Ordre de type Trigger / Take Profit Market)
        exchange.order(symbol, not is_buy, position_size_token, tp_price, {"trigger": {"isMarket": True, "triggerPx": tp_price, "tpsl": "tp"}})
        print(f"[+] Ordre de protection TAKE PROFIT placé à : {tp_price}")
        
        return tp_price, sl_price, position_size_token

    except Exception as trade_error:
        print(f"[-] Erreur critique lors de l'exécution sur Hyperliquid : {trade_error}")
        return False

# ==========================================
#  🔄 BOUCLE DE SURVEILLANCE PERMANENTE (H24)
# ==========================================
print("[+] Le Bot FX & Crypto Flow avec exécution Hyperliquid est opérationnel.")

while True:
    try:
        for symbol in CRYPTO_WATCHLIST:
            # Récupération des bougies complètes et figées via Coinbase
            df_1h = get_coinbase_candles(symbol, "1h")
            df_15m = get_coinbase_candles(symbol, "15m")
            df_5m = get_coinbase_candles(symbol, "5m")
            
            if df_1h is None or df_15m is None or df_5m is None:
                continue
                
            data_1h = compute_dmi_and_ema(df_1h, adx_period=14, compute_ema=True)
            data_15m = compute_dmi_and_ema(df_15m, adx_period=14)
            data_5m = compute_dmi_and_ema(df_5m, adx_period=14)
            
            if not data_1h or not data_15m or not data_5m:
                continue
                
            current_price = data_5m["close"]
            is_macro_bull = current_price > data_1h["EMA_200"]
            
            # Filtre strict du Triple Écran
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
            
            # Signal d'Achat détecté
            if buy_alignment:
                alert_key = f"{symbol}_BUY"
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    
                    # ENVOI DE L'ORDRE REEL
                    trade_success = execute_hyperliquid_trade(symbol, "BUY", current_price)
                    
                    if trade_success:
                        tp_p, sl_p, size_t = trade_success
                        msg = (
                            f"🤖 *[BOT AUTOMATIQUE] POSITION LONG OUVERTE*\n"
                            f"• Actif : {symbol}\n"
                            f"• Entrée exécutée : {round(current_price, 2)}\n"
                            f"• Taille du contrat : {size_t} {symbol}\n\n"
                            f"🟢 *SÉCURISATION :*\n"
                            f"🎯 TAKE PROFIT : {tp_p}\n"
                            f"🛑 STOP LOSS (Risque 20$) : {sl_p}"
                        )
                        send_telegram_alert(msg)
                        last_alerts[alert_key] = current_time
                    
            # Signal de Vente détecté
            elif sell_alignment:
                alert_key = f"{symbol}_SELL"
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    
                    # ENVOI DE L'ORDRE REEL
                    trade_success = execute_hyperliquid_trade(symbol, "SELL", current_price)
                    
                    if trade_success:
                        tp_p, sl_p, size_t = trade_success
                        msg = (
                            f"🤖 *[BOT AUTOMATIQUE] POSITION SHORT OUVERTE*\n"
                            f"• Actif : {symbol}\n"
                            f"• Entrée exécutée : {round(current_price, 2)}\n"
                            f"• Taille du contrat : {size_t} {symbol}\n\n"
                            f"🔴 *SÉCURISATION :*\n"
                            f"🎯 TAKE PROFIT : {tp_p}\n"
                            f"🛑 STOP LOSS (Risque 20$) : {sl_p}"
                        )
                        send_telegram_alert(msg)
                        last_alerts[alert_key] = current_time

    except Exception as loop_error:
        print(f"[-] Erreur boucle principale : {loop_error}")
        
    time.sleep(30)
