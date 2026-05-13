from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SafagoSpk(models.Model):
    _name = 'safago.spk'
    _description = 'Surat Perintah Kerja SAFAGO'

    name = fields.Char(string='Nomor SPK', required=True, copy=False, readonly=True, default='New')
    roll_kain_id = fields.Many2one('safago.roll.kain', string='Roll Kain', required=True)
    tanggal_mulai = fields.Date(string='Tanggal Mulai', default=fields.Date.context_today)
    jumlah_pemakaian_yard = fields.Float(string='Jumlah Pemakaian Yard', default=0.0)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proses', 'Sedang Diproses'),
        ('selesai', 'Selesai'),
        ('batal', 'Dibatalkan')
    ], string='Status', default='draft')

    started_at = fields.Datetime(readonly=True, copy=False)
    finished_at = fields.Datetime(readonly=True, copy=False)
    started_by_scan = fields.Boolean(default=False, copy=False)
    finished_by_scan = fields.Boolean(default=False, copy=False)

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
        for record in self:
            record.write({'state' : 'selesai'})

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
        if self.state == 'proses':
            for record in self:
                roll = record.roll_kain_id
                if roll and record.jumlah_pemakaian_yard > roll.sisa_stok_yard:
                    raise ValidationError('Jumlah pemakaian tidak boleh lebih besar dari sisa stok pada roll kain.')
        return res

