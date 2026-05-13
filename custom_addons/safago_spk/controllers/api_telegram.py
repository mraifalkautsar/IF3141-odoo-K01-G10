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

        if 'scan_' in kode_roll:
            kode_roll = kode_roll.split('scan_')[-1]

        spk_ditemukan = request.env['safago.spk'].sudo().search([
            ('state', '=', 'draft'),
            ('roll_kain_id.name', '=', kode_roll)
        ])
        
        if not spk_ditemukan:
            return {
                'status': 'error',
                'pesan': f'Gagal: Tidak ditemukan draf SPK untuk roll kain {kode_roll}.'
            }

        if len(spk_ditemukan) > 1:
            list_spk = [{'id': spk.id, 'name': f"ID:{spk.id} | {spk.jumlah_pemakaian_yard} Yard"} for spk in spk_ditemukan]
            return {
                'status': 'pilih',
                'pesan': f'Ditemukan {len(spk_ditemukan)} SPK draft untuk roll {kode_roll}. Pilih yang mana:',
                'list_spk': list_spk
            }

        spk_ditemukan.action_mulai_produksi_from_scan()
        return {
            'status': 'sukses',
            'pesan': f'Produksi SPK {spk_ditemukan.name} dimulai. Stok {kode_roll} berhasil dipotong.'
        }

    @http.route('/api/safago/mulai_produksi_by_id', type='json', auth='public', methods=['POST'], csrf=False)
    def mulai_produksi_by_id(self, **kwargs):
        token_asli = request.env['ir.config_parameter'].sudo().get_param('safago.telegram_token')
        token_dikirim = request.httprequest.headers.get('Authorization')
        
        if not token_asli or token_dikirim != token_asli:
            return {'status': 'error', 'pesan': 'Akses ditolak: Token tidak valid!'}

        spk_id = kwargs.get('spk_id')
        spk = request.env['safago.spk'].sudo().browse(int(spk_id))

        if not spk.exists() or spk.state != 'draft':
            return {'status': 'error', 'pesan': 'SPK tidak ditemukan atau sudah tidak dalam status draft.'}

        spk.action_mulai_produksi_from_scan()
        return {
            'status': 'sukses',
            'pesan': f'Produksi SPK {spk.name} dimulai. Stok {spk.roll_kain_id.name} berhasil dipotong.'
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
            spk_ditemukan.action_selesai_produksi_from_scan()
            kumpulan_nama_spk = ', '.join(spk_ditemukan.mapped('name'))
            return {
                'status': 'sukses',
                'pesan': f'Proses produksi SPK {kumpulan_nama_spk} selesai. Stok {kode_roll} berhasil diperbarui.'
            }
                
        return {
            'status': 'error',
            'pesan': f'Gagal: Tidak ditemukan SPK yang sedang diproses untuk roll kain {kode_roll}.'
        }