#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres ****************************************************************
db_src = "coheliance8"
db_dst = "coheliance14"
#******************************************************************************

cnx,cr=GetCR(db_src)
db_migre = db_dst+'_migre'
SQL="DROP DATABASE "+db_migre+";CREATE DATABASE "+db_migre+" WITH TEMPLATE "+db_dst
cde='echo "'+SQL+'" | psql postgres'
lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
db_dst = db_migre

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)





#sys.exit()


tables=[
    'account_account',
    'account_account_tax_default_rel',
    #'account_account_template',
    #'account_account_template_tax_rel',
    'account_account_type',
    'account_analytic_account',
    'account_bank_statement',
    'account_bank_statement_line',
    #'account_chart_template',
    'account_fiscal_position',
    'account_fiscal_position_tax',
    #'account_fiscal_position_tax_template',
    #'account_fiscal_position_template',
    'account_journal',
    #'account_move',
    #'account_move_line',
    'account_payment_term',
    'account_payment_term_line',
    'account_tax',
    #'account_tax_template',
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
    #'res_country', TODO : Ne pas migrer cette table a cause des traductions
    #'res_country_group',
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
    #'stock_inventory',
    # 'stock_inventory_line',
    'stock_location',
    # 'stock_location_route',
    #'stock_move',
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
    default={}
    if table=='account_account':
        rename={
            'user_type': 'user_type_id',
        }
    if table=='account_account_type':
        rename={
            'code'       : 'type',
            'report_type': 'internal_group',
        }
    if table=="account_journal":
        rename={
            'currency'   : 'currency_id',
            'sequence_id': 'sequence',
        }
        default={
            'active'                 : True,
            'invoice_reference_type' :'invoice',
            'invoice_reference_model': 'odoo',
        }
    if table=='account_bank_statement_line':
        rename={'name':'payment_ref'}
        default={
            'move_id': 1,
        }
    if table=="account_payment_term":
        default={
            'active': 1,
            'sequence': 1,
        }
    if table=='account_payment_term_line':
        rename={'days2':'day_of_the_month'}
        default={
            'option': 'day_after_invoice_date',
        }
    if table=='account_tax':
        rename={'type':'amount_type'}
        default={
            'tax_group_id': 1,
        }
    if table=='product_attribute':
        rename={'type':'display_type'}
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


# ** Requetes diverses  *******************************************************
SQL="""
    update stock_location set parent_path=name;
    update product_category set parent_path='/' where parent_path is null;
    update product_category set complete_name=name;
    update account_account_type set internal_group='asset' where internal_group='none';
    update account_tax set amount=100*amount;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
# *****************************************************************************


# ** Migration sale_order_tax => account_tax_sale_order_line_rel **************
print('Migration sale_order_tax => account_tax_sale_order_line_rel')
rename={
    'order_line_id': 'sale_order_line_id',
    'tax_id'       : 'account_tax_id',
}
MigrationTable(db_src,db_dst,'sale_order_tax',table_dst='account_tax_sale_order_line_rel',rename=rename)
# *****************************************************************************


#** compute sale_order_line / price_subtotal ***********************************
SQL="UPDATE sale_order_line SET price_subtotal=product_uom_qty*price_unit"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** res_users (id=2) *************************************************************
champs = GetChamps(cr_dst,'res_partner')
champs.remove('id')
champs=','.join(champs)
SQL="""
    INSERT INTO res_partner(id,"""+champs+""")
    SELECT 2,"""+champs+"""
    FROM res_partner WHERE id=3;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

champs = GetChamps(cr_dst,'res_users')
champs.remove('id')
champs.remove('login')
champs=','.join(champs)
SQL="""
    INSERT INTO res_users(id,login,"""+champs+""")
    SELECT 2,'superuser',"""+champs+"""
    FROM res_users WHERE id=1;
    UPDATE res_users set login='__system__', partner_id=2 where id=1;
    UPDATE res_users set login='admin', partner_id=3 where id=2;   
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** siret res_company migré dans res_partner ***********************************
SQL="SELECT siret FROM res_company WHERE id=1"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_partner SET siret='"+row['siret']+"' WHERE id=1"
    cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** res_partner ****************************************************************
SQL="""
    SELECT id,name,supplier,customer
    FROM res_partner
    ORDER BY name
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    customer_rank=supplier_rank='0'
    if row['supplier']:
        supplier_rank='1'
    if row['customer']:
        customer_rank='1'
    SQL="UPDATE res_partner SET customer_rank="+customer_rank+", supplier_rank="+supplier_rank+" WHERE id="+str(row['id'])
    cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


#** product_pricelist_item *****************************************************
SQL="update product_pricelist_item set active='t'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


MigrationResGroups(db_src,db_dst)
MigrationDonneesTable(db_src,db_dst,'res_company')


#** state sale_order **********************************************************
print("state sale_order")
SQL="UPDATE sale_order SET state='sale', invoice_status='invoiced'"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id,name,state FROM sale_order"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    if row['state']=='manual':
        cr_dst.execute("UPDATE sale_order SET invoice_status='to invoice' WHERE id="+str(row["id"]))
    if row['state']=='draft':
        cr_dst.execute("UPDATE sale_order SET state='draft' WHERE id="+str(row["id"]))
    if row['state']=='cancel':
        cr_dst.execute("UPDATE sale_order SET state='cancel' WHERE id="+str(row["id"]))
cnx_dst.commit()
#*******************************************************************************



#** TODO : Je n'arrviais pas à afficher ceraines factures, mais après avoir migré la table account_account, cela a fonctionné
rename={}
default={
    'move_type'  : 'entry',
    'currency_id': 1,
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'currency_id': 1,
}
rename={
    'tax_amount': 'tax_base_amount',
}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)


