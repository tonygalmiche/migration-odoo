#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres *****************************************************************
db_src = "coheliance8"
db_dst = "coheliance14"
#*******************************************************************************

cnx,cr=GetCR(db_src)
db_migre = db_dst+'_migre'
SQL="DROP DATABASE "+db_migre+";CREATE DATABASE "+db_migre+" WITH TEMPLATE "+db_dst
cde='echo "'+SQL+'" | psql postgres'
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre


#sys.exit()


tables=[
    # 'account_account',
    # 'account_account_tax_default_rel',
    # 'account_account_template',
    # 'account_account_template_tax_rel',
    # 'account_account_type',
    # 'account_analytic_account',
    # 'account_bank_statement',
    # 'account_bank_statement_line',
    # 'account_chart_template',
    # 'account_fiscal_position',
    # 'account_fiscal_position_tax',
    # 'account_fiscal_position_tax_template',
    # 'account_fiscal_position_template',
    # 'account_journal',
    # 'account_move',
    # 'account_move_line',
    # 'account_payment_term',
    # 'account_payment_term_line',
    # 'account_tax',
    # 'account_tax_template',
    # 'bus_bus',
    # 'calendar_alarm',
    # 'calendar_event_type',
    'crm_lead',
    'decimal_precision',
    'hr_employee',
    # 'ir_act_client',
    # 'ir_act_report_xml',
    # 'ir_act_server',
    # 'ir_act_window',
    # 'ir_act_window_group_rel',
    # 'ir_act_window_view',
    # 'ir_actions',
    # 'ir_actions_todo',
    # 'ir_attachment',
    # 'ir_config_parameter',
    # 'ir_cron',
    # 'ir_filters',
    #'ir_mail_server',
    # 'ir_model',
    # 'ir_model_access',
    # 'ir_model_constraint',
    # 'ir_model_data',
    # 'ir_model_fields',
    # 'ir_model_relation',
    # 'ir_module_category',
    # 'ir_module_module',
    # 'ir_module_module_dependency',
    # 'ir_property',
    # 'ir_rule',
    # 'ir_sequence',
    # 'ir_translation',
    # 'ir_ui_menu',
    # 'ir_ui_menu_group_rel',
    # 'ir_ui_view',
    # 'ir_ui_view_group_rel',
    'is_acompte',
    'is_affaire',
    'is_affaire_intervenant',
    'is_affaire_intervention',
    'is_affaire_vente',
    'is_bilan_pedagogique',
    'is_bilan_pedagogique_financier',
    'is_bilan_pedagogique_type_stagiaire',
    'is_bilan_pedagogique_typologie',
    'is_classification',
    'is_compte_resultat',
    'is_compte_resultat_annee',
    'is_export_compta',
    'is_export_compta_ligne',
    'is_fiche_frais',
    'is_frais',
    'is_frais_ligne',
    'is_import_banque',
    'is_import_banque_cb_attachment_rel',
    'is_import_banque_operation_attachment_rel',
    'is_origine_financement',
    'is_prospective',
    'is_prospective_line',
    'is_region',
    'is_secteur_activite',
    'is_suivi_banque',
    'is_suivi_caisse',
    'is_suivi_tresorerie',
    'is_type_stagiaire_organisme',
    'is_typologie',
    'is_typologie_stagiaire',
    'mail_alias',
    'mail_followers',
    'mail_followers_mail_message_subtype_rel',
    #'mail_mail',
    'mail_message',
    #'mail_message_subtype',
    # 'message_attachment_rel',
    # 'payment_acquirer',
    # 'procurement_group',
    'product_category',
    'product_pricelist',
    'product_pricelist_item',
    'product_product',
    'product_removal',
    'product_supplier_taxes_rel',
    'product_taxes_rel',
    'product_template',
    'project_task_type',
    #'report_paperformat',
    'res_bank',
    #'res_company',
    #'res_company_users_rel',
    'res_country',
    'res_country_group',
    # 'res_country_res_country_group_rel',
    # 'res_country_state',
    # 'res_currency',
    # 'res_currency_rate',
    # 'res_groups',
    # 'res_groups_implied_rel',
    # 'res_groups_report_rel',
    # 'res_groups_users_rel',
    # 'res_lang',
    'res_partner',
    'res_partner_bank',
    'res_partner_category',
    'res_partner_res_partner_category_rel',
    'res_partner_title',
    'res_users',
    #'resource_resource',
    # 'rule_group_rel',
    'sale_order',
    'sale_order_line',
    # 'sale_order_line_invoice_rel',
    'stock_inventory',
    # 'stock_inventory_line',
    'stock_location',
    # 'stock_location_route',
    'stock_move',
    #'stock_picking',
    #'stock_picking_type',
    #'stock_quant',
    # 'stock_route_product',
    # 'stock_route_warehouse',
    'stock_warehouse',
]


