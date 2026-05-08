from odoo import models, fields

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    roll_kain_id = fields.Many2one('safago.roll.kain', string='Roll Kain Terkait')
    safago_stage = fields.Selection([
        ('draft_spk', 'Draft SPK'),
        ('cutting', 'Cutting'),
        ('sewing', 'Sewing'),
        ('finishing', 'Finishing'),
        ('waiting_qc', 'Menunggu QC'),
        ('qc_valid', 'QC Valid'),
        ('qc_reject', 'QC Reject'),
        ('done', 'Selesai'),
    ], string='Status Produksi SAFAGO', default='draft_spk', required=True)
