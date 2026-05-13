from unittest.mock import patch

import requests

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSafagoKainCacat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roll_model = cls.env['safago.roll.kain']
        cls.report_model = cls.env['safago.kain.cacat']

        cls.spk_roll = cls.roll_model.create({
            'name': 'ROLL-SPK',
            'jenis_kain': 'Katun',
            'warna': 'Hitam',
            'sisa_stok_yard': 20.0,
        })
        cls.other_roll = cls.roll_model.create({
            'name': 'ROLL-OTHER',
            'jenis_kain': 'Katun',
            'warna': 'Putih',
            'sisa_stok_yard': 10.0,
        })
        cls.spk = cls.env['safago.spk'].create({
            'name': 'SPK-TEST',
            'roll_kain_id': cls.spk_roll.id,
        })
        cls.spk.write({'state': 'proses'})

        cls.employee = cls.env['safago.staf'].create({
            'name': 'Staf QC Test',
            'telegram_id': '12345',
        })

    def _create_report(self, **extra_vals):
        vals = {
            'spk_id': self.spk.id,
            'roll_kain_id': self.spk_roll.id,
            'staf_id': self.employee.id,
            'jumlah_cacat_yard': 2.0,
            'alasan': 'Noda',
        }
        vals.update(extra_vals)
        return self.report_model.create(vals)

    def test_create_report_reduces_stock_and_uses_sequence(self):
        with patch.object(type(self.report_model), '_send_telegram_notification', return_value=None):
            first = self._create_report()
            second = self._create_report(jumlah_cacat_yard=1.0)

        self.assertEqual(self.spk_roll.sisa_stok_yard, 17.0)
        self.assertNotEqual(first.name, 'New')
        self.assertNotEqual(second.name, 'New')
        self.assertNotEqual(first.name, second.name)

    def test_reject_invalid_defect_quantities(self):
        for invalid_qty in (0.0, -1.0, 21.0):
            with self.subTest(invalid_qty=invalid_qty):
                with self.assertRaises(ValidationError):
                    self._create_report(jumlah_cacat_yard=invalid_qty)

    def test_reject_roll_that_does_not_match_spk(self):
        with self.assertRaises(ValidationError):
            self._create_report(roll_kain_id=self.other_roll.id)

    def test_write_and_unlink_reconcile_stock(self):
        with patch.object(type(self.report_model), '_send_telegram_notification', return_value=None):
            report = self._create_report(jumlah_cacat_yard=4.0)

        self.assertEqual(self.spk_roll.sisa_stok_yard, 16.0)
        report.write({'jumlah_cacat_yard': 6.0})
        self.assertEqual(self.spk_roll.sisa_stok_yard, 14.0)
        report.unlink()
        self.assertEqual(self.spk_roll.sisa_stok_yard, 20.0)

    def test_telegram_failure_does_not_rollback_report(self):
        self.env['ir.config_parameter'].sudo().set_param('safago_qc.telegram_bot_token', 'dummy-token')
        with patch('odoo.addons.safago_qc.models.kain_cacat.requests.post', side_effect=requests.Timeout('timeout')):
            report = self._create_report()

        self.assertTrue(report.exists())
        self.assertEqual(self.spk_roll.sisa_stok_yard, 18.0)

    def test_qc_user_cannot_unlink_but_manager_can(self):
        qc_group = self.env.ref('safago_qc.group_safago_qc_user')
        manager_group = self.env.ref('safago_qc.group_safago_qc_manager')
        qc_user = self.env['res.users'].create({
            'name': 'QC User',
            'login': 'qc_user_test',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, qc_group.id])],
        })
        manager_user = self.env['res.users'].create({
            'name': 'QC Manager',
            'login': 'qc_manager_test',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, manager_group.id])],
        })

        with patch.object(type(self.report_model), '_send_telegram_notification', return_value=None):
            report = self._create_report()

        with self.assertRaises(AccessError):
            report.with_user(qc_user).unlink()

        report.with_user(manager_user).unlink()
        self.assertFalse(report.exists())
