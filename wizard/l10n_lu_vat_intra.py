# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    Adapted by Noviat to
#     - make the 'mand_id' field optional
#     - support Noviat tax code scheme
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import time
import base64

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.report import report_sxw


class partner_vat_intra_lu(osv.osv_memory):
    """
    Partner Vat Intra
    """
    _inherit = "partner.vat.intra"

    def _get_datas_lu(self, cr, uid, ids, context=None):
        """Collects require data for vat intra xml
        :param ids: id of wizard.
        :return: dict of all data to be used to generate xml for Partner VAT Intra.
        :rtype: dict
        """
        if context is None:
            context = {}

        obj_user = self.pool.get('res.users')
        obj_sequence = self.pool.get('ir.sequence')
        obj_partner = self.pool.get('res.partner')
        account_tax_code_obj = self.pool.get('account.tax.code')

        xmldict = {}
        post_code = street = city = country = data_clientinfo = ''
        seq = amount_sum = 0

        wiz_data = self.browse(cr, uid, ids[0], context=context)
        comments = wiz_data.comments

        if wiz_data.tax_code_id:
            data_company = wiz_data.tax_code_id.company_id
        else:
            data_company = obj_user.browse(cr, uid, uid, context=context).company_id

        # Get Company vat
        company_vat = data_company.partner_id.vat
        if not company_vat:
            raise osv.except_osv(_('Insufficient Data!'),_('No VAT number associated with your company.'))
        company_vat = company_vat.replace(' ','').upper()
        issued_by = company_vat[:2]

        if len(wiz_data.period_code) != 6:
            raise osv.except_osv(_('Error!'), _('Period code is not valid.'))

        if not wiz_data.period_ids:
            raise osv.except_osv(_('Insufficient Data!'),_('Please select at least one Period.'))

        p_id_list = obj_partner.search(cr, uid, [('vat','!=',False)], context=context)
        if not p_id_list:
            raise osv.except_osv(_('Insufficient Data!'),_('No partner has a VAT number associated with him.'))

        seq_declarantnum = obj_sequence.get(cr, uid, 'declarantnum')
        dnum = company_vat[2:] + seq_declarantnum[-4:]

        addr = obj_partner.address_get(cr, uid, [data_company.partner_id.id], ['invoice'])
        email = data_company.partner_id.email or ''
        phone = data_company.partner_id.phone or ''

        if addr.get('invoice',False):
            ads = obj_partner.browse(cr, uid, [addr['invoice']])[0]
            city = (ads.city or '')
            post_code = (ads.zip or '')
            if ads.street:
                street = ads.street
            if ads.street2:
                street += ' '
                street += ads.street2
            if ads.country_id:
                country = ads.country_id.code

        if not country:
            country = company_vat[:2]
        if not email:
            raise osv.except_osv(_('Insufficient Data!'),_('No email address associated with the company.'))
        if not phone:
            raise osv.except_osv(_('Insufficient Data!'),_('No phone associated with the company.'))
        xmldict.update({
                        'company_name': data_company.name,
                        'company_vat': company_vat,
                        'vatnum':  company_vat[2:],
                        'mand_id': wiz_data.mand_id,
                        'sender_date': str(time.strftime('%Y-%m-%d')),
                        'street': street,
                        'city': city,
                        'post_code': post_code,
                        'country': country,
                        'email': email,
                        'phone': phone.replace('/','').replace('.','').replace('(','').replace(')','').replace(' ',''),
                        'period': wiz_data.period_code,
                        'period_name': wiz_data.period_ids[0].name,
                        'clientlist': [],
                        'comments': comments,
                        'issued_by': issued_by,
                        })
        
        #search Luxembourg intra tax codes
        codes = []
        account_tax_codes = account_tax_code_obj.search(cr, uid, [('|'),('code','ilike','%b_VB-IC%'),('code','ilike','%b_VP-IC%')])
        if account_tax_codes:
            for tax in account_tax_code_obj.browse(cr, uid, account_tax_codes):
                codes.append(tax.code)
        
        #transform list in tuple for SQL query
        codes = tuple(codes)
        
        cr.execute('''SELECT p.name As partner_name, l.partner_id AS partner_id, p.vat AS vat, t.code AS intra_code,
                      SUM(CASE WHEN t.code in ('48s44','48s46L','48s46T') THEN -l.tax_amount ELSE l.tax_amount END) AS amount
                      FROM account_move_line l
                      LEFT JOIN account_tax_code t ON (l.tax_code_id = t.id)
                      LEFT JOIN res_partner p ON (l.partner_id = p.id)
                      WHERE t.code IN %s
                       AND l.period_id IN %s
                       AND t.company_id = %s
                      GROUP BY p.name, l.partner_id, p.vat, intra_code''', (codes, tuple([p.id for p in wiz_data.period_ids]), data_company.id))                      
        p_count = 0

        for row in cr.dictfetchall():
            if not row['vat']:
                row['vat'] = ''
                p_count += 1

            seq += 1
            amt = row['amount'] or 0.0
            amount_sum += amt

            intra_code = row['intra_code'] #== '44' and 'S' or (row['intra_code'] == '46L' and 'L' or (row['intra_code'] == '46T' and 'T' or ''))

            xmldict['clientlist'].append({
                                        'partner_name': row['partner_name'],
                                        'seq': seq,
                                        'vatnum': row['vat'][2:].replace(' ','').upper(),
                                        'vat': row['vat'],
                                        'country': row['vat'][:2],
                                        'amount': round(amt,2),
                                        'intra_code': row['intra_code'],
                                        'code': intra_code})

        xmldict.update({'dnum': dnum, 'clientnbr': str(seq), 'amountsum': round(amount_sum,2), 'partner_wo_vat': p_count})
        return xmldict

    def create_xml_lu(self, cursor, user, ids, context=None):
        """Creates xml that is to be exported and sent to estate for partner vat intra.
        :return: Value for next action.
        :rtype: dict
        """
        mod_obj = self.pool.get('ir.model.data')
        xml_data = self._get_datas_lu(cursor, user, ids, context=context)
        month_quarter = xml_data['period'][:2]
        year = xml_data['period'][2:]
        data_file = ''

        # Can't we do this by etree?
        data_head = """<?xml version="1.0" encoding="ISO-8859-1"?>
<ns2:IntraConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/IntraConsignment" IntraListingsNbr="1">
    <ns2:Representative>
        <RepresentativeID identificationType="NVAT" issuedBy="%(issued_by)s">%(vatnum)s</RepresentativeID>
        <Name>%(company_name)s</Name>
        <Street>%(street)s</Street>
        <PostCode>%(post_code)s</PostCode>
        <City>%(city)s</City>
        <CountryCode>%(country)s</CountryCode>
        <EmailAddress>%(email)s</EmailAddress>
        <Phone>%(phone)s</Phone>
    </ns2:Representative>""" % (xml_data)
        if xml_data['mand_id']:
            data_head += '\n\t\t<ns2:RepresentativeReference>%(mand_id)s</ns2:RepresentativeReference>' % (xml_data)
        data_comp_period = '\n\t\t<ns2:Declarant>\n\t\t\t<VATNumber>%(vatnum)s</VATNumber>\n\t\t\t<Name>%(company_name)s</Name>\n\t\t\t<Street>%(street)s</Street>\n\t\t\t<PostCode>%(post_code)s</PostCode>\n\t\t\t<City>%(city)s</City>\n\t\t\t<CountryCode>%(country)s</CountryCode>\n\t\t\t<EmailAddress>%(email)s</EmailAddress>\n\t\t\t<Phone>%(phone)s</Phone>\n\t\t</ns2:Declarant>' % (xml_data)
        if month_quarter.startswith('3'):
            data_comp_period += '\n\t\t<ns2:Period>\n\t\t\t<ns2:Quarter>'+month_quarter[1]+'</ns2:Quarter> \n\t\t\t<ns2:Year>'+year+'</ns2:Year>\n\t\t</ns2:Period>'
        elif month_quarter.startswith('0') and month_quarter.endswith('0'):
            data_comp_period+= '\n\t\t<ns2:Period>\n\t\t\t<ns2:Year>'+year+'</ns2:Year>\n\t\t</ns2:Period>'
        else:
            data_comp_period += '\n\t\t<ns2:Period>\n\t\t\t<ns2:Month>'+month_quarter+'</ns2:Month> \n\t\t\t<ns2:Year>'+year+'</ns2:Year>\n\t\t</ns2:Period>'

        data_clientinfo = ''
        for client in xml_data['clientlist']:
            if not client['vatnum']:
                raise osv.except_osv(_('Insufficient Data!'),_('No vat number defined for %s.') % client['partner_name'])
            data_clientinfo +='\n\t\t<ns2:IntraClient SequenceNumber="%(seq)s">\n\t\t\t<ns2:CompanyVATNumber issuedBy="%(country)s">%(vatnum)s</ns2:CompanyVATNumber>\n\t\t\t<ns2:Code>%(code)s</ns2:Code>\n\t\t\t<ns2:Amount>%(amount).2f</ns2:Amount>\n\t\t</ns2:IntraClient>' % (client)

        data_decl = '\n\t<ns2:IntraListing SequenceNumber="1" ClientsNbr="%(clientnbr)s" DeclarantReference="%(dnum)s" AmountSum="%(amountsum).2f">' % (xml_data)

        data_file += data_head + data_decl + data_comp_period + data_clientinfo + '\n\t\t<ns2:Comment>%(comments)s</ns2:Comment>\n\t</ns2:IntraListing>\n</ns2:IntraConsignment>' % (xml_data)
        context = dict(context or {})
        context['file_save'] = data_file

        model_data_ids = mod_obj.search(cursor, user,[('model','=','ir.ui.view'),('name','=','view_vat_intra_save')], context=context)
        resource_id = mod_obj.read(cursor, user, model_data_ids, fields=['res_id'], context=context)[0]['res_id']

        return {
            'name': _('Save'),
            'context': context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'partner.vat.intra',
            'views': [(resource_id,'form')],
            'view_id': 'view_vat_intra_save',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def preview_lu(self, cr, uid, ids, context=None):
        xml_data = self._get_datas_lu(cr, uid, ids, context=context)
        datas = {
             'ids': [],
             'model': 'partner.vat.intra',
             'form': xml_data
        }
        return self.pool['report'].get_action(
            cr, uid, [], 'l10n_lu_improvements.report_l10nvatintraprint', data=datas, context=context
        )


class vat_intra_print_lu(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(vat_intra_print_lu, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
        })

class wrapped_vat_intra_print_lu(osv.AbstractModel):
    _name = 'report.l10n_lu_improvements.report_l10nvatintraprint'
    _inherit = 'report.abstract_report'
    _template = 'l10n_lu_improvements.report_l10nvatintraprint'
    _wrapped_report_class = vat_intra_print_lu