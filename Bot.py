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
TG_TOKEN = "8674377212:AAGIxMfDkNsDgTDkpEby-IWbV9NAhyZpvxw"
TG_CHAT_ID = "7864537791"

ACCOUNT_ADDRESS = "VOTRE_ADRESSE_DE_PORTEFEUILLE_ICI"
API_SECRET_KEY = "VOTRE_CLE_PRIVEE_OU_CLE_AGENT_ICI"

RISK_PER_TRADE_USD = 20.0  
SL_PCT_CRYPTO = 0.01       # 1% de Stop Loss
TP_PCT_CRYPTO = 0.02       # 2% de Take Profit
BE_THRESHOLD_PCT = 0.01    # Déclenchement du Breakeven dès +1% de gain

CRYPTO_WATCHLIST = ["BTC", "ETH", "SOL"]
ADX_THRESHOLD = 20
ALERT_COOLDOWN = 900       
last_alerts = {}

# Registre des positions gérées par le bot pour le suivi du Breakeven
# Structure : { "BTC": {"side": "BUY", "entry": 63752.0, "size": 0.031, "has_be": False} }
active_positions = {}

try:
    account = Account.from_key(API_SECRET_KEY)
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    print(f"[+] Connexion Hyperliquid validée : {account.address}")
except Exception as e:
    print(f"[-] Échec de l'initialisation Hyperliquid : {e}")

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=3)
    except:
        pass

def execute_hyperliquid_trade(symbol, side, current_price):
    try:
        sl_distance_usd = current_price * SL_PCT_CRYPTO
        position_size_token = round(RISK_PER_TRADE_USD / sl_distance_usd, 3)
        
        if position_size_token <= 0:
            return False

        is_buy = (side == "BUY")
        market_order_result = exchange.market_open(symbol, is_buy, position_size_token, slippage=0.01)
        
        if market_order_result["status"] != "ok":
            return False
            
        if is_buy:
            sl_price = round(current_price * (1 - SL_PCT_CRYPTO), 2)
            tp_price = round(current_price * (1 + TP_PCT_CRYPTO), 2)
        else:
            sl_price = round(current_price * (1 + SL_PCT_CRYPTO), 2)
            tp_price = round(current_price * (1 - TP_PCT_CRYPTO), 2)

        # Placement initial du SL et TP
        exchange.order(symbol, not is_buy, position_size_token, sl_price, {"trigger": {"isMarket": True, "triggerPx": sl_price, "tpsl": "sl"}})
        exchange.order(symbol, not is_buy, position_size_token, tp_price, {"trigger": {"isMarket": True, "triggerPx": tp_price, "tpsl": "tp"}})
        
        # Enregistrement de la position pour surveillance du Breakeven
        active_positions[symbol] = {
            "side": side,
            "entry": current_price,
            "size": position_size_token,
            "has_be": False
        }
        
        return tp_price, sl_price, position_size_token
    except Exception as e:
        print(f"[-] Erreur exécution ordre : {e}")
        return False

def check_and_apply_breakeven(symbol, current_price):
    """
    Vérifie si les gains latents ont atteint le palier pour sécuriser au prix d'entrée.
    """
    pos = active_positions.get(symbol)
    if not pos or pos["has_be"]:
        return

    entry = pos["entry"]
    side = pos["side"]
    size = pos["size"]
    
    # Calcul de la performance actuelle
    if side == "BUY":
        perf = (current_price - entry) / entry
    else:
        perf = (entry - current_price) / entry

    # Si le gain atteint ou dépasse le seuil (1%)
    if perf >= BE_THRESHOLD_PCT:
        try:
            print(f"[🛡️ BREAKEVEN] Seuil atteint sur {symbol} ({round(perf*100, 2)}%). Sécurisation en cours...")
            is_buy = (side == "BUY")
            
            # Modifier le Stop Loss pour le mettre au prix d'entrée exact (frais de glissement inclus au besoin)
            # Sur Hyperliquid, on repousse un ordre trigger au prix d'entrée
            be_price = round(entry, 2)
            exchange.order(symbol, not is_buy, size, be_price, {"trigger": {"isMarket": True, "triggerPx": be_price, "tpsl": "sl"}})
            
            # Marquer la position comme sécurisée
            active_positions[symbol]["has_be"] = True
            
            msg = f"🛡️ *[BOT AUTOMATIQUE] BREAKEVEN APPLIQUÉ*\n• Actif : {symbol}\n• Position : {side}\n• Le Stop Loss a été déplacé sur ton prix d'entrée (*{be_price}*).\n\nTrade sécurisé à 0$ de risque. On laisse courir vers le TP !"
            send_telegram_alert(msg)
            
        except Exception as e:
            print(f"[-] Erreur lors de l'application du Breakeven sur {symbol} : {e}")

