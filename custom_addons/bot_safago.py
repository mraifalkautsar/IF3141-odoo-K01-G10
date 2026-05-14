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

    if teks.startswith('/start qc_'):
        spk_name = teks.replace('/start qc_', '').strip()
        proses_qc(message, spk_name)
    elif teks.startswith('/start scan_'):
        barcode_value = teks.replace('/start scan_', '').strip()
        proses_barcode(message, barcode_value)
    else:
        bot.reply_to(message, "Sistem SAFAGO siap. Silakan pindai QR Code untuk memulai.")

def proses_qc(message, spk_name):
    bot.reply_to(message, f"🔍 SPK diterima: *{spk_name}*\nMemproses scan QC...", parse_mode='Markdown')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {"params": {"barcode_value": spk_name}}

    try:
        response = requests.post(os.getenv('URL_ODOO_QC_SCAN'), json=payload, headers=headers)
        data = response.json()

        if 'result' in data:
            hasil = data['result']
            if hasil.get('status') == 'sukses':
                spk = hasil.get('spk', {})
                max_yard = spk.get('jumlah_pemakaian_yard', 0)
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("✅ Lolos", callback_data=f"qc_lolos_{spk['id']}_{max_yard}"),
                    InlineKeyboardButton("⚠️ Parsial", callback_data=f"qc_parsial_{spk['id']}_{max_yard}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"qc_reject_{spk['id']}_{max_yard}")
                )
                pesan = (
                    f"*SPK:* {spk['name']}\n"
                    f"*Roll Kain:* {spk['roll_kain']}\n"
                    f"*Jumlah Yard:* {spk['jumlah_pemakaian_yard']}\n\n"
                    f"Pilih hasil QC:"
                )
                bot.reply_to(message, pesan, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.reply_to(message, hasil.get('pesan', 'Terjadi kesalahan.'))
        elif 'error' in data:
            bot.reply_to(message, f"Error Odoo: {data['error'].get('message', 'Cek log server')}")
        else:
            bot.reply_to(message, "Error: Format balasan tidak sesuai.")

    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('qc_lolos_') or
                                               call.data.startswith('qc_parsial_') or
                                               call.data.startswith('qc_reject_'))
def handle_hasil_qc(call):
    parts = call.data.split('_')
    hasil = parts[1]
    spk_id = parts[2]
    try:
        max_yard = float(parts[3]) if len(parts) > 3 else 0.0
    except ValueError:
        max_yard = 0.0

    bot.answer_callback_query(call.id)
    label = 'reject' if hasil == 'reject' else 'lolos'
    bot.send_message(call.message.chat.id, f"Masukkan qty {label} (angka, maks {max_yard}):")
    bot.register_next_step_handler(
        call.message,
        lambda m: tanya_qty_reject(m, spk_id, hasil, max_yard)
    )

def tanya_qty_reject(message, spk_id, hasil, max_yard):
    try:
        qty = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Format angka tidak valid. Ulangi dari scan QR.")
        return

    if max_yard > 0 and qty > max_yard:
        bot.reply_to(message, f"❌ Qty tidak boleh melebihi jumlah pemakaian yard ({max_yard}). Masukkan ulang:")
        bot.register_next_step_handler(message, lambda m: tanya_qty_reject(m, spk_id, hasil, max_yard))
        return

    if hasil == 'parsial':
        sisa = max_yard - qty
        bot.reply_to(message, f"Masukkan qty reject (angka, maks {sisa}):")
        bot.register_next_step_handler(message, lambda m: tanya_catatan(m, spk_id, hasil, qty, max_yard, qty_reject_input=None))
    else:
        qty_lolos = 0.0 if hasil == 'reject' else qty
        qty_reject = qty if hasil == 'reject' else 0.0
        bot.reply_to(message, "Masukkan catatan (atau ketik '-' jika tidak ada):")
        bot.register_next_step_handler(message, lambda m: submit_qc(m, spk_id, hasil, qty_lolos, qty_reject))

def tanya_catatan(message, spk_id, hasil, qty_lolos, max_yard, qty_reject_input):
    try:
        qty_reject = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Format angka tidak valid. Ulangi dari scan QR.")
        return

    sisa = max_yard - qty_lolos
    if qty_reject > sisa:
        bot.reply_to(message, f"❌ Qty reject tidak boleh melebihi sisa ({sisa}). Masukkan ulang:")
        bot.register_next_step_handler(message, lambda m: tanya_catatan(m, spk_id, hasil, qty_lolos, max_yard, qty_reject_input))
        return

    bot.reply_to(message, "Masukkan catatan (atau ketik '-' jika tidak ada):")
    bot.register_next_step_handler(message, lambda m: submit_qc(m, spk_id, hasil, qty_lolos, qty_reject))

