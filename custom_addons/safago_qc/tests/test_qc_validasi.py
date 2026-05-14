import json
from unittest.mock import patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSafagoQcValidasi(TransactionCase):

    def setUp(self):
        super().setUp()
        self.validasi_model = self.env['safago.qc.validasi']
        self.roll = self.env['safago.roll.kain'].create({
            'name': 'ROLL-QC-FINISH',
            'jenis_kain': 'Katun',
            'warna': 'Biru',
            'sisa_stok_yard': 50.0,
        })
        self.staf_qc = self.env['safago.staf'].create({
            'name': 'Staf QC Barang Jadi',
            'telegram_id': '998877',
        })
        self.spk = self.env['safago.spk'].create({
            'name': 'SPK-QC-FINISH',
            'roll_kain_id': self.roll.id,
            'jumlah_pemakaian_yard': 5.0,
        })
        self.spk.write({'state': 'menunggu_qc'})

    def _create_validasi(self, **extra_vals):
        vals = {
            'spk_id': self.spk.id,
            'staf_id': self.staf_qc.id,
            'barcode_value': self.spk.name,
            'hasil_qc': 'lolos',
            'qty_lolos': 5.0,
            'qty_reject': 0.0,
            'catatan': 'Barang jadi sesuai standar.',
        }
        vals.update(extra_vals)
        return self.validasi_model.create(vals)

    def test_selesai_produksi_moves_spk_to_menunggu_qc(self):
        self.spk.write({'state': 'proses'})
        self.spk.action_selesai_produksi()

        self.assertEqual(self.spk.state, 'menunggu_qc')

    def test_lolos_finalizes_spk_and_creates_mock_sync_log(self):
        validasi = self._create_validasi()
        self.assertEqual(self.spk.state, 'validasi_qc')

        validasi.action_finalize()

        self.assertEqual(validasi.state, 'final')
        self.assertEqual(self.spk.state, 'selesai')
        self.assertEqual(validasi.sync_status, 'mock_success')
        self.assertEqual(len(validasi.sync_log_ids), 1)
        payload = json.loads(validasi.sync_log_ids.payload)
        self.assertEqual(payload['qty_barang_jadi'], 5.0)
        self.assertEqual(payload['kode_spk'], self.spk.name)

    def test_parsial_sync_payload_uses_only_qty_lolos(self):
        validasi = self._create_validasi(
            hasil_qc='parsial',
            qty_lolos=3.0,
            qty_reject=2.0,
            catatan='Sebagian perlu rework.',
        )

        validasi.action_finalize()

        self.assertEqual(self.spk.state, 'selesai')
        payload = json.loads(validasi.sync_log_ids.payload)
        self.assertEqual(payload['qty_barang_jadi'], 3.0)
        self.assertEqual(payload['qty_reject'], 2.0)

    def test_reject_finalizes_without_accurate_sync(self):
        validasi = self._create_validasi(
            hasil_qc='reject',
            qty_lolos=0.0,
            qty_reject=5.0,
            catatan='Jahitan tidak sesuai standar.',
        )

        validasi.action_finalize()

        self.assertEqual(validasi.state, 'final')
        self.assertEqual(self.spk.state, 'qc_reject')
        self.assertEqual(validasi.sync_status, 'none')
        self.assertFalse(validasi.sync_log_ids)

    def test_reject_invalid_spk_state(self):
        self.spk.write({'state': 'draft'})

        with self.assertRaises(ValidationError):
            self._create_validasi()

    def test_real_accurate_failure_is_logged_without_rollback_qc(self):
        self.env['ir.config_parameter'].sudo().set_param('safago_qc.accurate_mock_mode', 'false')
        self.env['ir.config_parameter'].sudo().set_param('safago_qc.accurate_api_url', 'https://accurate.invalid/stock')
        self.env['ir.config_parameter'].sudo().set_param('safago_qc.accurate_api_token', 'dummy-token')

        with patch('odoo.addons.safago_qc.models.qc_validasi.requests.post', side_effect=requests.Timeout('timeout')):
            validasi = self._create_validasi()
            validasi.action_finalize()

        self.assertEqual(validasi.state, 'final')
        self.assertEqual(self.spk.state, 'selesai')
        self.assertEqual(validasi.sync_status, 'failed')
        self.assertIn('timeout', validasi.sync_log_ids.response_message)

    def test_retry_sync_requires_non_reject_final_validation(self):
        validasi = self._create_validasi(
            hasil_qc='reject',
            qty_lolos=0.0,
            qty_reject=5.0,
        )
        validasi.action_finalize()

        with self.assertRaises(ValidationError):
            validasi.action_retry_sync()
