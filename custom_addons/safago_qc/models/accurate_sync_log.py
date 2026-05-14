from odoo import fields, models


class SafagoAccurateSyncLog(models.Model):
    _name = 'safago.accurate.sync.log'
    _description = 'Log Sinkronisasi Accurate SAFAGO'
    _order = 'create_date desc'

    validasi_id = fields.Many2one(
        'safago.qc.validasi',
        string='Validasi QC',
        required=True,
        ondelete='cascade',
    )
    status = fields.Selection([
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('mock_success', 'Mock Success'),
    ], string='Status Sync', default='pending', required=True)
    payload = fields.Text(string='Payload')
    response_message = fields.Text(string='Response Message')
    synced_at = fields.Datetime(string='Waktu Sync')

    def action_retry(self):
        for record in self:
            record.validasi_id.action_retry_sync()
