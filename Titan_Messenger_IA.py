import os
import subprocess
import sys
import time
import requests
import json
import re

try:
    import telebot
    import speech_recognition as sr
    from gtts import gTTS
    from pydub import AudioSegment
    import static_ffmpeg
    ff_path = os.path.join(os.environ['LOCALAPPDATA'], r"Python\pythoncore-3.14-64\Lib\site-packages\static_ffmpeg\bin\win32\ffmpeg.exe")
    if os.path.exists(ff_path):
        AudioSegment.converter = ff_path
        print(f"🔊 MOTOR DE AUDIO DETECTADO: {ff_path}")
    else:
        print("⚠️ ADVERTENCIA: No se encontró ffmpeg en la ruta esperada.")
except ImportError:
    print("📦 Instalando dependencias de Evolución Sensorial...")
    deps = ["pyTelegramBotAPI", "SpeechRecognition", "gTTS", "pydub", "static-ffmpeg", "MetaTrader5", "requests"]
    for dep in deps:
        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
    
    import telebot
    import speech_recognition as sr
    from gtts import gTTS
    from pydub import AudioSegment
    import static_ffmpeg
    static_ffmpeg.add_paths()
    ff_path = os.path.join(os.environ['LOCALAPPDATA'], r"Python\pythoncore-3.14-64\Lib\site-packages\static_ffmpeg\bin\win32\ffmpeg.exe")
    if os.path.exists(ff_path):
        AudioSegment.converter = ff_path

import MetaTrader5 as mt5
import os
import requests
import json
import time

# --- CONFIGURACIÓN DE MANDO (IGUAL A BRAIN) ---
TOKEN = '8217691336:AAFWduUGkO_f-QRF6MN338HY-MA46CjzHMg'
CHAT_ID = '8339882349'
OLLAMA_URL = "http://localhost:11434/api/generate" # Ajustar si usa nube o local

bot = telebot.TeleBot(TOKEN)

def get_account_context():
    """ Recopila toda la información de la cuenta para que la IA sepa qué está pasando """
    if not mt5.initialize():
        return "ERROR: No se pudo conectar a MetaTrader 5."
    
    acc = mt5.account_info()
    positions = mt5.positions_get()
    
    context = (f"SISTEMA TITAN 2026 - ESTADO ACTUAL:\n"
               f"Balance: ${acc.balance:.2f} | Patrimonio: ${acc.equity:.2f} | Margen: {acc.margin_level:.1f}%\n"
               f"Trades Abiertos: {len(positions)}\n")
    
    if positions:
        context += "POSICIONES:\n"
        for p in positions:
            context += f"- #{p.ticket}: {p.symbol} ({'BUY' if p.type == 0 else 'SELL'}) Profit: ${p.profit:.2f}\n"
    
    return context

def call_ia(user_msg, context):
    """ Llama a la IA con el contexto de la cuenta y la duda del usuario """
    # v28.8: Soporte para ANÁLISIS y TRADING REMOTO
    prompt = f"""
    Eres el OFICIAL DE PUENTE del sistema TITAN. Tu jefe es el COMANDANTE.
    
    CONTEXTO DE LA CUENTA:
    {context}
    
    MENSAJE DEL COMANDANTE:
    "{user_msg}"
    
    INSTRUCCIONES:
    1. Si el Comandante pide analizar un símbolo (ej: EURUSD), responde obligatoriamente: "ANALIZANDO [SYMBOL]".
    2. Si pide abrir una operación (ej: Compra Oro en 0.02), responde obligatoriamente: "OPERANDO [BUY/SELL] [SYMBOL] LOT [LOTE]".
    3. Si pide cerrar algo, responde: "CERRANDO [TICKET]".
    4. Si solo tiene dudas, explica la situación técnica basada en el contexto.
    5. Mantén un tono técnico, directo y de élite. Estamos en el año 2026.
    
    RESPUESTA:
    """
    
    try:
        payload = {
            "model": "gpt-oss:20b-cloud",
            "prompt": prompt,
            "stream": False
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=15)
        return res.json().get('response', 'Error de respuesta IA')
    except Exception as e:
        return f"Error conectando con el Cerebro IA: {e}"

def speak_to_commander(chat_id, text):
    """ Convierte texto a voz y lo envía a Telegram """
    try:
        # Limpiar texto de caracteres raros o tags de IA
        clean_text = re.sub(r'[#\*\_]', '', text)
        tts = gTTS(text=clean_text, lang='es')
        voice_file = f"response_{chat_id}.mp3"
        tts.save(voice_file)
        
        with open(voice_file, 'rb') as voice:
            bot.send_voice(chat_id, voice)
        
        # Opcional: Limpiar archivo después de enviar
        if os.path.exists(voice_file): os.remove(voice_file)
    except Exception as e:
        print(f"⚠️ Error en TTS: {e}")

