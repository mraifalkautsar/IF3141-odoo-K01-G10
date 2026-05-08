from odoo import models, fields

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    production_stage = fields.Selection([
        ('cutting', 'Cutting'),
        ('sewing', 'Sewing'),
        ('finishing', 'Finishing'),
        ('waiting_qc', 'Menunggu QC'),
        ('qc_valid', 'QC Valid'),
        ('qc_reject', 'QC Reject'),
    ], string='Tahap Produksi', default='cutting')
