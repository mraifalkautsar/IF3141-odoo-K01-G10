from odoo import http
from odoo.http import request

class SafagoTelegramAPI(http.Controller):
    @http.route('/api/safago/mulai_produksi', type='json', auth='public', methods=['POST'], csrf=False)
    def mulai_produksi_telegram(self, **kwargs):
        token_asli = request.env['ir.config_parameter'].sudo().get_param('safago.telegram_token')
        token_dikirim = request.httprequest.headers.get('Authorization')
        
        if not token_asli or token_dikirim != token_asli:
            return {'status': 'error', 'pesan': 'Akses ditolak: Token tidak valid!'}
        
        kode_roll = kwargs.get('barcode_value', '')

        # Ekstrak ID roll dari deep link kalau formatnya URL
        if 'scan_' in kode_roll:
            kode_roll = kode_roll.split('scan_')[-1]

        spk_ditemukan = request.env['safago.spk'].sudo().search([
            ('state', '=', 'draft'),
            ('roll_kain_id.name', '=', kode_roll)  # cari by name, bukan barcode_value
        ])
        
        if spk_ditemukan:
            spk_ditemukan.action_mulai_produksi()
            kumpulan_nama_spk = ', '.join(spk_ditemukan.mapped('name'))
            return {
                'status': 'sukses', 
                'pesan': f'Produksi SPK {kumpulan_nama_spk} dimulai. Stok {kode_roll} berhasil dipotong.'
            }
            
        return {
            'status': 'error', 
            'pesan': f'Gagal: Tidak ditemukan draf SPK untuk roll kain {kode_roll}.'
        }
    @http.route('/api/safago/selesai_produksi', type='json', auth='public', methods=['POST'], csrf=False)
    def selesai_produksi_telegram(self, **kwargs):
        token_asli = request.env['ir.config_parameter'].sudo().get_param('safago.telegram_token')
        token_dikirim = request.httprequest.headers.get('Authorization')
        
        if not token_asli or token_dikirim != token_asli:
            return {'status': 'error', 'pesan': 'Akses ditolak: Token tidak valid!'}
        
        kode_roll = kwargs.get('roll_kain_id')
        
        spk_ditemukan = request.env['safago.spk'].sudo().search([
            ('state', '=', 'proses'), 
            ('roll_kain_id.name', '=', kode_roll)
        ])
        
        if spk_ditemukan:
            spk_ditemukan.action_selesai_produksi()
            kumpulan_nama_spk = ', '.join(spk_ditemukan.mapped('name'))
            return {
                'status': 'sukses', 
                'pesan': f'Proses produksi SPK {kumpulan_nama_spk} selesai. Stok {kode_roll} berhasil diperbarui.'
            }
                
        return {
                'status': 'error', 
                'pesan': f'Gagal: Tidak ditemukan SPK yang sedang diproses untuk roll kain {kode_roll}.'
            }