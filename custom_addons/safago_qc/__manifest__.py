{
    'name': 'Safago Quality Control',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['mrp', 'safago_roll_kain', 'safago_spk', 'safago_staf'],
    'data': [
        'security/safago_qc_security.xml',
        'security/ir.model.access.csv',
        'data/kain_cacat_sequence.xml',
        'views/kain_cacat_views.xml',
    ],
    'installable': True,
}
