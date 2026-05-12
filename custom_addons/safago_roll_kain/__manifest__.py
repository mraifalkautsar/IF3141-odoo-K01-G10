{
    'name': 'Safago Roll Kain',
    'version': '1.0',
    'summary': 'Modul untuk pengelolaan data roll kain',
    'description': 'Modul ini digunakan untuk mencatat dan mengelola inventaris roll kain.',
    'category': 'Inventory',
    'author': 'G10',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/roll_kain_sequence.xml',
        'views/roll_kain_views.xml',
        'report/roll_kain_barcode_report.xml',
        'report/roll_kain_barcode_templates.xml',
    ],
    'installable': True,
    'application': True,
}
