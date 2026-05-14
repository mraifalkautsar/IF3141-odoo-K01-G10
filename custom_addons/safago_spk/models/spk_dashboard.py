from odoo import fields, models, tools


class SafagoSpkDashboard(models.Model):
    _name = 'safago.spk.dashboard'
    _description = 'Dashboard Produksi SAFAGO'
    _auto = False
    _order = 'id'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('proses', 'Sedang Diproses'),
        ('selesai', 'Selesai'),
        ('batal', 'Dibatalkan'),
    ], string='Status', readonly=True)
    spk_count = fields.Integer(string='SPK Bulan Ini', readonly=True)
    total_pemakaian_yard = fields.Float(string='Total Yard Bulan Ini', readonly=True)
    avg_pemakaian_yard = fields.Float(string='Rata-Rata Yard Bulan Ini', readonly=True)
    overdue_count = fields.Integer(string='Overdue Bulan Ini', readonly=True)

    previous_spk_count = fields.Integer(string='SPK Bulan Lalu', readonly=True)
    previous_total_pemakaian_yard = fields.Float(string='Total Yard Bulan Lalu', readonly=True)
    previous_avg_pemakaian_yard = fields.Float(string='Rata-Rata Yard Bulan Lalu', readonly=True)
    previous_overdue_count = fields.Integer(string='Overdue Bulan Lalu', readonly=True)

    spk_count_delta = fields.Integer(string='Delta SPK', readonly=True)
    spk_count_delta_percent = fields.Float(string='Delta SPK (%)', readonly=True)
    total_pemakaian_yard_delta = fields.Float(string='Delta Total Yard', readonly=True)
    total_pemakaian_yard_delta_percent = fields.Float(string='Delta Total Yard (%)', readonly=True)
    avg_pemakaian_yard_delta = fields.Float(string='Delta Rata-Rata Yard', readonly=True)
    avg_pemakaian_yard_delta_percent = fields.Float(string='Delta Rata-Rata Yard (%)', readonly=True)
    overdue_count_delta = fields.Integer(string='Delta Overdue', readonly=True)
    overdue_count_delta_percent = fields.Float(string='Delta Overdue (%)', readonly=True)
    spk_count_trend_label = fields.Char(string='Tren SPK', readonly=True)
    total_yard_trend_label = fields.Char(string='Tren Total Yard', readonly=True)
    overdue_trend_label = fields.Char(string='Tren Overdue', readonly=True)

    def _get_dashboard_query(self):
        return """
            WITH periods AS (
                SELECT
                    date_trunc('month', CURRENT_DATE)::date AS current_start,
                    (date_trunc('month', CURRENT_DATE) - interval '1 month')::date AS previous_start
            ),
            states AS (
                SELECT *
                FROM (VALUES
                    (1, 'draft'),
                    (2, 'proses'),
                    (3, 'selesai'),
                    (4, 'batal')
                ) AS state_list(id, state)
            ),
            current_period AS (
                SELECT
                    spk.state,
                    COUNT(spk.id)::integer AS spk_count,
                    COALESCE(SUM(spk.jumlah_pemakaian_yard), 0.0) AS total_pemakaian_yard,
                    COALESCE(AVG(spk.jumlah_pemakaian_yard), 0.0) AS avg_pemakaian_yard,
                    COALESCE(SUM(CASE WHEN spk.is_overdue THEN 1 ELSE 0 END), 0)::integer AS overdue_count
                FROM safago_spk spk
                JOIN periods period ON TRUE
                LEFT JOIN safago_roll_kain roll ON roll.id = spk.roll_kain_id
                WHERE spk.tanggal_mulai >= period.current_start
                    AND spk.tanggal_mulai < (period.current_start + interval '1 month')
                GROUP BY spk.state
            ),
            previous_period AS (
                SELECT
                    spk.state,
                    COUNT(spk.id)::integer AS previous_spk_count,
                    COALESCE(SUM(spk.jumlah_pemakaian_yard), 0.0) AS previous_total_pemakaian_yard,
                    COALESCE(AVG(spk.jumlah_pemakaian_yard), 0.0) AS previous_avg_pemakaian_yard,
                    COALESCE(SUM(CASE WHEN spk.is_overdue THEN 1 ELSE 0 END), 0)::integer AS previous_overdue_count
                FROM safago_spk spk
                JOIN periods period ON TRUE
                LEFT JOIN safago_roll_kain roll ON roll.id = spk.roll_kain_id
                WHERE spk.tanggal_mulai >= period.previous_start
                    AND spk.tanggal_mulai < period.current_start
                GROUP BY spk.state
            ),
            dashboard AS (
                SELECT
                    states.id,
                    states.state,
                    COALESCE(current_period.spk_count, 0)::integer AS spk_count,
                    COALESCE(current_period.total_pemakaian_yard, 0.0) AS total_pemakaian_yard,
                    COALESCE(current_period.avg_pemakaian_yard, 0.0) AS avg_pemakaian_yard,
                    COALESCE(current_period.overdue_count, 0)::integer AS overdue_count,
                    COALESCE(previous_period.previous_spk_count, 0)::integer AS previous_spk_count,
                    COALESCE(previous_period.previous_total_pemakaian_yard, 0.0) AS previous_total_pemakaian_yard,
                    COALESCE(previous_period.previous_avg_pemakaian_yard, 0.0) AS previous_avg_pemakaian_yard,
                    COALESCE(previous_period.previous_overdue_count, 0)::integer AS previous_overdue_count
                FROM states
                LEFT JOIN current_period ON current_period.state = states.state
                LEFT JOIN previous_period ON previous_period.state = states.state
            ),
            metrics AS (
            SELECT
                dashboard.*,
                (dashboard.spk_count - dashboard.previous_spk_count)::integer AS spk_count_delta,
                CASE
                    WHEN dashboard.previous_spk_count = 0 AND dashboard.spk_count = 0 THEN 0.0
                    WHEN dashboard.previous_spk_count = 0 THEN 100.0
                    ELSE ((dashboard.spk_count - dashboard.previous_spk_count)::float
                        / dashboard.previous_spk_count::float) * 100.0
                END AS spk_count_delta_percent,
                dashboard.total_pemakaian_yard - dashboard.previous_total_pemakaian_yard AS total_pemakaian_yard_delta,
                CASE
                    WHEN dashboard.previous_total_pemakaian_yard = 0 AND dashboard.total_pemakaian_yard = 0 THEN 0.0
                    WHEN dashboard.previous_total_pemakaian_yard = 0 THEN 100.0
                    ELSE ((dashboard.total_pemakaian_yard - dashboard.previous_total_pemakaian_yard)
                        / dashboard.previous_total_pemakaian_yard) * 100.0
                END AS total_pemakaian_yard_delta_percent,
                dashboard.avg_pemakaian_yard - dashboard.previous_avg_pemakaian_yard AS avg_pemakaian_yard_delta,
                CASE
                    WHEN dashboard.previous_avg_pemakaian_yard = 0 AND dashboard.avg_pemakaian_yard = 0 THEN 0.0
                    WHEN dashboard.previous_avg_pemakaian_yard = 0 THEN 100.0
                    ELSE ((dashboard.avg_pemakaian_yard - dashboard.previous_avg_pemakaian_yard)
                        / dashboard.previous_avg_pemakaian_yard) * 100.0
                END AS avg_pemakaian_yard_delta_percent,
                (dashboard.overdue_count - dashboard.previous_overdue_count)::integer AS overdue_count_delta,
                CASE
                    WHEN dashboard.previous_overdue_count = 0 AND dashboard.overdue_count = 0 THEN 0.0
                    WHEN dashboard.previous_overdue_count = 0 THEN 100.0
                    ELSE ((dashboard.overdue_count - dashboard.previous_overdue_count)::float
                        / dashboard.previous_overdue_count::float) * 100.0
                END AS overdue_count_delta_percent
            FROM dashboard
            )
            SELECT
                metrics.*,
                CASE
                    WHEN metrics.spk_count_delta < 0 THEN 'Turun '
                    WHEN metrics.spk_count_delta > 0 THEN 'Naik '
                    ELSE 'Tetap '
                END
                    || ROUND(ABS(metrics.spk_count_delta_percent)::numeric, 2)::varchar
                    || '%(' || ABS(metrics.spk_count_delta)::varchar || ') dari bulan lalu'
                    AS spk_count_trend_label,
                CASE
                    WHEN metrics.total_pemakaian_yard_delta < 0 THEN 'Turun '
                    WHEN metrics.total_pemakaian_yard_delta > 0 THEN 'Naik '
                    ELSE 'Tetap '
                END
                    || ROUND(ABS(metrics.total_pemakaian_yard_delta_percent)::numeric, 2)::varchar
                    || '%(' || ROUND(ABS(metrics.total_pemakaian_yard_delta)::numeric, 2)::varchar || ') dari bulan lalu'
                    AS total_yard_trend_label,
                CASE
                    WHEN metrics.overdue_count_delta < 0 THEN 'Turun '
                    WHEN metrics.overdue_count_delta > 0 THEN 'Naik '
                    ELSE 'Tetap '
                END
                    || ROUND(ABS(metrics.overdue_count_delta_percent)::numeric, 2)::varchar
                    || '%(' || ABS(metrics.overdue_count_delta)::varchar || ') dari bulan lalu'
                    AS overdue_trend_label
            FROM metrics
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (%s)
        """ % (self._table, self._get_dashboard_query()))
