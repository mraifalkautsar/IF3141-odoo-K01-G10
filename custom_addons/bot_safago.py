import telebot
import requests
import os
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

bot = telebot.TeleBot(os.getenv('SAFAGO_TELEGRAM_BOT_TOKEN'))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"BINGO! ID Obrolan ruangan ini adalah: {message.chat.id}")
    
    teks = message.text.strip()
    
    if teks.startswith('/start scan_'):
        barcode_value = teks.replace('/start scan_', '').strip()
        proses_barcode(message, barcode_value)
    else:
        bot.reply_to(message, "Sistem SAFAGO siap. Silakan pindai QR Code untuk memulai produksi.")

@bot.message_handler(commands=['selesai'])
def proses_selesai_produksi(message):
    teks_mentah = message.text
    id_roll_lain = teks_mentah.replace('/selesai ', '').strip()
    kirim_selesai_produksi(message, id_roll_lain)

@bot.callback_query_handler(func=lambda call: call.data.startswith('selesai_'))
def handle_tombol_selesai(call):
    barcode_value = call.data.replace('selesai_', '')
    bot.answer_callback_query(call.id, "Memproses penyelesaian...")
    kirim_selesai_produksi(call.message, barcode_value)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pilihspk_'))
def handle_pilih_spk(call):
    data = call.data.split('_')
    spk_id = data[1]
    barcode_value = data[2] if len(data) > 2 else ""

    bot.answer_callback_query(call.id, "Memulai SPK yang dipilih...")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "spk_id": spk_id
        }
    }

    try:
        response = requests.post(os.getenv('URL_ODOO_MULAI_PRODUKSI_BY_ID'), json=payload, headers=headers)
        data_resp = response.json()

        if 'result' in data_resp:
            hasil = data_resp['result']
            pesan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal.')

            if hasil.get('status') == 'sukses':
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(
                    "✅ Selesai Produksi",
                    callback_data=f"selesai_{barcode_value}"
                ))
                bot.edit_message_text(pesan, call.message.chat.id, call.message.message_id, reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, pesan)
        elif 'error' in data_resp:
            bot.send_message(call.message.chat.id, f"Error Odoo: {data_resp['error'].get('message')}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Gagal terhubung: {e}")

def kirim_selesai_produksi(message, barcode_value):
    url_target = os.getenv('URL_ODOO_SELESAI_PRODUKSI')
    
    header = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "roll_kain_id": barcode_value
        }
    }
    
    try:
        response = requests.post(url_target, headers=header, json=payload)
        
        try:
            data = response.json()
        except ValueError:
            bot.reply_to(message, "Gagal: Peladen Odoo merespons dengan galat HTML. Harap RESTART kontainer web Odoo Anda.")
            return
        
        if 'result' in data:
            hasil = data['result']
            pesan_balasan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal pada Odoo.')
            
            if hasil.get('status') == 'sukses':
                bot.reply_to(message, pesan_balasan)
                bot.send_message(chat_id=os.getenv('SAFAGO_QC_REPORT_CHAT_ID'), text=pesan_balasan)
            else:
                bot.reply_to(message, pesan_balasan)
                
        elif 'error' in data:
            bot.reply_to(message, f"Eror Internal Odoo: {data['error'].get('message', 'Cek log server')}")
        else:
            bot.reply_to(message, "Error: Format balasan dari Odoo tidak sesuai.")
            
    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung atau sistem bot mengalami eror: {e}")

def proses_barcode(message, barcode_value):
    bot.reply_to(message, f"Mengecek data untuk {barcode_value}...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "barcode_value": barcode_value
        }
    }
    
    try:
        response = requests.post(os.getenv('URL_ODOO_MULAI_PRODUKSI'), json=payload, headers=headers)
        try:
            data = response.json()
        except ValueError:
            bot.reply_to(message, "Gagal: Server Odoo merespons dengan galat HTML.")
            return
        
        if 'result' in data:
            hasil = data['result']
            pesan_balasan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal.')
            
            if hasil.get('status') == 'sukses':
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(
                    "✅ Selesai Produksi",
                    callback_data=f"selesai_{barcode_value}"
                ))
                bot.reply_to(message, pesan_balasan, reply_markup=markup)
            elif hasil.get('status') == 'pilih':
                markup = InlineKeyboardMarkup()
                for spk in hasil.get('list_spk', []):
                    markup.add(InlineKeyboardButton(
                        text=f"Proses {spk['name']}",
                        callback_data=f"pilihspk_{spk['id']}_{barcode_value}"
                    ))
                bot.reply_to(message, pesan_balasan, reply_markup=markup)
            else:
                bot.reply_to(message, pesan_balasan)
                
        elif 'error' in data:
            pesan_balasan = f"Error Odoo: {data['error'].get('message', 'Cek log server')}"
            bot.reply_to(message, pesan_balasan)
        else:
            bot.reply_to(message, "Error: Format balasan tidak sesuai.")
            
    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung: {e}")

@bot.message_handler(func=lambda message: True)
def proses_scan_qr(message):
    barcode_value = message.text.strip()
    proses_barcode(message, barcode_value)

print("Bot Telegram SAFAGO sedang berjalan dan siap menerima pindaian...")
bot.infinity_polling()