#** account_account_type ******************************************************
SQL="update account_account_type set type='other' where type not in ('receivable','payable','liquidity')"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************






#** account_invoice_line => account_move **************************************
print("account_invoice => account_move")
SQL="""
    SELECT 
        ai.id,
        ai.move_id,
        ai.number,
        ai.date_invoice,
        ai.type,
        rp.name,
        ai.date_due,
        ai.order_id,
        ai.is_affaire_id,
        ai.is_refacturable,
        ai.is_nom_fournisseur,
        ai.is_personne_concernee_id,
        ai.amount_untaxed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual
    from account_invoice ai inner join res_partner rp on ai.partner_id=rp.id 
    order by ai.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=0
for row in rows:
    ct+=1
    move_id = row['move_id']
    if move_id:
        SQL="""
            UPDATE account_move 
            set 
                invoice_date=%s,
                move_type=%s,
                invoice_partner_display_name=%s,
                invoice_date_due=%s,
                order_id=%s,
                is_affaire_id=%s,
                is_refacturable=%s,
                is_nom_fournisseur=%s,
                is_personne_concernee_id=%s,
                amount_untaxed=%s,
                amount_tax=%s,
                amount_total=%s,
                amount_residual=%s,
                amount_untaxed_signed=%s,
                amount_tax_signed=%s,
                amount_total_signed=%s,
                amount_residual_signed=%s
            where id=%s
        """
        cr_dst.execute(SQL,(
                row['date_invoice'],
                row['type'],
                row['name'],
                row['date_due'],
                 row['order_id'],
                row['is_affaire_id'],
                row['is_refacturable'],
                row['is_nom_fournisseur'],
                row['is_personne_concernee_id'],
                row['amount_untaxed'],
                row['amount_tax'],
                row['amount_total'],
                row['residual'],
                row['amount_untaxed'],
                row['amount_tax'],
                row['amount_total'],
                row['residual'],

                move_id
            )
        )

        SQL="""
            SELECT 
                ail.id,
                ail.product_id,
                ail.name,
                ail.price_unit,
                ail.price_subtotal
            from account_invoice_line ail inner join account_invoice ai on ail.invoice_id=ai.id
            WHERE ai.id="""+str(row['id'])+"""
            order by ail.id
        """
        cr_src.execute(SQL)
        rows2 = cr_src.fetchall()
        nb2=len(rows2)
        ct2=0
        #Comme il n'y a pas de lien entre account_invoice_line et account_move_line, je considère que les id sont dans le même ordre
        for row2 in rows2:
            SQL="""
                UPDATE account_move_line 
                set 
                    name=%s, 
                    is_account_invoice_line_id=%s,
                    price_unit=%s,
                    price_subtotal=%s,
                    price_total=%s,
                    balance=(debit-credit),
                    amount_currency=(debit-credit)
                WHERE id IN (
                    SELECT id
                    FROM account_move_line
                    WHERE move_id=%s and product_id is not null
                    ORDER BY id
                    LIMIT 1 OFFSET %s
                ) 
            """
            cr_dst.execute(SQL,(row2['name'],row2['id'],row2['price_unit'],row2['price_subtotal'],row2['price_subtotal'],move_id,ct2))
            ct2+=1
cnx_dst.commit()
SQL="""
    update account_move_line set price_unit=(credit-debit) where price_unit is null;
    update account_move_line set balance=(debit-credit) where balance is null;
    update account_move_line set amount_currency=balance where amount_currency=0;
    update account_move_line set price_subtotal=(credit-debit) where price_subtotal is null;
    update account_move_line set price_total=(credit-debit) where price_total is null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""UPDATE account_move_line set exclude_from_invoice_tab='t' WHERE product_id is null"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Migration des taxes sur les factures **************************************
