import json
import logging
import os

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SafagoQcValidasi(models.Model):
    _name = 'safago.qc.validasi'
    _description = 'Validasi QC Barang Jadi'
    _order = 'create_date desc'

    ALLOWED_SPK_STATES = ('menunggu_qc', 'validasi_qc')

    name = fields.Char(string='Nomor Validasi', required=True, default='New', copy=False)
    spk_id = fields.Many2one('safago.spk', string='SPK', required=True)
    staf_id = fields.Many2one('safago.staf', string='Staf QC', required=True)
    barcode_value = fields.Char(string='Barcode', required=True)
    qty_lolos = fields.Float(string='Qty Lolos', default=0.0)
    qty_reject = fields.Float(string='Qty Reject', default=0.0)
    hasil_qc = fields.Selection([
        ('lolos', 'Lolos'),
        ('parsial', 'Parsial'),
        ('reject', 'Reject'),
    ], string='Hasil QC', required=True)
    catatan = fields.Text(string='Catatan')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('final', 'Final'),
    ], string='Status Validasi', default='draft', required=True, copy=False)
    sync_log_ids = fields.One2many(
        'safago.accurate.sync.log',
        'validasi_id',
        string='Log Sinkronisasi Accurate',
        readonly=True,
    )
    sync_status = fields.Selection([
        ('none', 'Belum Ada'),
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('mock_success', 'Mock Success'),
    ], string='Status Sync Accurate', compute='_compute_sync_status')

    @api.depends('sync_log_ids.status', 'sync_log_ids.create_date')
    def _compute_sync_status(self):
        for record in self:
            latest_log = record.sync_log_ids[:1]
            record.sync_status = latest_log.status if latest_log else 'none'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('safago.qc.validasi') or 'New'

        records = super().create(vals_list)
        for record in records:
            if record.spk_id.state not in self.ALLOWED_SPK_STATES:
                raise ValidationError(_(
                    'SPK %(spk)s belum siap divalidasi QC. Status saat ini: %(state)s.'
                ) % {
                    'spk': record.spk_id.display_name,
                    'state': record.spk_id.state,
                })
            if record.spk_id.state == 'menunggu_qc':
                record.spk_id.sudo().write({'state': 'validasi_qc'})
        return records

    @api.constrains('qty_lolos', 'qty_reject', 'hasil_qc')
    def _check_qc_quantities(self):
        for record in self:
            if record.qty_lolos < 0 or record.qty_reject < 0:
                raise ValidationError(_('Qty lolos dan qty reject tidak boleh negatif.'))
            if record.hasil_qc == 'lolos' and (record.qty_lolos <= 0 or record.qty_reject):
                raise ValidationError(_('Hasil lolos wajib memiliki qty lolos > 0 dan qty reject = 0.'))
            if record.hasil_qc == 'parsial' and (record.qty_lolos <= 0 or record.qty_reject <= 0):
                raise ValidationError(_('Hasil parsial wajib memiliki qty lolos > 0 dan qty reject > 0.'))
            if record.hasil_qc == 'reject' and (record.qty_reject <= 0 or record.qty_lolos):
                raise ValidationError(_('Hasil reject wajib memiliki qty reject > 0 dan qty lolos = 0.'))

    def action_finalize(self):
        for record in self:
            if record.state == 'final':
                continue

            record._check_qc_quantities()
            if record.hasil_qc in ('lolos', 'parsial'):
                record.spk_id.sudo().write({'state': 'selesai'})
                record.write({'state': 'final'})
                record._sync_to_accurate()
            else:
                record.spk_id.sudo().write({'state': 'qc_reject'})
                record.write({'state': 'final'})

    def action_retry_sync(self):
        for record in self:
            if record.state != 'final':
                raise ValidationError(_('Validasi QC harus final sebelum sinkronisasi Accurate.'))
            if record.hasil_qc == 'reject':
                raise ValidationError(_('Hasil reject tidak menambah stok barang jadi ke Accurate.'))
            record._sync_to_accurate()

    def _build_accurate_payload(self):
        self.ensure_one()
        return {
            'validasi_id': self.id,
            'nomor_validasi': self.name,
            'spk_id': self.spk_id.id,
            'kode_spk': self.spk_id.name,
            'barcode_value': self.barcode_value,
            'qty_barang_jadi': self.qty_lolos,
            'qty_reject': self.qty_reject,
            'hasil_qc': self.hasil_qc,
            'staf_qc': self.staf_id.name,
        }

    def _sync_to_accurate(self):
        self.ensure_one()
        payload = self._build_accurate_payload()
        payload_json = json.dumps(payload, ensure_ascii=False)
        config = self.env['ir.config_parameter'].sudo()
        api_url = config.get_param('safago_qc.accurate_api_url') or os.getenv('ACCURATE_API_URL')
        api_token = config.get_param('safago_qc.accurate_api_token') or os.getenv('ACCURATE_API_TOKEN')
        mock_mode = config.get_param('safago_qc.accurate_mock_mode') or os.getenv('ACCURATE_MOCK_MODE', 'true')
        mock_enabled = str(mock_mode).strip().lower() in ('1', 'true', 'yes', 'y')

        log_vals = {
            'validasi_id': self.id,
            'payload': payload_json,
            'status': 'pending',
        }

        if mock_enabled or not api_url or not api_token:
            log_vals.update({
                'status': 'mock_success',
                'response_message': 'Mock Accurate aktif atau konfigurasi Accurate belum lengkap.',
                'synced_at': fields.Datetime.now(),
            })
            return self.env['safago.accurate.sync.log'].sudo().create(log_vals)

        try:
            response = requests.post(
                api_url,
                json=payload,
                headers={'Authorization': f'Bearer {api_token}'},
                timeout=15,
            )
            log_vals.update({
                'status': 'success' if response.ok else 'failed',
                'response_message': response.text,
                'synced_at': fields.Datetime.now(),
            })
            if not response.ok:
                _logger.warning('Sinkronisasi Accurate gagal HTTP %s: %s', response.status_code, response.text)
        except requests.RequestException as error:
            log_vals.update({
                'status': 'failed',
                'response_message': str(error),
                'synced_at': fields.Datetime.now(),
            })
            _logger.warning('Sinkronisasi Accurate gagal: %s', error)

        return self.env['safago.accurate.sync.log'].sudo().create(log_vals)