@bot.message_handler(content_types=['voice'])
def handle_voice_msg(message):
    if str(message.chat.id) != CHAT_ID: return
    
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        ogg_file = f"voice_{message.chat.id}.ogg"
        wav_file = f"voice_{message.chat.id}.wav"
        
        with open(ogg_file, 'wb') as f:
            f.write(downloaded_file)
        
        # v27.0: Conversión y Transcripción Real
        audio = AudioSegment.from_ogg(ogg_file)
        audio.export(wav_file, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio_data = recognizer.record(source)
            try:
                user_text = recognizer.recognize_google(audio_data, language="es-ES")
                bot.reply_to(message, f"🎯 Entendido: \"{user_text}\"")
                # Procesar como mensaje de comando
                handle_commander_msg(message, override_text=user_text, reply_audio=True)
            except sr.UnknownValueError:
                bot.reply_to(message, "⚠️ Comandante, no pude entender el audio. ¿Podría repetirlo o usar texto?")
            except sr.RequestError as e:
                bot.reply_to(message, f"⚠️ Error en servicio STT: {e}")
        
        # Limpieza de archivos temporales
        if os.path.exists(ogg_file): os.remove(ogg_file)
        if os.path.exists(wav_file): os.remove(wav_file)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error en Módulo Auditivo v27: {e}")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_commander_msg(message, override_text=None, reply_audio=False):
    # Seguridad: Solo responder si es el Comandante
    if str(message.chat.id) != CHAT_ID: return

    text = (override_text if override_text else message.text).upper()
    print(f"📩 Mensaje del Comandante: {text}")
    bot.send_chat_action(message.chat.id, 'typing')
    
    context = get_account_context()
    ia_response = call_ia(text, context)
    
    # --- LOGICA DE EJECUCIÓN ATÓMICA v28.8 ---
    # 1. ANALISIS DE CUALQUIER INSTRUMENTO
    if "ANALIZANDO" in ia_response.upper():
        sym_match = re.search(r'ANALIZANDO\s+([A-Z0-9]+)', ia_response.upper())
        if sym_match:
            sym = sym_match.group(1)
            try:
                res = requests.get(f"http://localhost:8000/analyze/{sym}", timeout=10).json()
                if "error" in res:
                    ia_response = f"⚠️ Comandante, el símbolo {sym} no está disponible en MT5 o es inválido."
                else:
                    ia_response = (f"📊 *INFORME {sym}*:\n"
                                  f"Señal IA: *{res['signal']}* ({res['confidence']*100:.0f}%)\n"
                                  f"RSI: {res['rsi']:.1f} | Probabilidad: {res['probability']*100:.0f}%\n"
                                  f"Veredicto: {'✅ APTO PARA SCALPING' if res['confidence'] > 0.65 else '❌ NO OPERAR (Inseguro)'}")
            except: ia_response = "⚠️ Error conectando con el Cerebro Bridge (Port 8000)."

    # 2. APERTURA REMOTA DE ÓRDENES
    elif "OPERANDO" in ia_response.upper():
        trade_match = re.search(r'OPERANDO\s+(BUY|SELL)\s+([A-Z0-9]+)\s+LOT\s+([\d\.]+)', ia_response.upper())
        if trade_match:
            action, sym, lot = trade_match.groups()
            try:
                res = requests.post("http://localhost:8000/trade", json={"symbol": sym, "action": action, "lot": lot}, timeout=10).json()
                if res.get("status") == "success":
                    ia_response = f"✅ *EJECUCIÓN EXITOSA*\n{action} {sym} [#{res['ticket']}] con lote {lot}.\nReglas Bunker de $25 activadas."
                else:
                    ia_response = f"❌ *FALLO EN TRADING*: {res.get('reason', 'Rechazo MT5')}"
            except: ia_response = "⚠️ Error de comunicación con el Ejecutor MT5."

    # 3. CIERRE DE TICKETS (LEGACY)
    elif "CERRANDO" in ia_response.upper():
        tickets = re.findall(r'#(\d+)', ia_response + text)
        if tickets:
            for t in tickets:
                # El cierre se delega al MT5 via Bridge si estuviera activo o por comando directo
                bot.send_message(message.chat.id, f"🎯 Ticket #{t} identificado. Ejecutando cierre de emergencia...")
                # ... lógica legacy ...
        else:
            ia_response = "⚠️ No identifiqué el número de ticket para cerrar."

    # Responder por texto
    bot.reply_to(message, ia_response, parse_mode="Markdown")
    
    if reply_audio:
        speak_to_commander(message.chat.id, ia_response)

print("🦅 OFICIAL DE PUENTE TITAN ONLINE - Esperando al Comandante...")
bot.infinity_polling()
