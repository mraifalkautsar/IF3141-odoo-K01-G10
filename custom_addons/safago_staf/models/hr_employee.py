from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee' # Teknik menambah kolom ke model asli

    telegram_id = fields.Char(string='Telegram ID')
    is_verified = fields.Boolean(string='Telegram Verified', default=False)