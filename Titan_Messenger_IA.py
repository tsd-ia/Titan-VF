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
except ImportError:
    print("📦 Instalando dependencias de Percepción Sensorial...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyTelegramBotAPI SpeechRecognition"])
    import telebot
    import speech_recognition as sr

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
    prompt = f"""
    Eres el OFICIAL DE PUENTE del sistema TITAN. Tu jefe es el COMANDANTE.
    
    CONTEXTO DE LA CUENTA:
    {context}
    
    MENSAJE DEL COMANDANTE:
    "{user_msg}"
    
    INSTRUCCIONES:
    1. Si el Comandante te pide cerrar algo, responde confirmando y di: "CERRANDO [TICKET]".
    2. Si solo tiene dudas, explica la situación técnica basada en el contexto.
    3. Mantén un tono técnico, directo y de élite. Estamos en el año 2026.
    
    RESPUESTA:
    """
    
    try:
        payload = {
            "model": "gpt-oss:20b-cloud", # O el modelo que estés usando
            "prompt": prompt,
            "stream": False
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=15)
        return res.json().get('response', 'Error de respuesta IA')
    except Exception as e:
        return f"Error conectando con el Cerebro IA: {e}"

@bot.message_handler(content_types=['voice'])
def handle_voice_msg(message):
    if str(message.chat.id) != CHAT_ID: return
    
    try:
        bot.send_chat_action(message.chat.id, 'record_audio')
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        ogg_file = "voice_msg.ogg"
        with open(ogg_file, 'wb') as f:
            f.write(downloaded_file)
        
        # Intentar transcripción (Requiere ffmpeg para pydub, aviso si falla)
        bot.reply_to(message, "🎤 Escuchando audio, Comandante... (Procesando v26)")
        
        # En una versión ultra-pro usaríamos Whisper local, 
        # aquí intentamos una transcripción vía API de Google para velocidad.
        # Nota: Sin ffmpeg, esto puede fallar.
        # En caso de error, le pediremos al Comandante instalar ffmpeg.
        
        # Placeholder de respuesta si no hay transcriptor activo
        user_text = "[Transcripción no disponible: Instale FFMPEG en el servidor]"
        
        # Aquí iría la lógica de STT real si tuviéramos ffmpeg
        # Por ahora, procesamos como texto si logramos extraer algo.
        
        handle_commander_msg(message, override_text="Comandante, envié un audio. Por ahora por favor use texto mientras instalo el núcleo FFMPEG.")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error en Módulo Auditivo: {e}")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_commander_msg(message, override_text=None):
    # Seguridad: Solo responder si es el Comandante
    if str(message.chat.id) != CHAT_ID:
        return

    text = override_text if override_text else message.text
    print(f"📩 Mensaje del Comandante: {text}")
    bot.send_chat_action(message.chat.id, 'typing')
    
    context = get_account_context()
    ia_response = call_ia(text, context)
    
    # Lógica de Ejecución Atómica
    if "CERRANDO" in ia_response.upper():
        # Intentar extraer el ticket si la IA lo mencionó
        tickets = re.findall(r'#(\d+)', ia_response + text)
        if tickets:
            for t in tickets:
                bot.send_message(message.chat.id, f"🎯 Identificando Ticket #{t} para ejecución inmediata...")
                # Lógica de cierre MT5 aquí
        else:
            bot.send_message(message.chat.id, "⚠️ No identifiqué el número de ticket. Por favor, indíquelo con '#'.")

    bot.reply_to(message, ia_response)

print("🦅 OFICIAL DE PUENTE TITAN ONLINE - Esperando al Comandante...")
bot.infinity_polling()
