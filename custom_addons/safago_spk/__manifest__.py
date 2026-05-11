{
    'name': 'Safago SPK Extension',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['safago_roll_kain'], # Wajib bergantung pada modul kain Anda
    'data': [
        'security/ir.model.access.csv',
        'security/safago_spk_security.xml',
        'views/safago_spk_views.xml'
    ],
    'installable': True,
}