print("Migration des taxes sur les factures")
SQL="DELETE FROM account_move_line_account_tax_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT invoice_line_id, tax_id  FROM account_invoice_line_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="SELECT id FROM account_move_line WHERE is_account_invoice_line_id="+str(row['invoice_line_id'])
    cr_dst.execute(SQL)
    rows2 = cr_dst.fetchall()
    for row2 in rows2:
        SQL="""
            INSERT INTO account_move_line_account_tax_rel (account_move_line_id, account_tax_id)
            VALUES (%s,%s)
            ON CONFLICT DO NOTHING
        """
        cr_dst.execute(SQL,[row2['id'],row['tax_id']])
cnx_dst.commit()
#******************************************************************************


#** Correspondance ente id et tax_code_id *************************************
print("Correspondance ente id et tax_code_id")
SQL="select id,tax_code_id from account_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
Id2TaxCodeId={}
for row in rows:
    Id2TaxCodeId[row["tax_code_id"]]=row["id"]
#******************************************************************************


#** Migration account_invoice_tax *********************************************
print("Migration account_invoice_tax")
SQL="delete from account_move_line where tax_line_id is not null"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="""
    SELECT 
        t.id,
        t.invoice_id,
        t.account_id,
        t.company_id,
        t.invoice_id,
        t.base_amount,
        t.tax_code_id,
        t.amount,base,
        t.tax_amount,
        t.base_code_id,
        t.name,
        ai.move_id,
        ai.date_invoice,
        ai.state
    FROM account_invoice_tax t inner join account_invoice ai on t.invoice_id=ai.id
    WHERE ai.move_id is not null
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO account_move_line (
            move_id,
            move_name,
            currency_id,
            date,
            parent_state,
            journal_id,
            company_id,
            company_currency_id,
            account_id,
            quantity,
            price_unit,
            credit,
            balance,
            amount_currency,
            price_subtotal,
            price_total,
            tax_line_id,
            tax_group_id,
            exclude_from_invoice_tab
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
    """
    tax_line_id = Id2TaxCodeId[row['tax_code_id']]
    cr_dst.execute(SQL,[
        row['move_id'],
        row['name'],
        1,
        row['date_invoice'],
        'posted',
        1,
        1,
        1,
        row['account_id'],
        1,
        row['tax_amount'],
        row['tax_amount'],
        -row['tax_amount'],
        -row['tax_amount'],
        row['tax_amount'],
        row['tax_amount'],
        tax_line_id,
        1,
        True,
    ])
cnx_dst.commit()
#******************************************************************************


#** Factures sur les affaires *************************************************
print("Factures sur les affaires")
SQL="""
    SELECT ia.id, ia.account_id, ai.move_id
    FROM is_acompte ia inner join account_invoice ai on ia.account_id=ai.id 
    WHERE ia.account_id is not null
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE is_acompte set account_id='"+str(row['move_id'])+"' where id="+str(row['id'])
    cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Migration country_id dans res_partner ************************************
print("Migration country_id dans res_partner")
SQL="""
    select distinct rp.country_id,rc.name
    from res_partner rp inner join res_country rc on rp.country_id=rc.id 
    where country_id is not null 
"""
cr_src.execute(SQL)
rows_src = cr_src.fetchall()
src2dst={}
for row_src in rows_src:
    SQL="SELECT id FROM res_country WHERE name='"+row_src['name']+"'"
    cr_dst.execute(SQL)
    rows_dst = cr_dst.fetchall()
    for row_dst in rows_dst:
        src2dst[row_src['country_id']]=row_dst['id']
SQL="select id,name,country_id from res_partner where country_id is not null order by name"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    if row['country_id'] in src2dst:
        country_id = src2dst[row['country_id']]
        SQL="UPDATE res_partner SET country_id=%s WHERE id=%s"
        cr_dst.execute(SQL,[country_id,row['id']])
cr_dst.execute("update res_partner set country_id=75 where  country_id=255")
cnx_dst.commit()
# *****************************************************************************


#** Migration traduction name dans product.template **************************************
print("Migration traduction name dans product.template")
MigrationNameTraduction(db_src,db_dst,'product.template,name')
# *****************************************************************************












# # #** Migration mot de passe **************************************************
# TODO : Ne fonctionne pas
# SQL="SELECT id,password_crypt FROM res_users"
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     SQL="UPDATE res_users SET password=%s WHERE id=%s"
#     cr_dst.execute(SQL,[row['password_crypt'],row['id']])
# cnx_dst.commit()
# # #****************************************************************************


#** Réinitialisation du mot de passe *******************************************
SQL="update res_users set password='$pbkdf2-sha512$25000$5rzXmjOG0Lq3FqI0xjhnjA$x8X5biBuQQyzKksioIecQRg29ir6jY2dTd/wGhbE.wrUs/qJlrF1wV6SCQYLiKK1g.cwVCztAf3WfBxvFg6b7w'"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


# ** Migration des pièces jointes *********************************************
SQL="""
    select *
    from ir_attachment 
    where res_model<>'ir.ui.view' 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
