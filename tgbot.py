import requests
import pandas as pd
import time
from datetime import datetime
import numpy as np

# ==================== AYARLAR ====================
TELEGRAM_BOT_TOKEN = "8450222189:AAF8MvaUT-axEsDBsNwjo89jHCx414JAczA"
TELEGRAM_CHAT_ID = "-4894918800"
INTERVAL = '15m'
TP_PERCENT = 0.004
SL_PERCENT = 0.004
# ================================================

def send_telegram_message(symbol, signal, current_price, tp_price, sl_price):
    """Telegram'a detaylı mesaj gönder"""
    tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}.P"
    
    if signal == "BUY":
        message = f"""
🚀 **ALIM Sinyali** 🚀
**Sembol:** {symbol}
**Mevcut Fiyat:** {current_price:.4f} USDT
**Giriş:** {current_price:.4f} USDT
**TP:** {tp_price:.4f} USDT (%{TP_PERCENT*100:.2f})
**SL:** {sl_price:.4f} USDT (%{SL_PERCENT*100:.2f})

📊 **TradingView:** [Grafiği Aç]({tv_link})
⏰ **Saat:** {datetime.now().strftime('%H:%M:%S')}
        """
    else:
        message = f"""
🔻 **SATIM Sinyali** 🔻
**Sembol:** {symbol}
**Mevcut Fiyat:** {current_price:.4f} USDT
**Giriş:** {current_price:.4f} USDT
**TP:** {tp_price:.4f} USDT (%{TP_PERCENT*100:.2f})
**SL:** {sl_price:.4f} USDT (%{SL_PERCENT*100:.2f})

📊 **TradingView:** [Grafiği Aç]({tv_link})
⏰ **Saat:** {datetime.now().strftime('%H:%M:%S')}
        """
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': False
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"✅ {symbol} {signal} mesajı gönderildi")
    except Exception as e:
        print(f"❌ Telegram mesajı gönderilemedi: {e}")

def get_binance_klines(symbol, interval='5m', limit=100):
    """Binance Public API ile mum verilerini çek"""
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        # DataFrame oluştur
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Sayısal değerlere çevir
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])
            
        return df
    except Exception as e:
        print(f"❌ {symbol} veri çekilemedi: {e}")
        return None

def get_all_futures_symbols():
    """TÜM USDT-M futures sembollerini al"""
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    
    try:
        response = requests.get(url)
        data = response.json()
        symbols = []
        
        for symbol_info in data['symbols']:
            symbol = symbol_info['symbol']
            if (symbol.endswith('USDT') and 
                symbol_info['status'] == 'TRADING' and
                symbol_info['contractType'] == 'PERPETUAL' and
                'UP' not in symbol and 
                'DOWN' not in symbol and
                'BEAR' not in symbol and
                'BULL' not in symbol):
                symbols.append(symbol)
                
        return symbols
    except Exception as e:
        print(f"❌ Sembol listesi çekilemedi: {e}")
        return []

