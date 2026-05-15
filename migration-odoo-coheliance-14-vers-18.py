#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Traitements des arguments pour indiquer la base à traiter *****************
if len(sys.argv)!=2:
    print("Indiquez en argument la base à traiter (coheliance ou coheliance-formation)")
    sys.exit()
soc = sys.argv[1]
if soc not in ["coheliance","coheliance-formation"]:
    print("LA base à traiter doit-être coheliance ou coheliance-formation")
    sys.exit()
base=sys.argv[1]
#******************************************************************************

#** Paramètres ****************************************************************
db_src = "%s14"%base
db_dst = "%s18"%base
print(db_src,'=>',db_dst)
#******************************************************************************


cnx,cr=GetCR(db_src)
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
debut=datetime.now()
debut = Log(debut, "Début migration")




#sys.exit()



#** res_partner ***************************************************************
MigrationTable(db_src,db_dst,'res_partner_title',text2jsonb=True)
default={
    'autopost_bills': 'ask',
}
MigrationTable(db_src,db_dst,'res_partner',text2jsonb=True,default=default)
MigrationTable(db_src,db_dst,"res_partner_bank")
#******************************************************************************

#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************

#** res_users : chatter_position **********************************************
cr_dst.execute("update res_users set chatter_position='bottom'" )
cnx_dst.commit()
#******************************************************************************

#** res_groups ****************************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
MigrationResGroups(db_src,db_dst)
# #****************************************************************************

#** res_groups_users_rel : Ajoute des utilisateurs dans les nouveaux groupes **
AddUserGroupToOtherGroup(db_dst, "group_user"           , "group_allow_export")     # Export pour employés
AddUserGroupToOtherGroup(db_dst, "group_account_manager", "group_account_readonly") # Compta complète pour comptable
AddUserGroupToOtherGroup(db_dst, "group_account_manager", "group_account_user")     # Compta complète pour comptable
#******************************************************************************

#** L'utilisateur ne peut pas avoir plus d'un type d'utilisateur **************
#** Recherche des types d'uilisateurs
SQL="select id,name->>'en_US' as name from ir_module_category where name->>'en_US'='User types'" # where name->>'en_US'='User types'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
category_id=False
for row in rows:
    category_id=row["id"]
if category_id:
    # ** Recherche des utilisateurs avec plusieurs types
    SQL="""
        SELECT uid, array_agg(gid ORDER BY gid) as gids
        FROM res_groups_users_rel
        WHERE gid IN (
                SELECT id FROM res_groups WHERE category_id=%s
            )
        GROUP BY uid
        HAVING count(*) > 1;
    """
    cr_dst.execute(SQL,[category_id])
    rows = cr_dst.fetchall()
    # for row in rows:
    #     print(row)
    #** Si il a plusieurs types, il faut lui mettre le id le plus petit uniquement
    SQL="""
        DELETE FROM res_groups_users_rel r
        USING (                  
            SELECT uid, min(gid) AS keep_gid
            FROM res_groups_users_rel
            WHERE gid IN (
                SELECT id FROM res_groups WHERE category_id=75
            )
            GROUP BY uid
        ) AS sub
        WHERE r.uid = sub.uid
        AND r.gid IN (
            SELECT id FROM res_groups WHERE category_id=75
        )
        AND r.gid <> sub.keep_gid;
    """
    cr_dst.execute(SQL,[category_id])
    cnx_dst.commit()
#******************************************************************************

#** res_currency **************************************************************
MigrationTable(db_src,db_dst,'res_currency',text2jsonb=True)
#******************************************************************************

#** product_template : sale_delay passe de double precision à integer *********
SQL="update product_template set sale_delay=null;"
cr_src.execute(SQL)
cnx_src.commit()
#******************************************************************************

#** product *******************************************************************
default={
    "service_tracking"   : "no",
    "service_to_purchase": None, # A revoir car le champ est passé en json
}
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True, default=default)
MigrationTable(db_src,db_dst,'product_product')
#******************************************************************************

