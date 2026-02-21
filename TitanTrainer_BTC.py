"""
╔══════════════════════════════════════════════════════════════════╗
║         TITAN TRAINER BTC v1.0 — CEREBRO PROPIO BTC             ║
║  Entrena un modelo LSTM exclusivo para BTCUSDm                   ║
║  Corre toda la noche — lee miles de velas M1                     ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os, sys, time, math
import numpy as np
import pandas as pd
from datetime import datetime

print("=" * 60)
print("  🧠 TITAN TRAINER BTC v1.0 — Cerebro Propio Bitcoin")
print("=" * 60)
print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ── 1. CONEXIÓN MT5 ─────────────────────────────────────────────
print("🔌 Conectando a MetaTrader 5...")
try:
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("❌ Error inicializando MT5. Asegúrate que MT5 esté abierto.")
        sys.exit(1)
    print("✅ MT5 conectado.")
except ImportError:
    print("❌ MetaTrader5 no instalado.")
    sys.exit(1)

# ── 2. DESCARGA DE DATOS ─────────────────────────────────────────
SYMBOL = "BTCUSDm"
TIMEFRAME = mt5.TIMEFRAME_M1
MAX_CANDLES = 50000  # ~34 días de velas M1 (máximo disponible)

print(f"\n📥 Descargando hasta {MAX_CANDLES:,} velas M1 de {SYMBOL}...")
rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, MAX_CANDLES)

if rates is None or len(rates) == 0:
    print("❌ No se pudieron obtener datos. ¿Está BTCUSDm disponible en MT5?")
    mt5.shutdown()
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)
print(f"✅ {len(df):,} velas obtenidas | Rango: {df.index[0]} → {df.index[-1]}")

# ── HELPERS ──────────────────────────────────────────────────────
def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def _atr(df, period=14):
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _bollinger(series, period=20, std=2):
    mid = series.rolling(period).mean()
    s = series.rolling(period).std()
    return mid + std * s, mid, mid - std * s

# ── 3. FEATURE ENGINEERING PARA BTC ─────────────────────────────
print("\n⚙️  Calculando features BTC-específicos...")

# BTC-SPECIFIC: Normalizar por precio relativo, no absoluto
df['log_ret']    = np.log(df['close'] / df['close'].shift(1))
df['rsi']        = _rsi(df['close'], 14)
df['ema9']       = df['close'].ewm(span=9).mean()
df['ema21']      = df['close'].ewm(span=21).mean()
df['ema_diff']   = (df['ema9'] - df['ema21']) / df['close']  # % relativo, no absoluto
df['atr']        = _atr(df, 14) / df['close']                # ATR como % del precio
df['bb_upper'], df['bb_mid'], df['bb_lower'] = _bollinger(df['close'], 20, 2)
df['bb_pct']     = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-9)
df['vol_ratio']  = df['tick_volume'] / df['tick_volume'].rolling(20).mean()
df['macd_diff']  = (df['close'].ewm(span=12).mean() - df['close'].ewm(span=26).mean()) / df['close']  # % relativo

# Features finales - 9 dimensiones (compatible con Gold brain formato)
BTC_FEATURES = ['log_ret', 'rsi', 'ema_diff', 'atr', 'bb_pct', 'vol_ratio', 'macd_diff', 'ema9', 'ema21']

# Ema9/ema21 normalizados por precio para escala correcta
df['ema9']  = df['ema9']  / df['close']
df['ema21'] = df['ema21'] / df['close']

df.dropna(inplace=True)
print(f"✅ {len(df):,} velas con features calculados. 9 dimensiones: {BTC_FEATURES}")

# ── 4. ETIQUETAS ─────────────────────────────────────────────────
# Predecir si el precio sube en los próximos 5 minutos (>0.05% = BUY)
HORIZONTE = 5
df['future_ret'] = df['close'].shift(-HORIZONTE) / df['close'] - 1
df['label'] = (df['future_ret'] > 0.0005).astype(int)  # 0.05% threshold
df.dropna(inplace=True)

buys = df['label'].sum()
sells = len(df) - buys
print(f"📊 Distribución: BUY={buys:,} ({buys/len(df)*100:.1f}%) | SELL={sells:,} ({sells/len(df)*100:.1f}%)")

# ── 5. SCALER ────────────────────────────────────────────────────
print("\n📐 Normalizando con MinMaxScaler BTC-exclusivo...")
from sklearn.preprocessing import MinMaxScaler
import joblib

X_raw = df[BTC_FEATURES].values
scaler = MinMaxScaler(feature_range=(0, 1))
X_scaled = scaler.fit_transform(X_raw)

# Guardar scaler BTC
MQL5_PATH = r"C:\Users\dfa21\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\MQL5\Files"
SCALER_BTC_PATH = os.path.join(MQL5_PATH, "scaler_BTCUSDm.pkl")
joblib.dump(scaler, SCALER_BTC_PATH)
print(f"✅ Scaler BTC guardado: {SCALER_BTC_PATH}")

# ── 6. PREPARAR SECUENCIAS ───────────────────────────────────────
LOOKBACK = 120  # 120 velas M1 = 2 horas de contexto
print(f"\n🔢 Creando secuencias ({LOOKBACK} pasos de tiempo)...")

X_seq, y_seq = [], []
labels = df['label'].values

for i in range(LOOKBACK, len(X_scaled) - HORIZONTE):
    X_seq.append(X_scaled[i - LOOKBACK:i])
    y_seq.append(labels[i])

X_seq = np.array(X_seq)
y_seq = np.array(y_seq)
print(f"✅ {len(X_seq):,} secuencias | Shape: {X_seq.shape}")

# ── 7. SPLIT TRAIN/TEST ──────────────────────────────────────────
split = int(len(X_seq) * 0.85)
X_train, X_test = X_seq[:split], X_seq[split:]
y_train, y_test = y_seq[:split], y_seq[split:]
print(f"📦 Train: {len(X_train):,} | Test: {len(X_test):,}")

# ── 8. MODELO LSTM BTC ───────────────────────────────────────────
print("\n🏗️  Construyendo modelo LSTM BTC...")
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
    from tensorflow.keras.optimizers import Adam
    print(f"   TensorFlow: {tf.__version__}")
except ImportError:
    print("❌ TensorFlow no instalado.")
    sys.exit(1)

model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(LOOKBACK, 9)),
    BatchNormalization(),
    Dropout(0.3),
    LSTM(64, return_sequences=True),
    BatchNormalization(),
    Dropout(0.2),
    LSTM(32, return_sequences=False),
    BatchNormalization(),
    Dropout(0.2),
    Dense(16, activation='relu'),
    Dense(1, activation='sigmoid')
])

model.compile(
    optimizer=Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

model.summary()

# ── 9. ENTRENAMIENTO ─────────────────────────────────────────────
MODEL_BTC_PATH = os.path.join(MQL5_PATH, "modelo_lstm_btc.h5")
CHECKPOINT_PATH = os.path.join(MQL5_PATH, "modelo_lstm_btc_best.h5")

callbacks = [
    EarlyStopping(patience=8, restore_best_weights=True, verbose=1),
    ReduceLROnPlateau(patience=4, factor=0.5, verbose=1, min_lr=1e-6),
    ModelCheckpoint(CHECKPOINT_PATH, save_best_only=True, verbose=1)
]

print(f"\n🚀 ENTRENANDO... (esto puede tardar varias horas - es normal)")
print(f"   Epochs máximas: 50 | Early stopping: 8 sin mejora")
print(f"   Hora inicio: {datetime.now().strftime('%H:%M:%S')}\n")

history = model.fit(
    X_train, y_train,
    epochs=50,
    batch_size=256,
    validation_data=(X_test, y_test),
    callbacks=callbacks,
    verbose=1
)

# ── 10. EVALUACIÓN ───────────────────────────────────────────────
print(f"\n📊 EVALUANDO en datos de test...")
loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"   Loss: {loss:.4f} | Accuracy: {acc*100:.2f}%")

# Métricas adicionales
y_pred = (model.predict(X_test, verbose=0) > 0.5).astype(int).flatten()
from sklearn.metrics import classification_report, confusion_matrix
print("\n📋 Reporte de Clasificación:")
print(classification_report(y_test, y_pred, target_names=['SELL', 'BUY']))
print("Matriz de Confusión:")
print(confusion_matrix(y_test, y_pred))

# ── 11. GUARDAR MODELO FINAL ─────────────────────────────────────
model.save(MODEL_BTC_PATH)
print(f"\n✅ MODELO BTC GUARDADO: {MODEL_BTC_PATH}")
print(f"✅ SCALER BTC: {SCALER_BTC_PATH}")

# ── 12. RESUMEN FINAL ────────────────────────────────────────────
best_val_acc = max(history.history['val_accuracy'])
best_epoch = history.history['val_accuracy'].index(best_val_acc) + 1

print(f"""
╔══════════════════════════════════════════════════════════════════╗
║         ✅ ENTRENAMIENTO COMPLETADO — CEREBRO BTC LISTO          ║
╠══════════════════════════════════════════════════════════════════╣
║  Velas procesadas : {len(df):>10,}                              ║
║  Secuencias train : {len(X_train):>10,}                         ║
║  Accurracy final  : {acc*100:>9.2f}%                            ║
║  Mejor val_acc    : {best_val_acc*100:>9.2f}% (epoch {best_epoch})         ║
║  Modelo guardado  : modelo_lstm_btc.h5                          ║
║  Scaler guardado  : scaler_BTCUSDm.pkl                          ║
╠══════════════════════════════════════════════════════════════════╣
║  SIGUIENTE PASO: Activar Cerebro BTC en TitanBrain_BTC.py       ║
╚══════════════════════════════════════════════════════════════════╝
""")

mt5.shutdown()
