from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SafagoRollKain(models.Model):
    _name = 'safago.roll.kain'
    _description = 'Data Master Roll Kain'

    name = fields.Char(string='ID/Nomor Roll', required=True)
    jenis_kain = fields.Char(string='Jenis Kain', required=True)
    warna = fields.Char(string='Warna', required=True)
    sisa_stok_yard = fields.Float(string='Sisa Stok (Yard)', default=0.0)

    @api.constrains('sisa_stok_yard')
    def _check_sisa_stok_yard(self):
        for roll in self:
            if roll.sisa_stok_yard < 0:
                raise ValidationError('Sisa stok roll kain tidak boleh negatif.')
