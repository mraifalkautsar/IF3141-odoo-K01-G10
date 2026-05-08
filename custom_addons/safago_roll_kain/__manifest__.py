{
    'name': 'Safago Roll Kain',
    'version': '1.0',
    'summary': 'Modul untuk pengelolaan data roll kain',
    'description': 'Modul ini digunakan untuk mencatat dan mengelola inventaris roll kain.',
    'category': 'Inventory',
    'author': 'G10',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/roll_kain_views.xml'
    ],
    'installable': True,
    'application': True,
}
