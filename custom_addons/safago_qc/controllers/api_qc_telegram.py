from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class SafagoQcTelegramAPI(http.Controller):
    ALLOWED_SCAN_STATES = ('menunggu_qc', 'validasi_qc')

    def _check_token(self):
        token_asli = request.env['ir.config_parameter'].sudo().get_param('safago.telegram_token')
        token_dikirim = request.httprequest.headers.get('Authorization')
        return bool(token_asli and token_dikirim == token_asli)

    def _clean_barcode(self, barcode_value):
        barcode = (barcode_value or '').strip()
        if barcode.startswith('/qc '):
            barcode = barcode.replace('/qc ', '', 1).strip()
        if 'scan_' in barcode:
            barcode = barcode.split('scan_')[-1].strip()
        return barcode

    @http.route('/api/safago/qc/scan_barang_jadi', type='json', auth='public', methods=['POST'], csrf=False)
    def scan_barang_jadi(self, **kwargs):
        if not self._check_token():
            return {'status': 'error', 'pesan': 'Akses ditolak: Token tidak valid!'}

        barcode = self._clean_barcode(kwargs.get('barcode_value'))
        if not barcode:
            return {'status': 'error', 'pesan': 'Barcode SPK wajib dikirim.'}

        spk = request.env['safago.spk'].sudo().search([('name', '=', barcode)], limit=1)
        if not spk:
            return {'status': 'error', 'pesan': f'SPK dengan barcode {barcode} tidak ditemukan.'}
        if spk.state not in self.ALLOWED_SCAN_STATES:
            return {
                'status': 'error',
                'pesan': f'SPK {spk.name} belum siap QC barang jadi. Status saat ini: {spk.state}.',
            }

        if spk.state == 'menunggu_qc':
            spk.write({'state': 'validasi_qc'})

        return {
            'status': 'sukses',
            'pesan': f'SPK {spk.name} siap divalidasi QC.',
            'spk': {
                'id': spk.id,
                'name': spk.name,
                'state': spk.state,
                'roll_kain': spk.roll_kain_id.display_name,
                'jumlah_pemakaian_yard': spk.jumlah_pemakaian_yard,
            },
            'pilihan': ['lolos', 'parsial', 'reject'],
        }

    @http.route('/api/safago/qc/submit_validasi', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_validasi(self, **kwargs):
        if not self._check_token():
            return {'status': 'error', 'pesan': 'Akses ditolak: Token tidak valid!'}

        telegram_id = str(kwargs.get('telegram_id') or '').strip()
        staf = request.env['safago.staf'].sudo().search([('telegram_id', '=', telegram_id)], limit=1)
        if not staf:
            return {'status': 'error', 'pesan': f'Telegram ID {telegram_id or "-"} belum terdaftar sebagai staf QC.'}

        try:
            spk = request.env['safago.spk'].sudo().browse(int(kwargs.get('spk_id') or 0))
            qty_lolos = float(kwargs.get('qty_lolos') or 0.0)
            qty_reject = float(kwargs.get('qty_reject') or 0.0)
        except (TypeError, ValueError):
            return {'status': 'error', 'pesan': 'spk_id, qty_lolos, dan qty_reject harus berformat angka.'}

        if not spk.exists():
            return {'status': 'error', 'pesan': 'SPK tidak ditemukan.'}
        if spk.state not in self.ALLOWED_SCAN_STATES:
            return {
                'status': 'error',
                'pesan': f'SPK {spk.name} tidak bisa divalidasi QC dari status {spk.state}.',
            }

        try:
            validasi = request.env['safago.qc.validasi'].sudo().create({
                'spk_id': spk.id,
                'staf_id': staf.id,
                'barcode_value': kwargs.get('barcode_value') or spk.name,
                'hasil_qc': kwargs.get('hasil_qc'),
                'qty_lolos': qty_lolos,
                'qty_reject': qty_reject,
                'catatan': kwargs.get('catatan'),
            })
            validasi.action_finalize()
        except ValidationError as error:
            return {'status': 'error', 'pesan': error.args[0]}

        return {
            'status': 'sukses',
            'pesan': f'Validasi QC {validasi.name} tersimpan. Status SPK: {validasi.spk_id.state}.',
            'validasi_id': validasi.id,
            'hasil_qc': validasi.hasil_qc,
            'spk_state': validasi.spk_id.state,
            'sync_status': validasi.sync_status,
        }
