{
    'name': 'Luxembourg - Accounting improvements (AbAKUS)',
    'version': '1.1',
    'category': 'Accounting',
    'description': 
    """
    This modules adds some functionalities to the Luxembourg Accounting module. 
    
    Wizards provided by this module:
        - Partner VAT Intra: Enlist the partners with their related VAT and invoiced amounts.

    This module has been developed by Bernard Delhez, intern @ AbAKUS it-solutions, under the control of Valentin Thirion.
    """,
    'depends': [
        'account',
        'base_vat',
        'base_iban',
        'l10n_multilang',
        'l10n_lu_ext',
    ],
    'data': [
        'wizard/l10n_be_vat_intra_view.xml',
        'view/l10n_be_reports.xml',
        'view/report_vatintraprint.xml',
    ],
    'installable': True,
    'author': "Bernard DELHEZ, AbAKUS it-solutions SARL",
    'website': "http://www.abakusitsolutions.eu",
}