def submit_qc(message, spk_id, hasil_qc, qty_lolos, qty_reject):
    catatan = message.text.strip()
    if catatan == '-':
        catatan = ''

    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {
        "params": {
            "spk_id": spk_id,
            "telegram_id": str(message.from_user.id),
            "hasil_qc": hasil_qc,
            "qty_lolos": qty_lolos,
            "qty_reject": qty_reject,
            "catatan": catatan,
        }
    }

    try:
        response = requests.post(os.getenv('URL_ODOO_QC_SUBMIT'), json=payload, headers=headers)
        data = response.json()

        if 'result' in data:
            hasil = data['result']
            pesan = hasil.get('pesan', 'Terjadi kesalahan.')
            bot.reply_to(message, f"{'✅' if hasil.get('status') == 'sukses' else '❌'} {pesan}")
            if hasil.get('status') == 'sukses':
                bot.send_message(
                    chat_id=os.getenv('SAFAGO_QC_REPORT_CHAT_ID'),
                    text=f"📋 Validasi QC selesai\n{pesan}"
                )
        elif 'error' in data:
            bot.reply_to(message, f"Error Odoo: {data['error'].get('message', 'Cek log server')}")
        else:
            bot.reply_to(message, "Error: Format balasan tidak sesuai.")

    except Exception as e:
        bot.reply_to(message, f"Gagal terhubung: {e}")

@bot.message_handler(commands=['selesai'])
def proses_selesai_produksi(message):
    id_roll = message.text.replace('/selesai ', '').strip()
    kirim_selesai_produksi(message, id_roll)

@bot.callback_query_handler(func=lambda call: call.data.startswith('selesai_'))
def handle_tombol_selesai(call):
    barcode_value = call.data.replace('selesai_', '')
    bot.answer_callback_query(call.id, "Memproses penyelesaian...")
    kirim_selesai_produksi(call.message, barcode_value)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pilihspk_'))
def handle_pilih_spk(call):
    parts = call.data.split('_')
    spk_id = parts[1]
    barcode_value = parts[2] if len(parts) > 2 else ""

    bot.answer_callback_query(call.id, "Memulai SPK yang dipilih...")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {"params": {"spk_id": spk_id}}

    try:
        response = requests.post(os.getenv('URL_ODOO_MULAI_PRODUKSI_BY_ID'), json=payload, headers=headers)
        data = response.json()

        if 'result' in data:
            hasil = data['result']
            pesan = hasil.get('pesan', 'Terjadi kesalahan.')
            if hasil.get('status') == 'sukses':
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(
                    "✅ Selesai Produksi",
                    callback_data=f"selesai_{barcode_value}"
                ))
                bot.edit_message_text(pesan, call.message.chat.id, call.message.message_id, reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, pesan)
        elif 'error' in data:
            bot.send_message(call.message.chat.id, f"Error Odoo: {data['error'].get('message')}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Gagal terhubung: {e}")

def kirim_selesai_produksi(message, barcode_value):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {"params": {"roll_kain_id": barcode_value}}

    try:
        response = requests.post(os.getenv('URL_ODOO_SELESAI_PRODUKSI'), headers=headers, json=payload)
        try:
            data = response.json()
        except ValueError:
            bot.reply_to(message, "Gagal: Peladen Odoo merespons dengan galat HTML.")
            return

        if 'result' in data:
            hasil = data['result']
            pesan_balasan = hasil.get('pesan', 'Terjadi kesalahan tidak dikenal.')
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
        bot.reply_to(message, f"Gagal terhubung: {e}")

def proses_barcode(message, barcode_value):
    bot.reply_to(message, f"🔍 Scan diterima: *{barcode_value}*\nMemproses pemotongan stok...", parse_mode='Markdown')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': os.getenv('TOKEN_API_ODOO')
    }
    payload = {"params": {"barcode_value": barcode_value}}

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
                        text=f"📋 {spk['name']}",
                        callback_data=f"pilihspk_{spk['id']}_{barcode_value}"
                    ))
                bot.reply_to(message, pesan_balasan, reply_markup=markup)
            else:
                bot.reply_to(message, pesan_balasan)

        elif 'error' in data:
            bot.reply_to(message, f"Error Odoo: {data['error'].get('message', 'Cek log server')}")
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