def calculate_rsi(prices, period=14):
    """Basit RSI hesaplama"""
    deltas = prices.diff()
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)
    
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    
    # Sıfıra bölünmeyi önle
    avg_loss = avg_loss.replace(0, 0.001)
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(series, period):
    """EMA hesaplama"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_qqe_simple(df, length=14, ssf=5):
    """Basitleştirilmiş QQE hesaplama - Uyarılar düzeltildi"""
    if len(df) < 50:
        return None
    
    try:
        # DataFrame'in kopyasını oluştur (uyarıları önlemek için)
        df_calc = df.copy()
        
        # RSI hesapla
        df_calc['rsi'] = calculate_rsi(df_calc['close'], length)
        
        # NaN değerleri temizle
        df_calc = df_calc.dropna()
        
        if len(df_calc) < 20:
            return None
            
        # EMA ile smoothing - .loc kullanarak uyarıları önle
        df_calc.loc[:, 'RSII'] = calculate_ema(df_calc['rsi'], ssf)
        
        # TR ve ATRRSI
        df_calc.loc[:, 'TR'] = (df_calc['RSII'] - df_calc['RSII'].shift(1)).abs()
        df_calc.loc[:, 'WWMA'] = calculate_ema(df_calc['TR'], length)
        df_calc.loc[:, 'ATRRSI'] = calculate_ema(df_calc['WWMA'], length)
        
        # QQE değerleri
        df_calc.loc[:, 'QQEF'] = calculate_ema(df_calc['rsi'], ssf)
        df_calc.loc[:, 'QUP'] = df_calc['QQEF'] + (df_calc['ATRRSI'] * 4.236)
        df_calc.loc[:, 'QDN'] = df_calc['QQEF'] - (df_calc['ATRRSI'] * 4.236)
        
        # QQES için basit hesaplama
        qqes = []
        for i in range(len(df_calc)):
            if i == 0:
                qqes.append(df_calc['QDN'].iloc[i])
            else:
                prev_qqes = qqes[i-1]
                current_qup = df_calc['QUP'].iloc[i]
                current_qdn = df_calc['QDN'].iloc[i]
                current_qqef = df_calc['QQEF'].iloc[i]
                
                if current_qup < prev_qqes:
                    new_qqes = current_qup
                elif current_qdn > prev_qqes:
                    new_qqes = current_qdn
                else:
                    new_qqes = prev_qqes
                qqes.append(new_qqes)
        
        df_calc.loc[:, 'QQES'] = qqes
        return df_calc.tail(100)
        
    except Exception as e:
        print(f"❌ QQE hesaplama hatası: {e}")
        return None

def check_qqe_signal_simple(df):
    """Son 2 mumu kontrol ederek sinyal tespit et"""
    if df is None or len(df) < 2:
        return "NO_DATA"
    
    try:
        current_qqef = df['QQEF'].iloc[-1]
        previous_qqef = df['QQEF'].iloc[-2]
        current_qqes = df['QQES'].iloc[-1]
        previous_qqes = df['QQES'].iloc[-2]
        
        # Alım Sinyali
        if previous_qqef <= previous_qqes and current_qqef > current_qqes:
            return "BUY"
        # Satım Sinyali
        elif previous_qqef >= previous_qqes and current_qqef < current_qqes:
            return "SELL"
        else:
            return "NEUTRAL"
    except:
        return "NO_DATA"

def calculate_tp_sl(current_price, signal):
    """TP ve SL fiyatlarını hesapla"""
    if signal == "BUY":
        tp_price = current_price * (1 + TP_PERCENT)
        sl_price = current_price * (1 - SL_PERCENT)
    else:
        tp_price = current_price * (1 - TP_PERCENT)
        sl_price = current_price * (1 + SL_PERCENT)
    return tp_price, sl_price

def main():
    """Ana tarama fonksiyonu - TÜM SEMBOLLER"""
    print("🔍 TÜM USDT-M Futures sembolleri alınıyor...")
    symbols = get_all_futures_symbols()
    print(f"✅ {len(symbols)} sembol bulundu. 5m mumlar taranıyor...")
    
    signal_count = 0
    total_symbols = len(symbols)
    
    for i, symbol in enumerate(symbols):
        if i % 50 == 0:
            print(f"📊 {i}/{total_symbols} sembol tarandı...")
        
        # 100 mum çek (RSI hesaplaması için)
        df = get_binance_klines(symbol, INTERVAL, 100)
        if df is None or len(df) < 50:
            continue
            
        # QQE hesapla
        df_qqe = calculate_qqe_simple(df)
        if df_qqe is None or len(df_qqe) < 2:
            continue
            
        # Sadece son 2 mumu kontrol et
        signal = check_qqe_signal_simple(df_qqe.tail(2))
        current_price = df['close'].iloc[-1]
        
        if signal in ["BUY", "SELL"]:
            # TP/SL hesapla
            tp_price, sl_price = calculate_tp_sl(current_price, signal)
            
            # Telegram'a mesaj gönder
            send_telegram_message(symbol, signal, current_price, tp_price, sl_price)
            signal_count += 1
            
        # Binance rate limit için bekle
        time.sleep(0.05)
    
    print(f"✅ Tarama tamamlandı! {signal_count} sinyal bulundu.")

if __name__ == "__main__":
    print("🤖 Binance Futures QQE Scanner başlatıldı...")
    print("⏰ 5 dakikalık mumlar | TÜM Semboller")
    print("🔔 Sinyal gelirse Telegram'dan mesaj atılacak...")
    
    # Uyarıları gizle (opsiyonel)
    import warnings
    warnings.filterwarnings('ignore')
    
    # Sürekli çalışacak şekilde
    while True:
        try:
            start_time = time.time()
            main()
            end_time = time.time()
            
            execution_time = end_time - start_time
            print(f"⏱️  Tarama süresi: {execution_time:.2f} saniye")
            
            # 5 dakika bekle (5m mumlar için ideal)
            wait_time = max(300 - execution_time, 60)
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - {wait_time:.0f} saniye bekleniyor...")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Hata oluştu: {e}")
            print("⏰ 60 saniye beklenip yeniden denenecek...")
            time.sleep(60)
