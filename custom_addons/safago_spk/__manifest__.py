{
    'name': 'Safago SPK Extension',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['mrp', 'safago_roll_kain'], # Wajib bergantung pada modul kain Anda
    'data': [
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml'
    ],
    'installable': True,
}
