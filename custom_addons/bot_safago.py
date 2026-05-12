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
    
    bot.reply_to(message, "Sistem SAFAGO siap. Silakan pindai QR Code atau ketik ID Roll Kain (contoh: RK-001) untuk memulai produksi.")

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

@bot.message_handler(func=lambda message: True)
def proses_scan_qr(message):
    id_roll_kain = message.text.strip()
    bot.reply_to(message, f"Memproses pemotongan stok untuk {id_roll_kain} ke server Odoo...")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    
    payload = {
        "params": {
            "roll_kain_id": id_roll_kain
        }
    }
    
    try:
        response = requests.post(os.getenv('URL_ODOO_MULAI_PRODUKSI'), json=payload, headers=headers)
        
        try:
            data = response.json()
        except ValueError:
            bot.reply_to(message, "Gagal: Peladen Odoo merespons dengan galat HTML. Harap RESTART kontainer web Odoo Anda sekarang juga.")
            return
        
        if 'result' in data:
            hasil = data['result']
            pesan_balasan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal pada Odoo.')
        elif 'error' in data:
            pesan_balasan = f"Eror Internal Odoo: {data['error'].get('message', 'Cek log server')}"
        else:
            pesan_balasan = "Error: Format balasan dari Odoo tidak sesuai."
            
        bot.reply_to(message, pesan_balasan)
        
    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung atau sistem bot mengalami eror: {e}")


print("Bot Telegram SAFAGO sedang berjalan dan siap menerima pindaian...")
bot.infinity_polling()