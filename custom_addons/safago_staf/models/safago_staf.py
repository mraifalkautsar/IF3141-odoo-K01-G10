from odoo import models, fields

class SafagoStaf(models.Model):
    _name = 'safago.staf'
    _description = 'Data Staf SAFAGO'

    name = fields.Char(string='Nama Staf', required=True)
    telegram_id = fields.Char(string='Telegram ID')
    is_verified = fields.Boolean(string='Telegram Verified', default=False)