import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import ta
import joblib
import os
import time

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization, Conv1D, MaxPooling1D
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
from tensorflow.keras.losses import BinaryCrossentropy
from sklearn.preprocessing import RobustScaler
from sklearn.utils.class_weight import compute_class_weight

# ======= CONFIG v5.5 "TITAN SNIPER" =======
SYMBOLS = ["XAUUSDm"]
TIMEFRAME = mt5.TIMEFRAME_M1
BARS_TO_DOWNLOAD = 35000        
LOOKBACK = 120                  
PREDICT_BARS = 5                
NOISE_THRESHOLD = 0.0010        # v5.5: Un poco más de sensibilidad ($2.00)

USER_PATH = os.path.expanduser("~")
MQL5_FILES_PATH = os.path.join(USER_PATH, "AppData", "Roaming", "MetaQuotes", "Terminal", "53785E099C927DB68A545C249CDBCE06", "MQL5", "Files")
MODEL_PATH = os.path.join(MQL5_FILES_PATH, 'modelo_lstm_titan.h5')
SCALER_PATH_TEMPLATE = os.path.join(MQL5_FILES_PATH, 'scaler_{}.pkl')
os.makedirs(MQL5_FILES_PATH, exist_ok=True)

feature_cols = ['log_ret', 'rsi', 'atr_rel', 'bb_pct', 'macd_diff', 'wick_up', 'wick_dn', 'body_size', 'vol_rel']

def calculate_features(df):
    df = df.copy()
    # v5.2: Acción de Precio Pura (Anatomía de la Vela)
    df['wick_up'] = (df['high'] - np.maximum(df['open'], df['close'])) / df['close']
    df['wick_dn'] = (np.minimum(df['open'], df['close']) - df['low']) / df['close']
    df['body_size'] = np.abs(df['close'] - df['open']) / df['close']
    
    # v5.3: Volumen Relativo (Fuerza de la Jugada)
    df['vol_rel'] = df['tick_volume'] / (df['tick_volume'].rolling(20).mean() + 1e-9)
    
    # Indicadores Tradicionales Optimizados
    df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['atr_rel'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14) / df['close']
    
    # Presión en Bandas
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_pct'] = (df['close'] - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband() + 1e-9)
    
    # MACD 
    macd = ta.trend.MACD(close=df['close'])
    df['macd_diff'] = macd.macd_diff().fillna(0)
    
    df.dropna(inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)
    return df

def create_dataset():
    if not mt5.initialize():
        return None, None, None, None
    
    for symbol in SYMBOLS:
        print(f"Descargando {BARS_TO_DOWNLOAD} barras de {symbol}...")
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, BARS_TO_DOWNLOAD)
        if rates is None or len(rates) < 500:
            mt5.shutdown()
            return None, None, None, None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f"  Rango: {df['time'].iloc[0]} -> {df['time'].iloc[-1]} ({len(df)} barras)")
        
        df = calculate_features(df)
        print(f"  Features: {len(df)} muestras")

        scaler = RobustScaler()
        scaled = scaler.fit_transform(df[feature_cols])
        joblib.dump(scaler, SCALER_PATH_TEMPLATE.format(symbol))

        closes = df['close'].values
        X, y = [], []
        skip = 0
        
        for i in range(len(scaled) - LOOKBACK - PREDICT_BARS):
            curr = closes[i + LOOKBACK - 1]
            fut = closes[i + LOOKBACK + PREDICT_BARS - 1]
            pct = (fut - curr) / curr
            if abs(pct) < NOISE_THRESHOLD:
                skip += 1
                continue
            X.append(scaled[i : i + LOOKBACK])
            y.append(1 if pct > 0 else 0)
            
        print(f"  Muestras: {len(y)} (BUY:{sum(y)} SELL:{len(y)-sum(y)} Ruido:{skip})")

        split = int(len(X) * 0.8)
        X, y = np.array(X), np.array(y)
        
        mt5.shutdown()
        return X[:split], y[:split], X[split:], y[split:]
    
    mt5.shutdown()
    return None, None, None, None


def train():
    print("\n" + "="*60)
    print("TITAN TRAINER v5 'FINAL BOSS'")
    print("  Best of v2 params + v4 anti-overfitting")
    print("="*60)
    
    t0 = time.time()
    X_tr, y_tr, X_val, y_val = create_dataset()
    if X_tr is None:
        print("Sin datos.")
        return

    # Data augmentation: 2 copias con ruido
    X_aug1 = X_tr + np.random.normal(0, 0.003, X_tr.shape)
    X_aug2 = X_tr + np.random.normal(0, 0.007, X_tr.shape)
    X_full = np.concatenate([X_tr, X_aug1, X_aug2])
    y_full = np.concatenate([y_tr, y_tr, y_tr])
    
    print(f"\nDATASET:")
    print(f"  Train: {X_tr.shape} -> Aug: {X_full.shape}")
    print(f"  Val:   {X_val.shape}")
    
    classes = np.unique(y_full)
    w = compute_class_weight('balanced', classes=classes, y=y_full)
    cw = {int(c): float(v) for c, v in zip(classes, w)}
    print(f"  Pesos: {cw}")

    # --- MODELO: Conv1D para patrones + LSTM para memoria ---
    model = Sequential([
        Conv1D(32, 5, activation='relu', padding='same', input_shape=(LOOKBACK, len(feature_cols))),
        Conv1D(32, 3, activation='relu', padding='same'),
        MaxPooling1D(2),
        Dropout(0.25),
        
        LSTM(64, return_sequences=True),
        Dropout(0.3),
        LSTM(32),
        BatchNormalization(),
        Dropout(0.4),
        
        Dense(16, activation='relu', kernel_regularizer=l2(0.002)),
        Dropout(0.3),
        Dense(1, activation='sigmoid')
    ])

    loss = BinaryCrossentropy(label_smoothing=0.08)
    model.compile(optimizer=Adam(0.0008), loss=loss, metrics=['accuracy'])
    model.summary()

    es = EarlyStopping(monitor='val_accuracy', patience=15, restore_best_weights=True, verbose=1)
    rl = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1)

    print("\nENTRENANDO...\n")
    h = model.fit(X_full, y_full, epochs=100, batch_size=64,
                  validation_data=(X_val, y_val), shuffle=False,
                  class_weight=cw, callbacks=[es, rl], verbose=1)
    
    vl, va = model.evaluate(X_val, y_val, verbose=0)
    tl, ta_val = model.evaluate(X_tr, y_tr, verbose=0)
    
    best_va = max(h.history['val_accuracy'])
    best_ep = np.argmax(h.history['val_accuracy']) + 1
    
    print("\n" + "="*60)
    print("RESULTADO")
    print("="*60)
    print(f"  Tiempo:     {int(time.time()-t0)}s")
    print(f"  Train Acc:  {ta_val*100:.1f}%")
    print(f"  Val Acc:    {va*100:.1f}%")
    print(f"  BEST Val:   {best_va*100:.1f}% (ep {best_ep})")
    print(f"  Gap:        {(ta_val-va)*100:.1f}%")
    
    if va >= 0.525:
        model.save(MODEL_PATH)
        print(f"\n  GUARDADO: {MODEL_PATH}")
    else:
        print(f"\n  NO GUARDADO ({va*100:.1f}% < 52.5%)")
    print("="*60)

if __name__ == "__main__":
    train()