# ** Tables diverses **********************************************************
tables=[
    'is_acompte',
    'is_affaire',
    'is_affaire_intervenant',
    'is_affaire_intervention',
    'is_affaire_vente',
    'is_base_documentaire',
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
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************

#** sale_order ****************************************************************
MigrationTable(db_src,db_dst,'resource_calendar_leaves')
MigrationTable(db_src,db_dst,'sale_order')
MigrationTable(db_src,db_dst,'sale_order_line')
#******************************************************************************

#** account_journal ***********************************************************
table="account_journal"
rename={
}
default={
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
SQL="update account_journal set alias_id=Null;"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************

#** Ajout des paiements entrant et sortant dans les journaux ******************
SQL="select id,code,payment_type,name->>'fr_FR' from account_payment_method;"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
payment_method_inbound_id = payment_method_outbound_id = False
for row in rows:
    if row['payment_type']=='inbound':
        payment_method_inbound_id = row['id']
    if row['payment_type']=='outbound':
        payment_method_outbound_id = row['id']
if payment_method_inbound_id and payment_method_outbound_id:
    SQL="""
        select id,code,name->>'fr_FR' name,type 
        from account_journal 
        where type IN ('bank', 'cash', 'credit') order by id;
    """
    cr_dst.execute(SQL)
    rows = cr_dst.fetchall()

    for row in rows:
        journal_id = row['id']
        SQL="DELETE FROM account_payment_method_line WHERE journal_id=%s"
        cr_dst.execute(SQL,[journal_id])
        SQL="""
            INSERT INTO account_payment_method_line (journal_id, payment_method_id, name, sequence, create_uid, write_uid, create_date, write_date)
            VALUES 
            (%s, %s, 'Manuel', 10, 2, 2, NOW(), NOW()),  -- Méthode inbound
            (%s, %s, 'Manuel', 10, 2, 2, NOW(), NOW());  -- Méthode outbound
        """

        cr_dst.execute(SQL,[journal_id, payment_method_inbound_id, journal_id, payment_method_outbound_id])
    cnx_dst.commit()
#******************************************************************************

#account_payment_term *********************************************************
table="account_payment_term"
default = {
}
MigrationTable(db_src,db_dst,table,default=default,text2jsonb=True)
table="account_payment_term_line"
default = {
    'delay_type': 'days_after',
}
rename={
}
MigrationTable(db_src,db_dst,table,default=default,rename=rename)
#******************************************************************************



# #** Mettre le compte 512xxx pour les réglements par défaut ********************
# account_id = AccountCode2Id(cr_src,'512001')
# SQL="update ir_model_data set res_id=%s where name='1_account_journal_payment_debit_account_id'" # identifiant externe pour le compte 512xxx
# cr_dst.execute(SQL,[account_id])
# cnx_dst.commit()
# #******************************************************************************



#** account_journal ***********************************************************
SQL="""
    update account_journal set default_account_id=(select id from account_account where code_store->>'1'='707100') where code='SAJ';
    update account_journal set default_account_id=(select id from account_account where code_store->>'1'='607100') where code='EXJ';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************









#** Position fiscale **********************************************************
default={
    'company_id': 1,
}
MigrationTable(db_src,db_dst,'account_fiscal_position',default=default,text2jsonb=True)
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
MigrationTable(db_src,db_dst,'account_fiscal_position_account')
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
    'user_type': 'user_type_id',
}
default={
   'account_type': 'income',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
#******************************************************************************


#** account_account : code => code_store **************************************
SQL="SELECT id,code FROM account_account order by code"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    code = row['code']
    val=json.dumps({'1': code})
    SQL="UPDATE account_account SET code_store=%s WHERE id=%s"
    cr_dst.execute(SQL,[val,row['id']])
cnx_dst.commit()
#******************************************************************************





#** account_account : account_type ********************************************
# Correspondance entre Odoo 14 (type, internal_group) et Odoo 18 (account_type)
MAP_ODOO14_18 = {
    # receivable
    ('receivable', 'asset'): 'asset_receivable',
    # payable
    ('payable', 'liability'): 'liability_payable',
    # liquidity
    ('liquidity', 'asset'): 'asset_cash',
    # other
    ('other', 'asset'): 'asset_current',  # ou asset_fixed selon le code?
    ('other', 'liability'): 'liability_current',  # ou liability_non_current selon le code?
    ('other', 'expense'): 'expense',
    ('other', 'income'): 'income',
    ('other', 'off_balance'): None,  # Pas de correspondance directe
}
def get_account_type_18(type_14, internal_group_14):
    """
    Retourne le 'account_type' Odoo 18 à partir du type et internal_group Odoo 14.
    """
    return MAP_ODOO14_18.get((type_14, internal_group_14), None)
SQL = """
    select aa.id, aa.code, aat.type,aat.internal_group
    from account_account aa join  account_account_type aat on aa.user_type_id=aat.id 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:    
    type_14 = row['type']
    internal_group_14 = row['internal_group']
    account_type = get_account_type_18(type_14, internal_group_14)
    #print(row['code'], type_14, internal_group_14, account_type)
    if account_type:
        SQL="UPDATE account_account SET account_type=%s WHERE id=%s"
        cr_dst.execute(SQL,[account_type,row['id']])
cnx_dst.commit()
#******************************************************************************






# account_account account_type ************************************************
cr_dst.execute("update account_account set account_type='asset_current' where code_store->>'1' like '445%'") # Dette à court terme pour la TVA
cnx_dst.commit()
#******************************************************************************


#** account_tax_group *********************************************************
rename={
    #'type':'amount_type'
}
default={
    "company_id": 1,
}
MigrationTable(db_src,db_dst,'account_tax_group',rename=rename,default=default,text2jsonb=True)
#******************************************************************************

#** account_tax **************************************************************
table='account_tax'
rename={
}
default={
  "country_id"  : 75,
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default,text2jsonb=True)
#******************************************************************************

#** account_move_line *********************************************************
#**  Il est necessaire de désativer cet index, car il y a des numéros de factures en double
SQL="""
    DROP INDEX IF EXISTS account_move_unique_name;
    CREATE UNIQUE INDEX account_move_unique_name ON account_move(name, journal_id) WHERE id=0;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "Début account_move_line (2mn)")
rename={
    'amount': 'amount_total'
}
default={
    'move_type'  : 'entry',
    'currency_id': 1,
    'auto_post': 'no',
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'display_type': 'product',
}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
debut = Log(debut, "Fin account_move_line")
#******************************************************************************


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""
    update account_move_line set display_type='payment_term' where date_maturity is not null;
    update account_move_line set display_type='tax'          where tax_line_id is not null;
    update account_move_line set display_type='product'      where product_id is not null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************






#** account *******************************************************************
MigrationTable(db_src,db_dst,'account_full_reconcile')
MigrationTable(db_src,db_dst,'account_partial_reconcile')
MigrationTable(db_src,db_dst,'account_move_line_account_tax_rel')
default={
    'document_type': 'invoice',
}
MigrationTable(db_src,db_dst,'account_tax_repartition_line',default=default)
#******************************************************************************

# account_tax_repartition_line ************************************************
SQL="select id,invoice_tax_id,refund_tax_id from account_tax_repartition_line"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    tax_id=False
    if row['invoice_tax_id']:
        tax_id= row['invoice_tax_id']
        document_type = 'invoice'
    if row['refund_tax_id']:
        tax_id= row['refund_tax_id']
        document_type = 'refund'
    tax_id = row['invoice_tax_id'] or row['refund_tax_id']
    SQL="UPDATE account_tax_repartition_line SET tax_id=%s, document_type=%s WHERE id=%s"
    cr_dst.execute(SQL,[tax_id,document_type,row['id']])
cnx_dst.commit()
#******************************************************************************

#** account_payment *************************************************************
table="account_payment"
default = {
    'company_id': 1,
    'journal_id': 1,            # TODO : A revoir pour mettre le bon journal
    'state'     : 'paid',
    'date'      : '2000-01-01', # TODO  : A revoir
}
MigrationTable(db_src,db_dst,table,default=default)


# account_payment => Champs name, journal_id et date **************************
SQL="select ap.id, am.name, am.journal_id, am.date from account_payment ap join account_move am on ap.move_id=am.id order by ap.id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE account_payment SET name=%s, journal_id=%s, date=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['name'],row['journal_id'],row['date'],row['id']])
cnx_dst.commit()
#******************************************************************************


# account_payment : amount_company_currency_signed ****************************
SQL="""
    select ap.id, ap.payment_type, am.amount_total_signed 
    from account_payment ap join account_move am on ap.move_id=am.id order by ap.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    payment_type = row['payment_type']
    if payment_type=='outbound':
        amount = - row['amount_total_signed']
    else:
        amount = row['amount_total_signed']   
    SQL="UPDATE account_payment SET amount_company_currency_signed=%s WHERE id=%s"
    cr_dst.execute(SQL,[amount,row['id']])
cnx_dst.commit()
#******************************************************************************


#** account_account_res_company_rel *******************************************
SQL="delete from account_account_res_company_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id FROM account_account"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:  
    SQL="""
        INSERT INTO account_account_res_company_rel (account_account_id,res_company_id)
        VALUES (%s,1)
    """
    cr_dst.execute(SQL,[row['id']])
cnx_dst.commit()
#******************************************************************************


#** account_invoice_payment_rel => lien entre facture et facture de paiment ***
SQL="delete from account_move__account_payment"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="""
    select aml1.move_id invoice_id, aml2.move_id facture_paiment_id, am.payment_id
    from account_partial_reconcile apr join account_move_line aml1 on apr.debit_move_id=aml1.id 
                                       join account_move_line aml2 on apr.credit_move_id=aml2.id 
                                       join account_move am on aml2.move_id=am.id
    where am.payment_id is not null
    order by am.payment_id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO account_move__account_payment (invoice_id,payment_id)
        VALUES (%s,%s)
    """
    cr_dst.execute(SQL,[row['invoice_id'],row['payment_id']])
cnx_dst.commit()
#******************************************************************************

# ** account_bank_statement ****************************************************
MigrationTable(db_src,db_dst,'account_bank_statement')
default={
    'journal_id': 1,
    'company_id': 1,
}
MigrationTable(db_src,db_dst,'account_bank_statement_line',default=default)
#******************************************************************************

#Le compte 512001 Banque ne permet pas le lettrage. Modifiez sa configuration pour pouvoir lettrer des écritures.
cr_dst.execute("update account_account set reconcile=true where code_store->>'1' like '512001%'") 
cnx_dst.commit()
#******************************************************************************

#** ir_default ****************************************************************
SetDefaultValue(db_dst, 'res.partner', 'property_account_payable_id'   , '401100')
SetDefaultValue(db_dst, 'res.partner', 'property_account_receivable_id', '411100')
#******************************************************************************

#** ir_property n'existe plus. Les champs sont de type jsonb maintenant *******
MigrationIrProperty2JsonField(db_src,db_dst,'res.partner', property_src='property_account_receivable_id'   , field_dst="property_account_receivable_id")
MigrationIrProperty2JsonField(db_src,db_dst,'res.partner', property_src='property_account_payable_id'      , field_dst="property_account_payable_id")
MigrationIrProperty2JsonField(db_src,db_dst,'res.partner', property_src='property_payment_term_id'         , field_dst="property_payment_term_id")
MigrationIrProperty2JsonField(db_src,db_dst,'res.partner', property_src='property_supplier_payment_term_id', field_dst="property_supplier_payment_term_id")
#******************************************************************************

#** product_category **********************************************************
MigrationTable(db_src,db_dst,'product_category')
property_account_income_categ_id  = JsonAccountCode2Id(cr_dst,'707100')
property_account_expense_categ_id = JsonAccountCode2Id(cr_dst,'607100')
SQL="SELECT id FROM product_category"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    set_json_property(cr_dst,cnx_dst,'product_category', row['id'], 'property_account_income_categ_id' , 1, property_account_income_categ_id)
    set_json_property(cr_dst,cnx_dst,'product_category', row['id'], 'property_account_expense_categ_id', 1, property_account_expense_categ_id)
#******************************************************************************

#** Taxes à la vente et taxe fournisseur sur les articles *********************
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************



#** Sequence des factures et des avoirs ***************************************
SQL="select id,name,sequence_number,sequence_prefix,move_type from account_move where move_type in ('out_refund','out_invoice') order by id"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    name = row['name'].split('-')
    if len(name)==2:
        sequence_number = int(name[1])
        sequence_prefix = '%s-'%name[0]
        SQL="UPDATE account_move SET sequence_prefix=%s, sequence_number=%s WHERE id=%s"
        cr_dst.execute(SQL,[sequence_prefix,sequence_number,row['id']])
cnx_dst.commit()
#******************************************************************************

#** Pièces jointes ************************************************************
MigrationTable(db_src,db_dst,'ir_attachment')
#******************************************************************************





# # #** Wizard création de facture ************************************************
# SQL="""
#     delete from account_payment_register_move_line_rel;
# """
# cr_dst.execute(SQL,[account_id])
# cnx_dst.commit()
# # #******************************************************************************




#** ir_sequence ***************************************************************
SQL="SELECT id,code,implementation,prefix,padding,number_next FROM ir_sequence WHERE code is not null"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    code=row["code"]
    if row["implementation"]=="standard":
        SQL="SELECT id FROM ir_sequence WHERE code='"+code+"'"
        cr_dst.execute(SQL)
        rows2 = cr_dst.fetchall()
        for row2 in rows2:
            seq_id = "%03d" % row["id"]
            ir_sequence = "ir_sequence_"+seq_id
            SQL="SELECT last_value FROM "+ir_sequence
            cr_src.execute(SQL)
            rows3 = cr_src.fetchall()
            for row3 in rows3:
                seq_id = "%03d" % row2["id"]
                ir_sequence = "ir_sequence_"+seq_id
                last_value = row3["last_value"]+1
                SQL="ALTER SEQUENCE "+ir_sequence+" RESTART WITH %s"
                cr_dst.execute(SQL,[last_value])
cnx_dst.commit()
#******************************************************************************


# ** ir_filters ***************************************************************
# ** Si le filtre n'a pas d'action associée il sera visible dans tous les menus du modèle
# ** Et comme l'id de l'action change lors du changement de version, il est préférable de vider ce champ
default = {'sort': []}
MigrationTable(db_src,db_dst,"ir_filters", default=default)
SQL="""
    update ir_filters set action_id=NULL, active='t';
    update ir_filters set user_id=2 where user_id=1;
    update ir_filters set model_id='account.move' where model_id='account.invoice';

"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT id,model_id,domain,context FROM ir_filters"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    if row['model_id']=='account.move':
        domain  = row['domain'].replace('date_invoice','invoice_date')
        context = row['context'].replace('date_invoice','invoice_date')
        SQL="UPDATE ir_filters set domain=%s, context=%s WHERE id=%s"
        cr_dst.execute(SQL,(domain, context,row['id']))
cnx_dst.commit()
#******************************************************************************


#** mail **********************************************************************
SQL="""
    delete from discuss_channel_member;
    delete from mail_tracking_value;
    delete from mail_followers;
    delete from mail_mail where mail_message_id not in (select id from mail_message);
    delete from mail_alias;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationTable(db_src,db_dst,'mail_mail') #,text2jsonb=True)
MigrationTable(db_src,db_dst,'mail_message_subtype',text2jsonb=True)

default = {'partner_id': 1}
MigrationTable(db_src,db_dst,'mail_followers', default=default ) #, where="partner_id is not null")
MigrationTable(db_src,db_dst,'mail_followers_mail_message_subtype_rel')
default={
#    'message_type'  : 'notification',
}
MigrationTable(db_src,db_dst,'mail_message', default=default)
SQL="""
    delete from mail_mail mail where mail.mail_message_id not in (select id from mail_message);
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Récupérer la ligne de ir_attachment pour faire fonctionner les PDF ********
db_vierge = 'odoo18'
table="ir_attachment"
where="name='res.company.scss'"
CopieTable(db_vierge,db_dst,table,where)
#******************************************************************************

# wkhtmltopdf *****************************************************************
SQL="""
  update ir_config_parameter set value='http://127.0.0.1:8069'  where key='web.base.url';
  update ir_config_parameter set value='True'                   where key='web.base.url.freeze';
  INSERT INTO ir_config_parameter (key, value) VALUES ('web.base.url.freeze', 'True')                  ON CONFLICT DO NOTHING;
  INSERT INTO ir_config_parameter (key, value) VALUES ('report.url'         , 'http://127.0.0.1:8069') ON CONFLICT DO NOTHING;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_partner : complete_name ***********************************************
SQL="SELECT rp1.id,rp1.name,rp2.name as parent_name FROM res_partner rp1 left outer join res_partner rp2 on  rp1.parent_id=rp2.id" 
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    name=row['name'] or ''
    parent_name=row['parent_name']
    if parent_name:
        name="%s, %s"%(parent_name,name)
    SQL="UPDATE res_partner SET complete_name=%s WHERE id=%s"
    cr_dst.execute(SQL,[name,row['id']])
cnx_dst.commit()
#******************************************************************************


#** purchase_order ************************************************************
MigrationTable(db_src,db_dst,'purchase_order')
MigrationTable(db_src,db_dst,'purchase_order_line')
MigrationTable(db_src,db_dst,'account_tax_purchase_order_line_rel')
#******************************************************************************


# ** Tables diverses **********************************************************
tables=[
    'sale_order_line_invoice_rel',
    #'product_pricelist',
    #'product_pricelist_item',
    'account_account_account_tag',
    'account_account_tag',
    'account_account_tag_account_move_line_rel',
    'account_account_tag_account_tax_repartition_line_rel',
    'account_account_tax_default_rel',
    'account_group',
    'account_move_purchase_order_rel',
    #'account_reconcile_model',
    #'account_reconcile_model_line',
    'account_tax_sale_order_line_rel', 
]
for table in tables:
    MigrationTable(db_src,db_dst,table,text2jsonb=True)
#******************************************************************************



#** product_supplierinfo ******************************************************
rename={
    'name': ' partner_id',
}
MigrationTable(db_src,db_dst,'product_supplierinfo',rename=rename)
#******************************************************************************

   
#** uom  **********************************************************************
MigrationTable(db_src,db_dst, "uom_category",text2jsonb=True)
MigrationTable(db_src,db_dst, "uom_uom",text2jsonb=True)
#******************************************************************************


#** product_template : Compte de revenus et de charges ************************
SQL="SELECT id,name FROM product_template order by name"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    val = getPropertyValue(db_src,'product.template','property_account_income_id',row['id'])
    if val:
        set_json_property(cr_dst,cnx_dst,'product_template', row['id'], 'property_account_income_id' , 1, val)
    val = getPropertyValue(db_src,'product.template','property_account_expense_id',row['id'])
    if val:
        set_json_property(cr_dst,cnx_dst,'product_template', row['id'], 'property_account_expense_id' , 1, val)
#******************************************************************************


#** res_company ***************************************************************
SQL="""
    update res_company set account_sale_tax_id=null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************


#** res_company : company_registry => is_company_registry *********************
SQL="SELECT id,company_registry FROM res_company" 
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_company SET is_company_registry=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['company_registry'],row['id']])
cnx_dst.commit()
#******************************************************************************


#** Requetes diverses *********************************************************
SQL="""
    update sale_order set team_id=null;
    update sale_order set pricelist_id=null;
    update  account_move set team_id=null;
    delete from account_account_tag_account_tax_repartition_line_rel;
    delete from account_account_account_tag;
    delete from account_tax_sale_order_line_rel where sale_order_line_id not in (select id from sale_order_line);

    update account_payment ap set payment_method_line_id=(select id from account_payment_method_line where journal_id=ap.journal_id and payment_method_id=ap.payment_method_id limit 1);
"""

# Il faut le faire manuellement, sinon ce n'est pas pris en compte
# update decimal_precision set digits=3 where name in ('Product Price','Product Unit of Measure');



cr_dst.execute(SQL,[name,row['id']])
cnx_dst.commit()
#******************************************************************************


#** account_move => Nouveaux champs xx_in_currency_signed *********************
SQL="""
    update account_move set amount_untaxed_in_currency_signed=amount_untaxed_signed;
    update account_move set amount_total_in_currency_signed=amount_total_signed;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# #** crm_phonecall => mail_activity ******************************************
SQL="""
    update mail_activity_type set keep_done=True;
    DELETE FROM mail_activity;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT date,name,partner_id,user_id,create_date,create_uid,write_date,write_uid FROM crm_phonecall WHERE  partner_id is not null order by id"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO mail_activity (
            res_model_id, 
            res_id, 
            is_partner_id,
            activity_type_id, 
            user_id, 
            res_model, 
            res_name, 
            summary, 
            note, 
            date_deadline, 
            date_done, 
            automated, 
            active,
            create_date,
            create_uid,
            write_date,
            write_uid
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    summary = (row['name'] or '')[0:30]
    note    = '<p>' + (row['name'] or '').replace('\n','<br/>') + '</p>'

    cr_dst.execute(SQL,[
        87,
        row['partner_id'],
        row['partner_id'],
        2,
        row['user_id'],
        'res.partner',
        'res_name',
        summary,
        note,
        row['date'],
        row['date'],
        False,
        False,
        row['create_date'],
        row['create_uid'],
        row['write_date'],
        row['write_uid'],
    ])
cnx_dst.commit()
#******************************************************************************


#** crm ***************************************************************
MigrationTable(db_src,db_dst,"crm_lead")
MigrationTable(db_src,db_dst,"crm_stage",text2jsonb=True)
#******************************************************************************






#** mail **********************************************************************
SQL="""
    update crm_lead set team_id=null;
    delete from crm_team;
"""
cr_dst.execute(SQL)
cnx_dst.commit()



debut = Log(debut, "Fin migration")
