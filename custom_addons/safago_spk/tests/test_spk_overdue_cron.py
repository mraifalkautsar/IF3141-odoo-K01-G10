from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSafagoSpkOverdueCron(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roll = cls.env['safago.roll.kain'].create({
            'name': 'ROLL-OVD',
            'jenis_kain': 'Katun',
            'warna': 'Biru',
            'sisa_stok_yard': 50.0,
        })
        deadline = fields.Datetime.now() - timedelta(hours=2)
        cls.spk = cls.env['safago.spk'].create({
            'name': 'SPK-OVD',
            'roll_kain_id': cls.roll.id,
            'jumlah_pemakaian_yard': 5.0,
            'state': 'proses',
            'deadline_selesai': deadline,
        })
        cls.spk._compute_overdue_status()

    def test_compute_overdue_fields(self):
        self.spk._compute_overdue_status()
        self.assertTrue(self.spk.is_overdue)
        self.assertGreater(self.spk.overdue_hours, 0.0)

    def test_cron_marks_alert_sent(self):
        self.env['ir.config_parameter'].sudo().set_param('safago_spk.telegram_bot_token', 'dummy-token')
        self.env['ir.config_parameter'].sudo().set_param('safago_spk.telegram_chat_id', '12345')

        with patch('odoo.addons.safago_spk.models.safago_spk.requests.post') as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            self.spk.cron_check_overdue_spk()

        self.assertEqual(self.spk.alert_count, 1)
        self.assertTrue(self.spk.last_alert_at)

    def test_cron_respects_cooldown(self):
        self.spk.write({
            'last_alert_at': fields.Datetime.now(),
            'alert_count': 1,
        })
        self.env['ir.config_parameter'].sudo().set_param('safago_spk.telegram_bot_token', 'dummy-token')
        self.env['ir.config_parameter'].sudo().set_param('safago_spk.telegram_chat_id', '12345')

        with patch('odoo.addons.safago_spk.models.safago_spk.requests.post') as mock_post:
            self.spk.cron_check_overdue_spk()

        self.assertEqual(self.spk.alert_count, 1)
        self.assertFalse(mock_post.called)