for table in tables:
    print('Migration ',table)
    rename={}
    if table=='product_attribute':
        rename={'type':'display_type'}

    default={}
    if table=="product_template":
        default={
            'sale_line_warn'    : 'no-message',
            'purchase_line_warn': 'no-message',
            'tracking'          : 'none',
        }
    if table=="sale_order_line":
        default={
            'customer_lead': 0,
        }
    if table=="product_pricelist":
        default={
            'discount_policy': 'with_discount',
        }
    if table=="product_pricelist_item":
        default={
            'applied_on'   : '3_global',
            'pricelist_id' : 1,
            'compute_price': 'fixed',
        }
    if table=="project_task_type":
        default={
            'legend_blocked': 'Blocked',
            'legend_done'   : 'Ready',
            'legend_normal' : 'In Progress',
        }
    if table=="res_users":
        default={
            'notification_type': 'email',
        }
    if table=="hr_employee":
        default={
            'company_id': 1,
            'active': True,
        }
    if table=="res_company":
        default={
            'fiscalyear_last_day'  : 31,
            'fiscalyear_last_month': 12,
            'account_opening_date' : '2020-01-01',
        }

    if table=="mail_message":
        default={
            'message_type'  : 'notification',
        }

    if table=="res_partner_bank":
        default={
            'partner_id'  : 1,
            'active'  : True,
        }





    MigrationTable(db_src,db_dst,table,rename=rename,default=default)


MigrationResGroups(db_src,db_dst)
MigrationDonneesTable(db_src,db_dst,'res_company')

 

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


#** Réinitialisation du mot de passe *******************************************
SQL="update res_users set password='$pbkdf2-sha512$25000$5rzXmjOG0Lq3FqI0xjhnjA$x8X5biBuQQyzKksioIecQRg29ir6jY2dTd/wGhbE.wrUs/qJlrF1wV6SCQYLiKK1g.cwVCztAf3WfBxvFg6b7w'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** siret res_company migré dans res_partner ***********************************
SQL="SELECT siret FROM res_company WHERE id=1"
cr.execute(SQL)
rows = cr.fetchall()
for row in rows:
    SQL="UPDATE res_partner SET siret='"+row['siret']+"' WHERE id=1"
    cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** Les traductions des pays ne corresponden plus suite migration table ********
SQL="DELETE FROM ir_translation WHERE name like 'res.country%'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************




# #** res_partner ****************************************************************
# SQL="""
#     SELECT id,name,supplier,customer
#     FROM res_partner
#     ORDER BY name
# """
# cr.execute(SQL)
# rows = cr.fetchall()
# for row in rows:
#     customer_rank=supplier_rank='0'
#     if row['supplier']:
#         supplier_rank='1'
#     if row['customer']:
#         customer_rank='1'
#     SQL="UPDATE res_partner SET customer_rank="+customer_rank+", supplier_rank="+supplier_rank+" WHERE id="+str(row['id'])
#     cr_dst.execute(SQL)
# cnx_dst.commit()
# #*******************************************************************************


# #** product_pricelist_item *****************************************************
# SQL="update product_pricelist_item set active='t'"
# cr_dst.execute(SQL)
# cnx_dst.commit()
# #*******************************************************************************


# #** ir_property ****************************************************************
# properties=[
#     ('res.partner','property_payment_term_id'),
#     ('res.partner','property_supplier_payment_term_id')
# ]
# for p in properties:
#     model = p[0]
#     field = p[1]
#     MigrationIrProperty(db_src,db_dst,model,field)
# #*******************************************************************************










# cde="rsync -rva /home/odoo/.local/share/Odoo/filestore/"+db_src+"/ /home/odoo/.local/share/Odoo/filestore/"+db_dst
# lines=os.popen(cde).readlines()

# SQL="""
#     update ir_attachment set res_field='image_128'  where res_field='image_small';
#     update ir_attachment set res_field='image_1920' where res_field='image';
# """
# cnx_dst,cr_dst=GetCR(db_dst)
# cr_dst.execute(SQL)
# cnx_dst.commit()

