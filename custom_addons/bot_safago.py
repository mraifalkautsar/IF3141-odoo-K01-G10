import telebot
import requests
import os
from dotenv import load_dotenv

load_dotenv()

bot = telebot.TeleBot(os.getenv('SAFAGO_TELEGRAM_BOT_TOKEN'))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Baris ini akan mencetak ID grup secara langsung ke terminal Anda
    print(f"BINGO! ID Obrolan ruangan ini adalah: {message.chat.id}")
    
    teks = message.text.strip()
    
    # Cek apakah ini hasil link scan dari QR
    if teks.startswith('/start scan_'):
        barcode_value = teks.replace('/start scan_', '').strip()
        proses_barcode(message, barcode_value)
    else:
        bot.reply_to(message, "Sistem SAFAGO siap. Silakan pindai QR Code atau ketik barcode_value untuk memulai produksi.")

@bot.message_handler(commands=['selesai'])
def proses_selesai_produksi(message):
    teks_mentah = message.text
    # Gunakan .strip() untuk membuang spasi tak terlihat di akhir teks
    id_roll_lain = teks_mentah.replace('/selesai ', '').strip()
    
    url_target = os.getenv('URL_ODOO_SELESAI_PRODUKSI')
    
    header = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "roll_kain_id": id_roll_lain
        }
    }
    
    try:
        response = requests.post(url_target, headers=header, json=payload)
        
        # Perlindungan tambahan jika Odoo membalas dengan HTML (Galat Server)
        try:
            data = response.json()
        except ValueError:
            bot.reply_to(message, "Gagal: Peladen Odoo merespons dengan galat HTML. Harap RESTART kontainer web Odoo Anda.")
            return
        
        if 'result' in data:
            hasil = data['result']
            pesan_balasan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal pada Odoo.')
            
            # Pengecekan status sekarang diarahkan ke variabel 'hasil'
            if hasil.get('status') == 'sukses':
                bot.reply_to(message, pesan_balasan)
                # Notifikasi ke grup QC jika berhasil
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
    bot.reply_to(message, f"Memproses pemotongan stok untuk {barcode_value}...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "barcode_value": barcode_value # jadinya gak cuma nampilin id roll kain aja tapi nampilin link/value dari barcode
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
        elif 'error' in data:
            pesan_balasan = f"Error Odoo: {data['error'].get('message', 'Cek log server')}"
        else:
            pesan_balasan = "Error: Format balasan tidak sesuai."
            
        bot.reply_to(message, pesan_balasan)
        
    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung: {e}")

@bot.message_handler(func=lambda message: True)
def proses_scan_qr(message):
    barcode_value = message.text.strip()
    proses_barcode(message, barcode_value)

print("Bot Telegram SAFAGO sedang berjalan dan siap menerima pindaian...")
bot.infinity_polling()