SQL="DELETE FROM ir_attachment WHERE res_model<>'ir.ui.view' and res_field is null"
cr_dst.execute(SQL)
for row in rows:
    res_id    = row['res_id']
    res_model = row['res_model']
    if row['res_model']=='account.invoice':
        res_id = InvoiceId2MoveId(cr_src,res_id)
        res_model = 'account.move'
    SQL="""
        INSERT INTO ir_attachment (name,res_model,res_id,company_id,create_date,create_uid,file_size,mimetype,store_fname,type,url,write_date,write_uid)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cr_dst.execute(SQL,[
        row['name'],
        res_model,
        res_id,
        row['company_id'],
        row['create_date'],
        row['create_uid'],
        row['file_size'],
        row['file_type'],
        row['store_fname'],
        row['type'],
        row['url'],
        row['write_date'],
        row['write_uid'],
    ])
cnx_dst.commit()
# *****************************************************************************


# ** image dans res_partner dans ir_attachment ********************************
print("Pour finaliser la migration, il faut démarrer Odoo avec cette commande : ")
print("/opt/odoo-14/odoo-bin -c /etc/odoo/coheliance14.conf")
name = input("Appuyer sur Entrée pour continuer") 
models,uid,password = XmlRpcConnection(db_dst)
SQL="SELECT id,image_small,image,name  from res_partner where image is not null order by name"
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=1
for row in rows:
    ImageField2IrAttachment(models,db_dst,uid,password,"res.partner",row["id"],row["image"])
    print(ct,"/",nb,row["name"])
    ct+=1
#*******************************************************************************








# #** Les traductions des pays ne corresponden plus suite migration table ********
# SQL="DELETE FROM ir_translation WHERE name like 'res.country%'"
# cr_dst.execute(SQL)
# cnx_dst.commit()
# #*******************************************************************************



# # ** ir_attachment ************************************************************
# table = 'ir_attachment'
# rename={
#     'file_type': 'mimetype',
# }
# print('Migration ',table,db_src,db_dst)
# MigrationTable(db_src,db_dst,table,rename=rename)
# SQL="""
#     update ir_attachment set res_field='image_128'  where res_field='image_small';
#     update ir_attachment set res_field='image_1920' where res_field='image';
# """
# cr_dst.execute(SQL)
# cnx_dst.commit()
# #*******************************************************************************


# #** Fusion des tables account_move et account_invoice_line dans account_move **
# cnx_src,cr_src=GetCR(db_src)
# cnx_dst,cr_dst=GetCR(db_dst)

# rename={
# }
# default={
#     # 'move_id'    : 1,
#     'currency_id': 1,
#     # 'account_id' : 1,
# }
# MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)

# SQL="""
#     select ai.id,ai.number,ai.name,ai.move_id 
#     from account_invoice ai inner join account_move am on ai.move_id=am.id 
#     where ai.id>0
#     order by ai.id
# """
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     print(row['number'],row['move_id'])
#     SQL="UPDATE account_move_line WHERE "
# rename={
#     'type'        : 'move_type',
#     'date_invoice': 'invoice_date',
#     'date_due'    : 'invoice_date_due',
# }
# default={
#     'date':'1990-01-01',
#     'name':'MIGRATION',
#     'invoice_partner_display_name': 'MIGRATION',
#     'state': 'draft',
# }
# MigrationTable(db_src,db_dst,'account_invoice', table_dst='account_move', rename=rename,default=default)
# rename={
#     'invoice_id': 'move_id',
# }
# default={
#     'currency_id': 1,
# }
# MigrationTable(db_src,db_dst,'account_invoice_line', table_dst='account_move_line', rename=rename,default=default)


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

