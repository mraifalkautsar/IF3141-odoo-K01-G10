from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSafagoSpkDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roll = cls.env['safago.roll.kain'].create({
            'name': 'ROLL-DSH',
            'jenis_kain': 'Katun',
            'warna': 'Hitam',
            'sisa_stok_yard': 500.0,
        })

    def _dashboard_snapshot_by_state(self):
        self.env['safago.spk'].flush_model()
        self.env.invalidate_all()
        dashboard = self.env['safago.spk.dashboard'].search([])
        return {
            line.state: {
                'spk_count': line.spk_count,
                'total_pemakaian_yard': line.total_pemakaian_yard,
                'avg_pemakaian_yard': line.avg_pemakaian_yard,
                'overdue_count': line.overdue_count,
                'previous_spk_count': line.previous_spk_count,
                'previous_total_pemakaian_yard': line.previous_total_pemakaian_yard,
                'previous_avg_pemakaian_yard': line.previous_avg_pemakaian_yard,
                'previous_overdue_count': line.previous_overdue_count,
                'spk_count_delta': line.spk_count_delta,
                'spk_count_delta_percent': line.spk_count_delta_percent,
                'overdue_count_delta': line.overdue_count_delta,
                'overdue_count_delta_percent': line.overdue_count_delta_percent,
            }
            for line in dashboard
        }

    def _create_spk(self, name, tanggal_mulai, state, yard, deadline=False):
        spk = self.env['safago.spk'].create({
            'name': name,
            'roll_kain_id': self.roll.id,
            'tanggal_mulai': tanggal_mulai,
            'jumlah_pemakaian_yard': yard,
            'state': state,
            'deadline_selesai': deadline,
        })
        spk._compute_overdue_status()
        return spk

    def _expected_percent(self, current, previous):
        if previous == 0 and current == 0:
            return 0.0
        if previous == 0:
            return 100.0
        return ((current - previous) / previous) * 100.0

    def test_dashboard_aggregates_current_and_previous_month(self):
        before = self._dashboard_snapshot_by_state()

        today = fields.Date.today()
        previous_month = today.replace(day=1) - timedelta(days=1)
        previous_date = previous_month.replace(day=1)
        overdue_deadline = fields.Datetime.now() - timedelta(hours=1)

        self._create_spk('SPK-DSH-DRAFT-CURRENT', today, 'draft', 10.0)
        self._create_spk('SPK-DSH-PROSES-CURRENT', today, 'proses', 5.0, overdue_deadline)
        self._create_spk('SPK-DSH-PROSES-PREVIOUS', previous_date, 'proses', 2.0)
        self._create_spk('SPK-DSH-SELESAI-PREVIOUS', previous_date, 'selesai', 8.0)

        after = self._dashboard_snapshot_by_state()

        self.assertEqual(after['draft']['spk_count'], before['draft']['spk_count'] + 1)
        self.assertEqual(after['draft']['previous_spk_count'], before['draft']['previous_spk_count'])
        self.assertAlmostEqual(
            after['draft']['total_pemakaian_yard'],
            before['draft']['total_pemakaian_yard'] + 10.0,
        )

        self.assertEqual(after['proses']['spk_count'], before['proses']['spk_count'] + 1)
        self.assertEqual(after['proses']['previous_spk_count'], before['proses']['previous_spk_count'] + 1)
        self.assertEqual(after['proses']['overdue_count'], before['proses']['overdue_count'] + 1)
        self.assertAlmostEqual(
            after['proses']['total_pemakaian_yard'],
            before['proses']['total_pemakaian_yard'] + 5.0,
        )
        self.assertAlmostEqual(
            after['proses']['previous_total_pemakaian_yard'],
            before['proses']['previous_total_pemakaian_yard'] + 2.0,
        )

        self.assertEqual(after['selesai']['spk_count'], before['selesai']['spk_count'])
        self.assertEqual(after['selesai']['previous_spk_count'], before['selesai']['previous_spk_count'] + 1)
        self.assertAlmostEqual(
            after['selesai']['previous_total_pemakaian_yard'],
            before['selesai']['previous_total_pemakaian_yard'] + 8.0,
        )

        for line in after.values():
            self.assertEqual(line['spk_count_delta'], line['spk_count'] - line['previous_spk_count'])
            self.assertAlmostEqual(
                line['spk_count_delta_percent'],
                self._expected_percent(line['spk_count'], line['previous_spk_count']),
            )
            self.assertEqual(line['overdue_count_delta'], line['overdue_count'] - line['previous_overdue_count'])
            self.assertAlmostEqual(
                line['overdue_count_delta_percent'],
                self._expected_percent(line['overdue_count'], line['previous_overdue_count']),
            )
