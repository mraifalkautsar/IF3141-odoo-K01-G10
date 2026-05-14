from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import io
import qrcode


class SafagoRollKain(models.Model):
    _name = 'safago.roll.kain'
    _description = 'Data Master Roll Kain'

    name = fields.Char(
        string='ID/Nomor Roll',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    jenis_kain = fields.Char(string='Jenis Kain', required=True)
    warna = fields.Char(string='Warna', required=True)
    sisa_stok_yard = fields.Float(string='Sisa Stok (Yard)', default=0.0)
    quality_state = fields.Selection([
        ('normal', 'Normal'),
        ('cacat_review', 'Cacat/Review'),
        ('layak_pakai', 'Layak Pakai'),
        ('reject', 'Reject'),
    ], string='Status Kualitas', default='normal', required=True)

    barcode_value = fields.Char(
        string='Barcode/QR Value',
        copy=False,
        index=True,
        readonly=True,
    )
    qr_code_image = fields.Binary(
        string='QR Code',
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'ID/Nomor Roll harus unik.'),
        ('barcode_value_unique', 'UNIQUE(barcode_value)', 'Barcode value harus unik.'),
    ]

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

    @api.constrains('sisa_stok_yard')
    def _check_sisa_stok_yard(self):
        for roll in self:
            if roll.sisa_stok_yard < 0:
                raise ValidationError('Sisa stok roll kain tidak boleh negatif.')

    @api.model_create_multi
    def create(self, vals_list):
        bot_username = "safago_notif_bot"
        for vals in vals_list:
            if vals.get('sisa_stok_yard', 0) <= 0:
                raise ValidationError('Sisa stok awal roll kain harus lebih besar dari 0 yard.')
            
            if vals.get('name', 'New') == 'New':
                seq = self.env['ir.sequence'].next_by_code('safago.roll.kain.barcode')
                deep_link = f"https://t.me/{bot_username}?start=scan_{seq}"
                vals['name'] = seq
                vals['barcode_value'] = seq
                vals['qr_code_image'] = self._build_qr_image(deep_link)
        return super().create(vals_list)

    def action_save_and_reload(self):
        if self.barcode_value and not self.qr_code_image:
            self.write({'qr_code_image': self._build_qr_image(self.barcode_value)})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print_barcode_label(self):
        return self.env.ref('safago_roll_kain.action_report_roll_kain_barcode').report_action(self)