# ==========================================
#  🔄 BOUCLE DE SURVEILLANCE PERMANENTE (H24)
# ==========================================
print("[+] Le Bot FX & Crypto Flow avec BREAKEVEN IMPÉRATIF est opérationnel.")

while True:
    try:
        for symbol in CRYPTO_WATCHLIST:
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
            
            # 1. Gestion des positions en cours (Vérification du Breakeven)
            if symbol in active_positions:
                check_and_apply_breakeven(symbol, current_price)
                
                # Nettoyage si la position a été coupée par le TP ou le SL sur l'échange
                # Pour garder le code léger ce soir, le registre se met à jour si le prix traverse le TP ou le SL
                pos_info = active_positions[symbol]
                if pos_info["side"] == "BUY" and (current_price >= pos_info["entry"] * (1 + TP_PCT_CRYPTO) or current_price <= (pos_info["entry"] if pos_info["has_be"] else pos_info["entry"] * (1 - SL_PCT_CRYPTO))):
                    del active_positions[symbol]
                elif pos_info["side"] == "SELL" and (current_price <= pos_info["entry"] * (1 - TP_PCT_CRYPTO) or current_price >= (pos_info["entry"] if pos_info["has_be"] else pos_info["entry"] * (1 + SL_PCT_CRYPTO))):
                    del active_positions[symbol]
                continue

            # 2. Logique de détection des nouveaux signaux (Triple Écran)
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
            
            if buy_alignment:
                alert_key = f"{symbol}_BUY"
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    trade_success = execute_hyperliquid_trade(symbol, "BUY", current_price)
                    if trade_success:
                        tp_p, sl_p, size_t = trade_success
                        msg = f"🤖 *[BOT AUTOMATIQUE] POSITION LONG OUVERTE*\n• Actif : {symbol}\n• Entrée : {round(current_price, 2)}\n\n🟢 *SÉCURISATION INTERNE :*\n🎯 TAKE PROFIT : {tp_p}\n🛑 STOP LOSS INITIAL : {sl_p}\n🛡️ *Breakeven automatisé activé à +1%*"
                        send_telegram_alert(msg)
                        last_alerts[alert_key] = current_time
                    
            elif sell_alignment:
                alert_key = f"{symbol}_SELL"
                if alert_key not in last_alerts or (current_time - last_alerts[alert_key] > ALERT_COOLDOWN):
                    trade_success = execute_hyperliquid_trade(symbol, "SELL", current_price)
                    if trade_success:
                        tp_p, sl_p, size_t = trade_success
                        msg = f"🤖 *[BOT AUTOMATIQUE] POSITION SHORT OUVERTE*\n• Actif : {symbol}\n• Entrée : {round(current_price, 2)}\n\n🔴 *SÉCURISATION INTERNE :*\n🎯 TAKE PROFIT : {tp_p}\n🛑 STOP LOSS INITIAL : {sl_p}\n🛡️ *Breakeven automatisé activé à +1%*"
                        send_telegram_alert(msg)
                        last_alerts[alert_key] = current_time

    except Exception as loop_error:
        print(f"[-] Erreur boucle principale : {loop_error}")
        
    time.sleep(30)
