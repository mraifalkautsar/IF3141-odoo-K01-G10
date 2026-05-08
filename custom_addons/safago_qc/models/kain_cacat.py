import io
import os
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import logging
import base64
_logger = logging.getLogger(__name__)

class SafagoKainCacat(models.Model):
    _name = 'safago.kain.cacat'
    _description = 'Laporan Kain Cacat'

    name = fields.Char(string='Nomor Laporan', required=True, default='New')
    spk_id = fields.Many2one('mrp.production', string='Referensi SPK', required=True)
    roll_kain_id = fields.Many2one('safago.roll.kain', string='Roll Kain', required=True)
    staf_id = fields.Many2one('hr.employee', string='Staf Pemeriksa', required=True)
    jumlah_cacat_yard = fields.Float(string='Jumlah Cacat (Yard)', required=True)
    alasan = fields.Text(string='Deskripsi Kerusakan')
    foto_cacat = fields.Binary(string='Foto Bukti Cacat')

    @api.constrains('jumlah_cacat_yard', 'roll_kain_id', 'spk_id')
    def _check_laporan_cacat(self):
        for record in self:
            if record.jumlah_cacat_yard <= 0:
                raise ValidationError(_('Jumlah cacat harus lebih besar dari 0 yard.'))
            if (
                record.spk_id
                and record.roll_kain_id
                and record.spk_id.roll_kain_id
                and record.spk_id.roll_kain_id != record.roll_kain_id
            ):
                raise ValidationError(_('Roll kain laporan harus sama dengan roll kain pada SPK.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('safago.kain.cacat') or 'New'

            roll = self.env['safago.roll.kain'].browse(vals.get('roll_kain_id'))
            jumlah_cacat = vals.get('jumlah_cacat_yard', 0.0)
            self._validate_defect_stock(roll, jumlah_cacat)

            record = super(SafagoKainCacat, self).create([vals])
            record._apply_defect_stock_move(jumlah_cacat)
            record._send_telegram_notification()
            records |= record

        return records

    def write(self, vals):
        self.check_access_rights('write')
        self.check_access_rule('write')

        if len(self) > 1:
            for record in self:
                record.write(vals)
            return True

        self.ensure_one()
        old_roll = self.roll_kain_id
        old_jumlah = self.jumlah_cacat_yard
        new_roll = self.env['safago.roll.kain'].browse(vals.get('roll_kain_id')) if vals.get('roll_kain_id') else old_roll
        new_jumlah = vals.get('jumlah_cacat_yard', old_jumlah)

        stock_fields_changed = 'roll_kain_id' in vals or 'jumlah_cacat_yard' in vals
        if stock_fields_changed:
            available_adjustment = old_jumlah if old_roll == new_roll else 0.0
            self._validate_defect_stock(new_roll, new_jumlah, available_adjustment=available_adjustment)
            self._apply_defect_stock_move(-old_jumlah, roll=old_roll)

        result = super().write(vals)

        if stock_fields_changed:
            self._apply_defect_stock_move(self.jumlah_cacat_yard)

        return result

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')

        for record in self:
            record._apply_defect_stock_move(-record.jumlah_cacat_yard)
        return super().unlink()

    def _validate_defect_stock(self, roll, jumlah_cacat, available_adjustment=0.0):
        if jumlah_cacat <= 0:
            raise ValidationError(_('Jumlah cacat harus lebih besar dari 0 yard.'))
        if not roll:
            return
        available_yard = roll.sisa_stok_yard + available_adjustment
        if jumlah_cacat > available_yard:
            raise ValidationError(_(
                'Jumlah cacat %(jumlah).2f yard melebihi sisa stok roll %(roll)s (%(stok).2f yard).'
            ) % {
                'jumlah': jumlah_cacat,
                'roll': roll.display_name,
                'stok': available_yard,
            })

    def _apply_defect_stock_move(self, quantity, roll=None):
        self.ensure_one()
        target_roll = roll or self.roll_kain_id
        if not target_roll or not quantity:
            return
        target_roll.write({'sisa_stok_yard': target_roll.sisa_stok_yard - quantity})

    def _send_telegram_notification(self):
        self.ensure_one()
        chat_id = self.staf_id.telegram_id
        
        if not chat_id:
            return

        message = (
            f"*LAPORAN KAIN CACAT BARU*\n\n"
            f"*No. Laporan:* {self.name}\n"
            f"*Roll Kain:* {self.roll_kain_id.name}\n"
            f"*Ref SPK:* {self.spk_id.name}\n"
            f"*Jumlah Cacat:* {self.jumlah_cacat_yard} Yard\n"
            f"*Pemeriksa:* {self.staf_id.name}\n"
            f"*Alasan:* {self.alasan or '-'}"
        )

        if self.foto_cacat:
            image_data = base64.b64decode(self.foto_cacat)
            image_file = io.BytesIO(image_data)
            image_file.name = 'cacat_kain.jpg'

            files = {'photo': image_file}
            payload = {
                'chat_id': chat_id,
                'caption': message,
                'parse_mode': 'Markdown'
            }
            self._send_telegram_request('sendPhoto', payload, files=files, timeout=15)
        else:
            payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
            self._send_telegram_request('sendMessage', payload, timeout=10)

    def _send_telegram_request(self, endpoint, payload, files=None, timeout=10):
        token = (
            self.env['ir.config_parameter'].sudo().get_param('safago_qc.telegram_bot_token')
            or os.getenv('SAFAGO_TELEGRAM_BOT_TOKEN')
        )
        token = token.strip() if token else ''
        if not token:
            _logger.info('Token Telegram SAFAGO QC belum dikonfigurasi.')
            return False

        url = f'https://api.telegram.org/bot{token}/{endpoint}'
        try:
            if files:
                response = requests.post(url, data=payload, files=files, timeout=timeout)
            else:
                response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.warning('Gagal mengirim notifikasi Telegram QC: %s', error)
            return False

        return True
