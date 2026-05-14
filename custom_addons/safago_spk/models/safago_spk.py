import logging
import os
from datetime import datetime, time, timedelta
import base64
import io
import qrcode

import requests

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class SafagoSpk(models.Model):
    _name = 'safago.spk'
    _description = 'Surat Perintah Kerja SAFAGO'

    name = fields.Char(string='Nomor SPK', required=True, copy=False, readonly=True, default='New')
    roll_kain_id = fields.Many2one('safago.roll.kain', string='Roll Kain', required=True)
    tanggal_mulai = fields.Date(string='Tanggal Mulai', default=fields.Date.context_today)
    jumlah_pemakaian_yard = fields.Float(string='Jumlah Pemakaian Yard', default=0.0)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('aktif', 'Aktif'),
        ('proses', 'Sedang Diproses'),
        ('cacat_review', 'Cacat/Review'),
        ('cutting', 'Cutting'),
        ('menunggu_qc', 'Menunggu QC'),
        ('validasi_qc', 'Validasi QC'),
        ('qc_reject', 'QC Reject'),
        ('selesai', 'Selesai'),
        ('batal', 'Dibatalkan')
    ], string='Status', default='draft')

    started_at = fields.Datetime(readonly=True, copy=False)
    finished_at = fields.Datetime(readonly=True, copy=False)
    started_by_scan = fields.Boolean(default=False, copy=False)
    finished_by_scan = fields.Boolean(default=False, copy=False)

    deadline_selesai = fields.Datetime(string='Deadline Selesai')
    is_overdue = fields.Boolean(compute='_compute_overdue_status', store=True)
    overdue_hours = fields.Float(compute='_compute_overdue_status', store=True)
    last_alert_at = fields.Datetime(readonly=True, copy=False)
    alert_count = fields.Integer(default=0, readonly=True, copy=False)
    qr_spk_value = fields.Char(string='QR SPK Value', readonly=True, copy=False)
    qr_spk_image = fields.Binary(string='QR SPK', readonly=True, copy=False)

    def action_mulai_produksi_from_scan(self):
        for record in self:
            record.action_mulai_produksi()
            record.write({
                'started_at': fields.Datetime.now(),
                'started_by_scan': True,
            })

    def action_selesai_produksi_from_scan(self):
        for record in self:
            record.action_selesai_produksi()
            record.write({
                'finished_at': fields.Datetime.now(),
                'finished_by_scan': True,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('safago.spk.sequence') or 'New'
        return super(SafagoSpk, self).create(vals_list)
    
    def action_mulai_produksi(self):
        for record in self:            
            record.write({'state': 'proses'})
            sisa_baru = record.roll_kain_id.sisa_stok_yard - record.jumlah_pemakaian_yard
            
            record.roll_kain_id.sudo().write({'sisa_stok_yard': sisa_baru})

    def action_selesai_produksi(self):
        bot_username = "safago_notif_bot"
        for record in self:
            deep_link = f"https://t.me/{bot_username}?start=qc_{record.name}"
            record.write({
                'state': 'menunggu_qc',
                'qr_spk_value': deep_link,
                'qr_spk_image': self._build_qr_image(deep_link),
            })
            record._mark_alert_resolved()

    def action_batal_produksi(self):
        for record in self:
            record.write({'state' : 'batal'})
            sisa_baru = record.roll_kain_id.sisa_stok_yard + record.jumlah_pemakaian_yard
            record.roll_kain_id.sudo().write({'sisa_stok_yard': sisa_baru})
    
    @api.constrains('jumlah_pemakaian_yard', 'roll_kain_id')
    def _validasi_ketersediaan_stok(self):
        for record in self:
            roll = record.roll_kain_id
            if roll and record.jumlah_pemakaian_yard > roll.sisa_stok_yard:
                raise ValidationError('Jumlah pemakaian tidak boleh lebih besar dari sisa stok pada roll kain.')

    @api.constrains('tanggal_mulai', 'deadline_selesai')
    def _check_deadline_after_tanggal_mulai(self):
        for record in self:
            if not record.tanggal_mulai or not record.deadline_selesai:
                continue

            tanggal_mulai_dt = datetime.combine(record.tanggal_mulai, time.min)
            deadline_dt = fields.Datetime.to_datetime(record.deadline_selesai)
            if deadline_dt <= tanggal_mulai_dt:
                raise ValidationError('Deadline selesai harus lebih lambat dari tanggal mulai.')

    def action_confirm(self):
        res = super(SafagoSpk, self).action_confirm()
        if self.state == 'proses':
            for record in self:
                roll = record.roll_kain_id
                if roll and record.jumlah_pemakaian_yard > roll.sisa_stok_yard:
                    raise ValidationError('Jumlah pemakaian tidak boleh lebih besar dari sisa stok pada roll kain.')
        return res

    def write(self, vals):
        res = super(SafagoSpk, self).write(vals)
        for record in self:
            if record.state in ('proses', 'cacat_review', 'cutting'):
                roll = record.roll_kain_id
                if roll and record.jumlah_pemakaian_yard > roll.sisa_stok_yard:
                    raise ValidationError('Jumlah pemakaian tidak boleh lebih besar dari sisa stok pada roll kain.')
        return res

    @api.depends('deadline_selesai', 'state', 'finished_at')
    def _compute_overdue_status(self):
        now = fields.Datetime.now()
        for record in self:
            overdue = False
            overdue_hours = 0.0
            active_states = ('aktif', 'proses', 'cacat_review', 'cutting', 'menunggu_qc', 'validasi_qc', 'qc_reject')
            if record.state in active_states and record.deadline_selesai and not record.finished_at:
                if now > record.deadline_selesai:
                    overdue = True
                    delta = now - record.deadline_selesai
                    overdue_hours = delta.total_seconds() / 3600.0
            record.is_overdue = overdue
            record.overdue_hours = overdue_hours

    def cron_check_overdue_spk(self):
        overdue_spk = self.filtered('is_overdue') if self else self.search([('is_overdue', '=', True)])
        for record in overdue_spk:
            if record._should_send_overdue_alert():
                if record._send_overdue_telegram_alert():
                    record._mark_alert_sent()

    def _should_send_overdue_alert(self):
        self.ensure_one()
        if not self.is_overdue:
            return False
        if not self.last_alert_at:
            return True
        return fields.Datetime.now() - self.last_alert_at >= timedelta(minutes=30)

    def _send_overdue_telegram_alert(self):
        self.ensure_one()
        token = (
            self.env['ir.config_parameter'].sudo().get_param('safago_spk.telegram_bot_token')
            or os.getenv('SAFAGO_TELEGRAM_BOT_TOKEN')
        )
        chat_id = (
            self.env['ir.config_parameter'].sudo().get_param('safago_spk.telegram_chat_id')
            or os.getenv('SAFAGO_QC_REPORT_CHAT_ID')
        )
        token = token.strip() if token else ''
        chat_id = str(chat_id).strip() if chat_id else ''

        if not token or not chat_id:
            _logger.info('Token/chat_id Telegram SPK belum dikonfigurasi.')
            return False

        message = (
            '*ALERT SPK TERLAMBAT*\n\n'
            f'*No. SPK:* {self.name}\n'
            f'*Roll Kain:* {self.roll_kain_id.display_name}\n'
            f'*Deadline:* {self.deadline_selesai}\n'
            f'*Overdue:* {self.overdue_hours:.2f} jam'
        )

        url = f'https://api.telegram.org/bot{token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            _logger.warning('Gagal mengirim alert SPK overdue: %s', error)
            return False

        return True

    def _mark_alert_sent(self):
        self.ensure_one()
        self.write({
            'last_alert_at': fields.Datetime.now(),
            'alert_count': self.alert_count + 1,
        })

    def _mark_alert_resolved(self):
        self.ensure_one()
        self.write({
            'last_alert_at': False,
            'alert_count': 0,
        })
    
    @staticmethod
    def _build_qr_image(value):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(value)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue())