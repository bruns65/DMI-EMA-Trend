import pandas as pd
import numpy as np
import requests

def get_coinbase_candles(symbol, timeframe):
    """ Récupère les bougies depuis l'API publique de Coinbase """
    granularity_map = {"5m": 300, "15m": 900, "1h": 3600}
    granularity = granularity_map.get(timeframe, 300)
    
    cb_symbol = f"{symbol}-USD"
    url = f"https://api.exchange.coinbase.com/products/{cb_symbol}/candles"
    params = {"granularity": granularity, "limit": 100}
    
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Coinbase renvoie [time, low, high, open, close, volume]
            df = pd.DataFrame(data, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
            df = df.sort_values('time').reset_index(drop=True)
            return df
    except Exception as e:
        print(f"Erreur API Coinbase ({symbol} {timeframe}): {e}")
    return None

def compute_dmi_and_ema(df, period=14, compute_ema=False):
    """ Calcule le DMI, l'ADX, l'EMA 200, le MA/EMA Cross 10 et le Stoch RSI """
    if df is None or len(df) < 30:
        return None
        
    df = df.copy()
    
    # 1. CALCUL COMPOSANTES DMI / ADX
    df['UpMove'] = df['high'].diff()
    df['DownMove'] = df['low'].diff() * -1
    
    df['PlusDM'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0)
    df['MinusDM'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0)
    
    # True Range
    df['ATR_1'] = df['high'] - df['low']
    df['ATR_2'] = abs(df['high'] - df['close'].shift(1))
    df['ATR_3'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['ATR_1', 'ATR_2', 'ATR_3']].max(axis=1)
    
    # Lissage Wilder
    TR_smooth = df['TR'].ewm(alpha=1/period, adjust=False).mean()
    PlusDM_smooth = df['PlusDM'].ewm(alpha=1/period, adjust=False).mean()
    MinusDM_smooth = df['MinusDM'].ewm(alpha=1/period, adjust=False).mean()
    
    df['DI+'] = (PlusDM_smooth / TR_smooth) * 100
    df['DI-'] = (MinusDM_smooth / TR_smooth) * 100
    
    DX = (abs(df['DI+'] - df['DI-']) / (df['DI+'] + df['DI-'])) * 100
    df['ADX'] = DX.ewm(alpha=1/period, adjust=False).mean()
    
    # 2. CALCUL EMA 200 STRUCUTUREL
    if compute_ema:
        df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
    # 3. FILTRE MA/EMA CROSS (10) REPERÉ SUR TON ÉCRAN
    df['MA_10'] = df['close'].rolling(window=10).mean()
    df['EMA_10'] = df['close'].ewm(span=10, adjust=False).mean()
    
    # 4. LE DÉTECTEUR FLASH : STOCH RSI (14, 14, 3, 3)
    # Étape A : Calcul du RSI standard
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).ewm(alpha=1/14, adjust=False).mean()
    avg_loss = pd.Series(loss).ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Étape B : Application de la Stochastique sur le RSI
    rsi_min = df['RSI'].rolling(window=14).min()
    rsi_max = df['RSI'].rolling(window=14).max()
    df['StochRSI_K'] = ((df['RSI'] - rsi_min) / (rsi_max - rsi_min + 1e-10)) * 100
    # Lissage standard %K sur 3 périodes
    df['StochRSI_K'] = df['StochRSI_K'].rolling(window=3).mean()
    
    # Extraction des 2 dernières lignes pour analyser la pente (pente montante ou descendante)
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    result = {
        "close": last_row["close"],
        "DI+": round(last_row["DI+"], 1),
        "DI-": round(last_row["DI-"], 1),
        "ADX": round(last_row["ADX"], 1),
        "ADX_prev": round(prev_row["ADX"], 1), # Pour capter la raideur de la pente
        "MA_10": last_row["MA_10"],
        "EMA_10": last_row["EMA_10"],
        "StochRSI_K": round(last_row["StochRSI_K"], 2),
        "EMA_200": last_row["EMA_200"] if compute_ema else None
    }
    return result
