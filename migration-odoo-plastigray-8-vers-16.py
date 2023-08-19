#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from datetime import datetime
from migration_fonction import *


#** Traitements des arguments pour indique le site à traiter ******************
if len(sys.argv)!=2:
    print("Indiquez en argument le site à traiter (0, 1, 3 ou 4)")
    sys.exit()
soc = sys.argv[1]
if soc not in ["0","1","3","4"]:
    print("Le site à traiter doit-être 0, 1, 3 ou 4")
    sys.exit()
#******************************************************************************


#TODO : Durée de la migration complète de odoo8 sur vm-postgres à odoo16 su vm-postgres-bullseye (le 24/06/2023)
#                 23/06   | 23/07
#- odoo0       :    1mn   |   2mn
#- odoo1       :  105mn   | 125mn     | 90mn tout seul
#- odoo3       :   90mn   | 100mn
#- odoo4       :   47mn   |  47mn
#- Total en // :  120mn


#TODO : 
# - Revoir les routes pour une livraison (emplacement 01 de déstcage) => Fait manuellement dans odoo1 => A revoir pour les autres sites

#Facturation fournisseur : J'ai du configr maneullement ces 2 champs dans account_journal pour faire une facture d'achat
# pg-odoo16-1=# select id,name,default_account_id,type from account_journal where id=2;
#  id |        name        | default_account_id |   type   
# ----+--------------------+--------------------+----------
#   2 | Journal des achats |                618 | purchase


#TODO : 
#- Sequences des ordres de fabrictions à revoir
#- Faire une vérfication de l'intégrite des bases : cat /media/sf_dev_odoo/migration-odoo/controle-integrite-bdd.sql | psql pg-odoo16-1
#- Recalculer les qt livrées et facturées sur les commandes de ventes


# TODO : Permet de récupérer les tables d'origine d'une base vierge
# db_src = "pg-odoo16"
# db_dst = "pg-odoo16-1"
# #MigrationTable(db_src,db_dst,'stock_route')
# #MigrationTable(db_src,db_dst,'stock_rule')
# MigrationTable(db_src,db_dst,'ir_attachment')


#TODO : Lien entre lignes des commandes clients et lignes des factures à revoir

# #** sale_order_line_invoice_rel ***********************************************
# #ids=InvoiceIds2MoveIds(cr_src)
# cr_dst.execute("delete from sale_order_line_invoice_rel")
# cnx_dst.commit()
# SQL="SELECT order_line_id, invoice_id FROM sale_order_line_invoice_rel"
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     order_line_id=row["order_line_id"]
#     invoice_id=ids[row["invoice_id"]]

#     SQL="SELECT order_line_id, invoice_id FROM sale_order_line_invoice_rel"
#     cr_src.execute(SQL)
#     rows = cr_src.fetchall()

#     print(order_line_id, row["invoice_id"],'=>',invoice_id)
#     SQL="""
#         INSERT INTO sale_order_line_invoice_rel (order_line_id, invoice_id)
#         VALUES(%s,%s)
#     """
#     cr_dst.execute(SQL,[order_line_id, invoice_id])
# cnx_dst.commit()
# debut = Log(debut, "sale_order_line_invoice_rel")
# #******************************************************************************

# sys.exit()

# #pg-odoo16-1=# select id,is_account_invoice_line_id from account_move_line where is_account_invoice_line_id is not null
    # SQL="""
    #     INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing)
    #     VALUES (%s,%s,%s,%s,%s,%s);
    # """


#TODO : Revoir le lien entre les lignes des DEB et les factures
#odoo16-4=# update is_deb_line set invoice_id=NULL;


#TODO une fois migrée à Plastigray les PDF ne fonctionnaitent pas => web.base.url = http://127.0.0.1:8969


#** Paramètres ****************************************************************
db_src    = "pg-odoo8-%s"%soc
db_dst    = "pg-odoo16-%s"%soc
db_vierge = "pg-odoo16"
#******************************************************************************


#cnx,cr=GetCR(db_src)
#SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
#cde="""echo '"""+SQL+"""' | psql postgres"""
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue

cnx_src   , cr_src    = GetCR(db_src)
cnx_dst   , cr_dst    = GetCR(db_dst)
cnx_vierge, cr_vierge = GetCR(db_vierge)
debut=datetime.now()



#MigrationTable(db_src,db_dst,"is_mold_operation_systematique") #TODO : Test modif
#sys.exit()



debut=datetime.now()

debut = Log(debut, "** Début migration %s ***********************************************"%(db_dst))


#** Correction des anomalies dans odoo8 avant migration ***********************
SQL="""
    delete from product_packaging where qty<=0;
"""
cr_src.execute(SQL)
cnx_src.commit()
#******************************************************************************


#** barcode_rule => Nouvelle table pas utile à priori *************************
SQL="update barcode_rule set associated_uom_id=Null"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** decimal_precision *********************************************************
tables=[
"decimal_precision",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


#** res_country ***************************************************************
MigrationTable(db_src,db_dst,'res_country',text2jsonb=True)
#******************************************************************************


#** res_partner_title *********************************************************
MigrationTable(db_src,db_dst,'res_partner_title',text2jsonb=True)
#******************************************************************************


#** res_partner ****************************************************************
MigrationTable(db_src,db_dst,'res_partner')
debut = Log(debut, "res_partner")
#*******************************************************************************


#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_users (id=2) **********************************************************
MigrationTable(db_src,db_dst,"is_database")
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


#** Migration mot de passe ****************************************************
SQL="SELECT id,password_crypt FROM res_users"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE res_users SET password=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['password_crypt'],row['id']])
cnx_dst.commit()
SQL="update res_users set password=(select password from res_users where id=1) where id=2"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_company_users_rel *****************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
cr_dst.execute("insert into res_company_users_rel values(1,2)")
cnx_dst.commit()
# #****************************************************************************


#** res_groups ****************************************************************
MigrationResGroups(db_src,db_dst)
cr_dst.execute("delete from res_groups_users_rel where gid in (9,10);") # L'utilisateur ne peut pas avoir plus d'un type d'utilisateur.
cnx_dst.commit()
# #****************************************************************************


#** res_groups_users_rel ******************************************************
SQL="select id,name->>'en_US' as name from ir_module_category where name->>'en_US'='User types'" # where name->>'en_US'='User types'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
category_id=False
for row in rows:
    category_id=row["id"]
if category_id:
    SQL="select id,name->>'fr_FR' as name from res_groups where category_id=%s and id>1"
    cr_dst.execute(SQL,[category_id])
    rows = cr_dst.fetchall()
    for row in rows:
        SQL="delete from res_groups_users_rel where gid=%s"
        cr_dst.execute(SQL,[row["id"]]) # L'utilisateur ne peut pas avoir plus d'un type d'utilisateur.
    cnx_dst.commit()
#******************************************************************************

#** res_groups_users_rel ******************************************************
SQL="""
    delete from res_groups_users_rel where uid not in (select id from res_users);
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************

# ** Property res_parter et res_users *****************************************
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_payment_term'         , field_dst='property_payment_term_id') 
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_supplier_payment_term', field_dst='property_supplier_payment_term_id') 
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_receivable', field_dst='property_account_receivable_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_payable'   , field_dst='property_account_payable_id')
MigrationIrProperty(db_src,db_dst,'res.partner', 'property_stock_customer')
MigrationIrProperty(db_src,db_dst,'res.partner', 'property_stock_supplier')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_product_pricelist')
MigrationIrProperty2Field(db_src,db_dst,'res.partner', property_src='property_product_pricelist_purchase', field_dst="pricelist_purchase_id")
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_position', field_dst='property_account_position_id')
debut = Log(debut, "res_users")
#******************************************************************************


#** product *******************************************************************
default={
    "detailed_type": "consu",
    "tracking"     : "none",
    "purchase_line_warn"     : "no-message",
    "sale_line_warn"     : "no-message",
    "invoice_policy": "delivery",
}
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True, default=default)
MigrationTable(db_src,db_dst,'product_product')
#******************************************************************************


#** uom  **********************************************************************
MigrationTable(db_src,db_dst, table_src="product_uom_categ", table_dst="uom_category", text2jsonb=True)
MigrationTable(db_src,db_dst, table_src="product_uom"      , table_dst="uom_uom"     , text2jsonb=True)
#******************************************************************************


# ** product_packaging et product_ul ******************************************
MigrationTable(db_src,db_dst, table_src="product_ul", table_dst="is_product_ul") # Cette table n'existe plus dans Odoo 16
SQL="delete from product_packaging where qty<>qty::integer"
cr_src.execute(SQL)
cnx_src.commit()
MigrationTable(db_src,db_dst,"product_packaging")
SQL="""
    SELECT pack.id,pp.id product_id
    FROM product_packaging pack join product_product pp on pack.product_tmpl_id=pp.product_tmpl_id 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE product_packaging SET product_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['product_id'],row['id']])
cnx_dst.commit()
# *****************************************************************************


#** product_taxes *************************************************************
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************


#** product_supplierinfo ******************************************************
default={
    'currency_id': 1,
    'price'      : 0,
}
rename={
    'name': ' partner_id',
}
MigrationTable(db_src,db_dst,'product_supplierinfo',rename=rename, default=default)
#******************************************************************************


# ** Property product *********************************************************
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_income' , field_dst='property_account_income_id')
MigrationIrProperty(db_src,db_dst,'product.template', field_src='property_account_expense', field_dst='property_account_expense_id')
MigrationIrProperty(db_src,db_dst,'product.template', 'property_stock_production')
MigrationIrProperty(db_src,db_dst,'product.template', 'property_stock_inventory')
MigrationIrProperty(db_src,db_dst,'product.category', field_src='property_account_income_categ' , field_dst='property_account_income_categ_id')
MigrationIrProperty(db_src,db_dst,'product.category', field_src='property_account_expense_categ', field_dst='property_account_expense_categ_id')
#******************************************************************************


#** product_pricelist ****************************************************************
default={
    'discount_policy': 'with_discount',
    'company_id'     : 1,
}
MigrationTable(db_src,db_dst,'product_pricelist',default=default,text2jsonb=True)
MigrationTable(db_src,db_dst,'product_pricelist_version')
default={
    'compute_price': 'fixed',
    'applied_on'   : '0_product_variant',
    'company_id'   : 1,
    'active'       : True,
}
MigrationTable(db_src,db_dst,'product_pricelist_item',default=default)
debut = Log(debut, "product")
#******************************************************************************


#** res_currency ***************************************************************
default = {
    'symbol'        : '???',
    'decimal_places': 2,
}
MigrationTable(db_src,db_dst,'res_currency',default=default)
#******************************************************************************


#** account_journal ***********************************************************
table="account_journal"
rename={
    'currency'   : 'currency_id',
    'sequence_id': 'sequence',
}
default={
    'active'                 : True,
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
#******************************************************************************


#** account_payment_term ******************************************************
table="account_payment_term"
default = {'sequence': 10}
MigrationTable(db_src,db_dst,table,default=default,text2jsonb=True)
table="account_payment_term_line"
default = {'months': 0}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** account_incoterms  ********************************************************
MigrationTable(db_src,db_dst, table_src="stock_incoterms", table_dst="account_incoterms", text2jsonb=True)
#******************************************************************************


#** Position fiscale **********************************************************
default={
    'company_id': 1,
}
MigrationTable(db_src,db_dst,'account_fiscal_position',default=default,text2jsonb=True)
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
#"user_type": "user_type_id",
    "type"     : "account_type",
}
MigrationTable(db_src,db_dst,table,rename=rename)
#******************************************************************************


#** account_type **************************************************************
cr_dst.execute("update account_account set account_type='equity'           , internal_group='equity'") 
cr_dst.execute("update account_account set account_type='asset_fixed'      , internal_group='asset'     where code like '2%'") 
cr_dst.execute("update account_account set account_type='asset_current'    , internal_group='asset'     where code like '44%'") 
cr_dst.execute("update account_account set account_type='liability_payable', internal_group='liability' where code like '401%'") 
cr_dst.execute("update account_account set account_type='asset_receivable' , internal_group='asset'     where code like '411%'") 
cr_dst.execute("update account_account set account_type='expense'          , internal_group='expense'   where code like '6%'") 
cr_dst.execute("update account_account set account_type='income'           , internal_group='income'    where code like '7%'") 
cnx_dst.commit()
#******************************************************************************


#** account_root **************************************************************
SQL="SELECT id,code FROM account_account"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    id=row["id"]
    code=row["code"]
    root_id = (ord(code[0]) * 1000 + ord(code[1:2] or '\x00'))
    SQL="UPDATE account_account SET root_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[root_id,id])
cnx_dst.commit()
#******************************************************************************


#** account_tax **************************************************************
SQL="""
    delete from account_move_line;
    delete from account_tax_repartition_line;
    delete from account_account_tag_account_tax_repartition_line_rel;
    update res_company set account_purchase_tax_id=1;
    update res_company set account_sale_tax_id=2;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
table='account_tax'
rename={
    'type':'amount_type'
}
default={
    "tax_group_id": 1,
    "country_id"  : 75,
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
cr_dst.execute("update account_tax set amount=100*amount")
cnx_dst.commit()
#******************************************************************************


#** Traductions account_tax *******************************************************
SQL="SELECT id,name FROM account_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    res_id = row["id"]
    value=GetTraduction(cr_src,'account.tax','name', res_id)
    if value:
        SQL="update account_tax set name=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
#SQL="delete from ir_translation where name like 'account.tax,%'"
#cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** Ajouter les comptes sur les taxes *****************************************    
cr_dst.execute("delete from account_tax_repartition_line")
SQL="SELECT id, account_collected_id,account_paid_id FROM account_tax"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    id = row["id"]
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[0,'base',id,1,1,False])
    SQL="""
        INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, refund_tax_id, company_id, sequence, use_in_tax_closing)
        VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[0,'base',id,1,1,False])
    SQL="""
    INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing, account_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True,row["account_collected_id"]])
    SQL="""
    INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, refund_tax_id, company_id, sequence, use_in_tax_closing, account_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True,row["account_paid_id"]])
cnx_dst.commit()
debut = Log(debut, "account")
#******************************************************************************


#** mrp_workcenter ************************************************************
default = {
    'sequence': 10,
    'company_id': 1,
    'resource_calendar_id': 1,
    'working_state': 'normal',
    'resource_type': 'material',
    'active': True,
    'default_capacity': 1,
    'time_efficiency': 100,
}
MigrationTable(db_src,db_dst,"mrp_workcenter",default=default)
SQL="""
    select rr.name, rr.code, rr.resource_type,  mw.id
    from resource_resource rr join mrp_workcenter mw on rr.id=mw.resource_id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE mrp_workcenter SET name=%s, code=%s, resource_type=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["name"],row["code"],row["resource_type"],row["id"]])
cnx_dst.commit()
#******************************************************************************


#** mrp_bom ***************************************************************
rename={'product_uom':'product_uom_id'}
default={
    'ready_to_produce': 'all_available',
    'consumption'     : 'warning',
}
MigrationTable(db_src,db_dst,'mrp_bom', rename=rename, default=default)
rename={'product_uom':'product_uom_id'}
MigrationTable(db_src,db_dst,'mrp_bom_line', rename=rename)
#******************************************************************************


#** mrp_routing ***************************************************************
tables=[
"mrp_routing",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
default={
    'active'   : True,
    'time_mode': 'manual',
}
MigrationTable(db_src,db_dst,'mrp_routing_workcenter', default=default)
SQL="""
    UPDATE mrp_routing_workcenter SET time_cycle_manual=is_nb_secondes/60;
    UPDATE mrp_routing_workcenter set active=True;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "mrp")
#******************************************************************************


#** purchase_order ************************************************************
rename={
    'validator': 'user_id',
}
MigrationTable(db_src,db_dst,'purchase_order', rename=rename)
SQL="""
    UPDATE purchase_order set state='purchase' where state='except_picking';
    UPDATE purchase_order set state='purchase' where state='approved';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="""
    DELETE FROM purchase_order_line where product_id is null;
"""
cr_src.execute(SQL) # TODO : A revoir
cnx_src.commit()
default={
}
MigrationTable(db_src,db_dst,'purchase_order_line', default=default)
rename={
    'ord_id': 'purchase_order_line_id',
    'tax_id': 'account_tax_id',
}
MigrationTable(db_src,db_dst,'purchase_order_taxe',table_dst='account_tax_purchase_order_line_rel',rename=rename)
debut = Log(debut, "purchase_order")
#******************************************************************************


# ** stock_location / stock_warehouse  ****************************************
MigrationTable(db_src,db_dst,'stock_location')
default={'manufacture_steps': 'mrp_one_step'}
MigrationTable(db_src,db_dst,'stock_warehouse', default=default)
SQL="""
    update stock_location set parent_path=name;
    update stock_location set company_id=1;
    update product_category set parent_path='/' where parent_path is null;
    update product_category set complete_name=name;
    update stock_warehouse set active='t';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
# *****************************************************************************


#** stock_picking_type ********************************************************
default={
    "company_id"        : 1,
    "sequence_code"     : "x",
    "reservation_method": "at_confirm",
    "create_backorder"  : "ask",
}
MigrationTable(db_src,db_dst,'stock_picking_type', default=default, text2jsonb=True)
SQL="""
    INSERT INTO stock_picking_type (
        default_location_src_id, 
        default_location_dest_id, 
        warehouse_id, 
        company_id, 
        sequence_id,
        sequence_code,
        code,
        reservation_method,
        create_backorder,
        name,
        active
    )
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""
default_location_src_id  = 12 # WH / 01 pour les 3 sites
default_location_dest_id = 12 # WH / 01 pour les 3 sites
warehouse_id = 1
company_id = 1
sequence_id = 17
sequence_code = 'MO'
code = "mrp_operation"
reservation_method = "at_confirm"
create_backorder = "ask"
name = '{"en_US": "Fabrication"}'
active = True
vals=[
    default_location_src_id, 
    default_location_dest_id, 
    warehouse_id, 
    company_id, 
    sequence_id,
    sequence_code,
    code,
    reservation_method,
    create_backorder,
    name,
    active
]
cr_dst.execute(SQL,vals)
cnx_dst.commit()
#******************************************************************************


#** ir_sequence ***************************************************************
#MigrationTable(db_src,db_dst,'ir_sequence') # TODO  la relation « ir_sequence_071 » n'existe pas
#******************************************************************************

#** ir_sequence ***************************************************************
SQL="SELECT id,code,implementation,prefix,padding,number_next FROM ir_sequence WHERE code is not null"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    code=row["code"]
    SQL="UPDATE ir_sequence SET prefix=%s,padding=%s,number_next=%s WHERE code=%s"
    cr_dst.execute(SQL,[row["prefix"],row["padding"],row["number_next"],code])
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

#** ir_sequence************************************************************
#TODO pour les réceptions et livraisons des 3 sites, les id des sequences sont les même
MigrationIrSequence(db_src,db_dst,id_src=30,id_dst=11) # Séquence d'entrée (Réception)
MigrationIrSequence(db_src,db_dst,id_src=31,id_dst=12) # Séquence de sortie (livraison)
#MigrationIrSequence(db_src,db_dst,id_src=43,id_dst=26) # Séquence pour les ordres de fabrication
#**************************************************************************

#** Affecter les bonnes séquences dans stock_picking_type *****************
cr_dst.execute("update stock_picking_type set sequence_id=11 where code='incoming'")
cr_dst.execute("update stock_picking_type set sequence_id=12 where code='outgoing'")
#cr_dst.execute("update stock_picking_type set sequence_id=26 where code='mrp_operation'")
cnx_dst.commit()
#**************************************************************************

debut = Log(debut, "ir_sequence")


#** stock_picking *************************************************************
default={
    "location_id"     : 7,  #TODO A Revoir => Mettre les données de stock_picking_type
    "location_dest_id": 7,  #TODO A Revoir
}
MigrationTable(db_src,db_dst,'stock_picking', default=default)
# #******************************************************************************


#** scheduled_date et date_deadline de stock_picking **********************
SQL="SELECT id,max_date FROM stock_picking"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE stock_picking SET scheduled_date=%s,date_deadline=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["max_date"],row["max_date"],row["id"]])
cnx_dst.commit()
debut = Log(debut, "stock_picking")
#******************************************************************************


#** stock_quant ****************************************************************
default={
    "reserved_quantity": 0,
}
rename={
'qty':'quantity'
}
MigrationTable(db_src,db_dst,'stock_quant', default=default, rename=rename)
debut = Log(debut, "stock_quant")
#******************************************************************************


#** stock_lot  ****************************************************************
default={
    "company_id": 1,
    "name"      : "??",
}
MigrationTable(db_src,db_dst, table_src="stock_production_lot", table_dst="stock_lot", default=default)
debut = Log(debut, "stock_lot")
#******************************************************************************


#** stock_location ***********************************************************
default={
    "warehouse_id": 1,
}
MigrationTable(db_src,db_dst,'stock_location', default=default, text2jsonb=True)
parent_store_compute(cr_dst,cnx_dst,'stock_location','location_id')
#******************************************************************************

#** Recherche emplacement de stock virtuel WH *********************************
location_stock_id = False
SQL="select id from stock_location where active='t' and usage='view' and name='WH'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    location_stock_id = row["id"]
#******************************************************************************


#** Recherche emplacement de stock virtuel Customers **************************
location_customer_id = False
SQL="select id from stock_location where active='t' and usage='customer'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    location_customer_id = row["id"]
#******************************************************************************


#** stock_route : stock_rule **************************************************
#MigrationTable(db_src,db_dst,'stock_rule') #TODO : Ne pas migrer cette table => Laisser la table par défaut
MigrationTable(db_src,db_dst,'stock_location_route',table_dst='stock_route',text2jsonb=True)
MigrationTable(db_src,db_dst,'stock_route_product')
#******************************************************************************


#** Initialisation location_src_id et location_dest_id dans stock_rule ********
SQL="delete from stock_rule where route_id not in (select id from stock_route)"
cr_dst.execute(SQL)
SQL="update stock_rule set location_src_id=Null, location_dest_id=1, picking_type_id=1"
cr_dst.execute(SQL)
SQL="""
    select 
        rule.id, 
        rule.action, 
        rule.procure_method, 
        rule.name->>'en_US' rule,
        route.name->>'en_US' route
    from stock_rule rule join stock_route route on rule.route_id=route.id
    where rule.active='t' and route.active='t'
"""
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    if row["action"]=="pull":
        SQL="""
            update stock_rule 
            set picking_type_id=(select id from stock_picking_type where code='outgoing' limit 1), location_src_id=%s, location_dest_id=%s
            where id=%s
        """%(location_stock_id, location_customer_id,row["id"])
    if row["action"]=="manufacture":
        SQL="""
            update stock_rule 
            set picking_type_id=(select id from stock_picking_type where code='mrp_operation' limit 1), location_src_id=Null, location_dest_id=%s
            where id=%s
        """%(location_stock_id,row["id"])
    if row["action"]=="buy":
        SQL="""
            update stock_rule 
            set picking_type_id=(select id from stock_picking_type where code='incoming' limit 1), location_src_id=Null, location_dest_id=%s
            where id=%s
        """%(location_stock_id,row["id"])
    cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "stock_route / stock_rule")
#******************************************************************************


#** mrp_production ************************************************************
default = {
    "picking_type_id"   : 1,
    "consumption"       : 'flexible',
    #"date_planned_start": "1990-01-01",
}
rename={
    'product_uom' : 'product_uom_id',
    'date_planned': 'date_planned_start',
}
MigrationTable(db_src,db_dst,"mrp_production",default=default,rename=rename)
SQL="""
    update mrp_production set state='draft' where state='in_production';
    update mrp_production set priority=Null;
    update mrp_production set picking_type_id=(select id from stock_picking_type where code='mrp_operation' limit 1);
    update mrp_production set production_location_id=(select id from stock_location where usage='production' limit 1);
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "mrp_production")
#******************************************************************************


#** mrp_workorder *************************************************************
default={
    "product_uom_id": 1,
}
rename={
    'hour'        : 'duration_expected',
    'date_planned': 'date_planned_start',
}
MigrationTable(db_src,db_dst,'mrp_production_workcenter_line',table_dst='mrp_workorder', default=default, rename=rename)
SQL="""
    update mrp_workorder set state='ready'    where state='draft';
    update mrp_workorder set state='progress' where state='startworking';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "mrp_workorder")
#******************************************************************************


#** stock_move ****************************************************************
debut = Log(debut, "début stock_move (prévoir 5mn pour odoo1 et 3mn pour odoo3)")
MigrationTable(db_src,db_dst,'stock_move')
SQL="""
    update stock_move set state='draft' where raw_material_production_id is not null and state in ('confirmed','assigned');
    update stock_move set state='draft' where production_id is not null and state='confirmed';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "stock_move")
#******************************************************************************


#** stock_move_line (45 mn de traitement pour odoo1) **************************
debut = Log(debut, "début stock_move_line (prévoir 45mn pour odoo1)")
cnx_src = psycopg2.connect("dbname='"+db_src+"'")
cr_src = cnx_src.cursor('BigCursor', cursor_factory=RealDictCursor)
cr_src.itersize = 10000 # Rows fetched at one time from the server
SQL="""
    delete from stock_move_line;
    alter sequence stock_move_line_id_seq RESTART;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="""
    SELECT 
        spl.name            as lot_name,
        sm.create_date      as sm_create_date,
        sm.location_id      as sm_location_id,
        sm.location_dest_id as sm_location_dest_id,
        * 
    from stock_move sm join stock_quant_move_rel rel on sm.id=rel.move_id  
                    join stock_quant           sq on sq.id=rel.quant_id
                    left join stock_production_lot spl on sq.lot_id=spl.id
    order by sm.create_date
"""
cr_src.execute(SQL)
ct=1
for row in cr_src:
    SQL="""
        INSERT INTO stock_move_line (
            company_id, 
            create_date, 
            create_uid, 
            date, 
            description_picking, 
            location_dest_id, 
            location_id, 
            lot_id, 
            lot_name, 
            move_id, 
            owner_id, 
            package_id, 
            package_level_id, 
            picking_id, 
            product_category_name, 
            product_id, 
            product_uom_id, 
            production_id, 
            qty_done, 
            reference, 
            reserved_qty, 
            reserved_uom_qty, 
            result_package_id, 
            state, 
            workorder_id, 
            write_date, 
            write_uid
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    company_id = 1
    create_date = row["sm_create_date"]
    create_uid = row["create_uid"]
    date = row["date"]
    description_picking =  None
    location_dest_id = row["sm_location_dest_id"]
    location_id = row["sm_location_id"]
    lot_id = row["lot_id"]
    lot_name =  row["lot_name"]
    move_id = row["move_id"]
    owner_id = row["owner_id"]
    package_id =  row["package_id"]
    package_level_id =  None
    picking_id = row["picking_id"]
    product_category_name =  None
    product_id= row["product_id"]
    product_uom_id =  row["product_uom"]
    production_id = row["production_id"]
    qty_done = row["product_uom_qty"]
    reference = row["ref"]
    reserved_qty = 0
    reserved_uom_qty = 0
    result_package_id = None
    state = row["state"]
    workorder_id =  None
    write_date = row["write_date"]
    write_uid = row["write_uid"]
    vals=[
        company_id, 
        create_date, 
        create_uid, 
        date, 
        description_picking, 
        location_dest_id, 
        location_id, 
        lot_id, 
        lot_name, 
        move_id, 
        owner_id, 
        package_id, 
        package_level_id, 
        picking_id, 
        product_category_name, 
        product_id, 
        product_uom_id, 
        production_id, 
        qty_done, 
        reference, 
        reserved_qty, 
        reserved_uom_qty, 
        result_package_id, 
        state, 
        workorder_id, 
        write_date, 
        write_uid
    ]
    cr_dst.execute(SQL,vals)
    ct+=1
cnx_dst.commit()
debut = Log(debut, "fin stock_move_line")
#******************************************************************************



#** stock_rule TODO : A Revoir avec stock_picking *****************************
#TODO : Ne pas migrer cette table => Laisser la table par défaut
#SQL="""
#    update stock_rule set picking_type_id=3 where picking_type_id not in (select id from stock_picking_type);
#"""
#cr_dst.execute(SQL)
#cnx_dst.commit()
#******************************************************************************


#** sale_order ****************************************************************
MigrationTable(db_src,db_dst,'resource_calendar_leaves')
rename={
    'fiscal_position':'fiscal_position_id'
}
default={
    'currency_id': 1,
}
MigrationTable(db_src,db_dst,'sale_order', default=default,rename=rename)
default={
    "customer_lead": 7,
}
MigrationTable(db_src,db_dst,'sale_order_line', default=default)
#******************************************************************************


#** compute sale_order_line / price_subtotal ***********************************
SQL="UPDATE sale_order_line SET price_subtotal=product_uom_qty*price_unit"
cr_dst.execute(SQL)
cnx_dst.commit()
#*******************************************************************************


# ** Migration sale_order_tax => account_tax_sale_order_line_rel **************
rename={
    'order_line_id': 'sale_order_line_id',
    'tax_id'       : 'account_tax_id',
}
MigrationTable(db_src,db_dst,'sale_order_tax',table_dst='account_tax_sale_order_line_rel',rename=rename)
# *****************************************************************************


#** procurement_group *********************************************************
rename={}
default={}
MigrationTable(db_src,db_dst,'procurement_group', rename=rename, default=default)
#******************************************************************************

debut = Log(debut, "sale_order")


#** account_move_line *********************************************************
debut = Log(debut, "Début account_move_line")
MigrationTable(db_src,db_dst,'is_export_cegid')
MigrationTable(db_src,db_dst,'is_export_cegid_ligne')
MigrationTable(db_src,db_dst,'is_account_folio')
MigrationTable(db_src,db_dst,'account_move_reconcile', table_dst='account_full_reconcile')
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
    'currency_id': 1,
    'debit': 0,
    'credit': 0,
    'amount_currency': 0,
    'display_type': 'product',
}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
debut = Log(debut, "Fin account_move_line")
#******************************************************************************


#** account_invoice_line => account_move **************************************
debut = Log(debut, "Début account_invoice_line => account_move")
cnx_src,cr_src=GetCR(db_src)
SQL="""
    SELECT 
        ai.id,
        ai.move_id,
        ai.number,
        ai.date_invoice,
        ai.type,
        rp.name,
        ai.date_due,
        -- ai.order_id,
        -- ai.is_affaire_id,
        -- ai.is_refacturable,
        -- ai.is_nom_fournisseur,
        -- ai.is_personne_concernee_id,
        ai.amount_untaxed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual,
        ai.user_id,
        ai.fiscal_position,
        ai.name move_name,
        ai.origin,
        ai.supplier_invoice_number,
        ai.payment_term,

        ai.is_bon_a_payer,
        ai.is_date_envoi_mail,
        ai.is_document,
        ai.is_export_cegid_id,
        ai.is_folio_id,
        ai.is_masse_nette,
        ai.is_mode_envoi_facture,
        ai.is_num_bl_manuel,
        ai.is_num_cde_client,
        ai.is_origine_id,
        ai.is_type_facture
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
                amount_untaxed=%s,
                amount_tax=%s,
                amount_total=%s,
                amount_residual=%s,
                amount_untaxed_signed=%s,
                amount_tax_signed=%s,
                amount_total_signed=%s,
                amount_residual_signed=%s,
                invoice_user_id=%s,
                fiscal_position_id=%s,
                invoice_origin=%s,
                invoice_payment_term_id=%s,

                is_bon_a_payer=%s,
                is_date_envoi_mail=%s,
                is_document=%s,
                is_export_cegid_id=%s,
                is_folio_id=%s,
                is_masse_nette=%s,
                is_mode_envoi_facture=%s,
                is_num_bl_manuel=%s,
                is_num_cde_client=%s,
                is_origine_id=%s,
                is_type_facture=%s
            where id=%s
        """
        cr_dst.execute(SQL,(
            row['date_invoice'],
            row['type'],
            row['name'],
            row['date_due'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['user_id'],
            row['fiscal_position'],
            row['origin'],
            row['payment_term'],

            row['is_bon_a_payer'],
            row['is_date_envoi_mail'],
            row['is_document'],
            row['is_export_cegid_id'],
            row['is_folio_id'],
            row['is_masse_nette'],
            row['is_mode_envoi_facture'],
            row['is_num_bl_manuel'],
            row['is_num_cde_client'],
            row['is_origine_id'],
            row['is_type_facture'],

            move_id
        ))
        SQL="""
            SELECT 
                ail.id,
                ail.product_id,
                ail.name,
                ail.price_unit,
                ail.price_subtotal,
                ail.sequence,

                ail.is_amortissement_moule,
                ail.is_amt_interne,
                ail.is_cagnotage,
                ail.is_document,
                ail.is_montant_amt_interne,
                ail.is_montant_amt_moule,
                ail.is_montant_cagnotage,
                ail.is_montant_matiere,
                ail.is_move_id,
                ail.is_section_analytique_id
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
                    amount_currency=(debit-credit),
                    sequence=%s,

                    is_amortissement_moule=%s,
                    is_amt_interne=%s,
                    is_cagnotage=%s,
                    is_document=%s,
                    is_montant_amt_interne=%s,
                    is_montant_amt_moule=%s,
                    is_montant_cagnotage=%s,
                    is_montant_matiere=%s,
                    is_move_id=%s,
                    is_section_analytique_id=%s
                WHERE id IN (
                    SELECT id
                    FROM account_move_line
                    WHERE move_id=%s and product_id is not null
                    ORDER BY id
                    LIMIT 1 OFFSET %s
                ) 
            """
            cr_dst.execute(SQL,(
                row2['name'],
                row2['id'],
                row2['price_unit'],
                row2['price_subtotal'],
                row2['price_subtotal'],
                row2['sequence'],

                row2['is_amortissement_moule'],
                row2['is_amt_interne'],
                row2['is_cagnotage'],
                row2['is_document'],
                row2['is_montant_amt_interne'],
                row2['is_montant_amt_moule'],
                row2['is_montant_cagnotage'],
                row2['is_montant_matiere'],
                row2['is_move_id'],
                row2['is_section_analytique_id'],

                move_id,
                ct2
            ))
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
debut = Log(debut, "Fin account_invoice_line => account_move")
#******************************************************************************

#** Migration invoice_id dans is_export_cegid_ligne **************************
ids=InvoiceIds2MoveIds(cr_src)
SQL="SELECT id, invoice_id FROM is_export_cegid_ligne"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    invoice_id = ids[row['invoice_id']]
    SQL="UPDATE is_export_cegid_ligne SET invoice_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[invoice_id,row['id']])
cnx_dst.commit()
debut = Log(debut, "invoice_id dans is_export_cegid_ligne")
#******************************************************************************

# ** Migration tax_code_id ****************************************************
cr_dst.execute("update account_move_line set amount_currency=(debit-credit)")
cr_dst.execute("update account_move_line set company_currency_id=currency_id")
cnx_dst.commit()
SQL="""
    select aml.id move_line_id,aml.name,aml.tax_code_id,aml.debit,aml.credit,at.id tax_line_id
    from account_move_line aml inner join account_tax at on aml.tax_code_id=at.tax_code_id 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        UPDATE account_move_line
        SET 
            tax_line_id=%s,
            tax_group_id=1,
            currency_id=1,
            company_currency_id=1,
            quantity=1
        WHERE id=%s
    """
    cr_dst.execute(SQL,[row["tax_line_id"],row["move_line_id"]])
cnx_dst.commit()
debut = Log(debut, "tax_code_id")
#******************************************************************************



#** Migration des taxes sur les factures **************************************
SQL="DELETE FROM account_move_line_account_tax_rel"
cr_dst.execute(SQL)
cnx_dst.commit()
SQL="SELECT invoice_line_id, tax_id  FROM account_invoice_line_tax order by invoice_line_id"
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
debut = Log(debut, "account_move_line_account_tax_rel")
#******************************************************************************


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""
    update account_move_line set display_type='payment_term' 
    where account_id in (select id from account_account where account_type in ('asset_receivable', 'liability_payable'));
    update account_move_line set display_type='tax' where tax_line_id is not null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** hr_department ***************************************************************
default={
    "active": True,
}
MigrationTable(db_src,db_dst,'hr_department', default=default)
cr_dst.execute("update hr_department set complete_name=name") #TODO : Pour actualier tous les noms, il suffira de modiifer la racine DIRECTION GENERALE
cnx_dst.commit()
parent_store_compute(cr_dst,cnx_dst,'hr_department','parent_id')
#******************************************************************************


#** hr_job ********************************************************************
default={
    "active": True,
}
MigrationTable(db_src,db_dst,'hr_job', default=default, text2jsonb=True)
#******************************************************************************


#** resource_resource *********************************************************
default={
    "calendar_id": 1,
    "tz"         : "Europe/Paris",
}
MigrationTable(db_src,db_dst,'resource_resource', default=default)
#******************************************************************************


#** hr_employee - user_id *****************************************************
SQL="""
    select rr.user_id, max(he.id) as employe_id
    from resource_resource rr join hr_employee he on rr.id=he.resource_id
    group by rr.user_id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE hr_employee SET user_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["user_id"],row["employe_id"]])
cnx_dst.commit()
#******************************************************************************

debut = Log(debut, "hr_employee")


tables=[
    "is_atelier",
    "is_badge",
    "is_bl_manuel_line",
    "is_bl_manuel",
    "is_bon_achat_ville_line",
    "is_bon_achat_ville",
    "is_bon_transfert_line",
    "is_bon_transfert",
    "is_bon_transfert",
    "is_budget_nature",
    "is_budget_responsable",
    "is_capteur",
    "is_category",
    "is_cde_ferme_cadencee_histo",
    "is_cde_ferme_cadencee_order",
    "is_cde_ferme_cadencee",
    "is_cde_ouverte_fournisseur_histo",
    "is_cde_ouverte_fournisseur_line",
    "is_cde_ouverte_fournisseur_message",
    "is_cde_ouverte_fournisseur_product",
    "is_cde_ouverte_fournisseur_tarif",
    "is_cde_ouverte_fournisseur",
    "is_certificat_conformite_autre",
    "is_certificat_conformite_autre2",
    "is_certificat_conformite_fabricant",
    "is_certificat_conformite_reference",
    "is_certificat_conformite",
    "is_certifications_qualite",
    "is_code_cas",
    "is_commande_externe",
    "is_config_champ_line",
    "is_config_champ",
    "is_consigne_journaliere_ass",
    "is_consigne_journaliere_inj",
    "is_consigne_journaliere",
    "is_cout_calcul_actualise",
    "is_cout_calcul_log",
    "is_cout_calcul_niveau",
    "is_cout_calcul",
    "is_cout_gamme_ma_pk",
    "is_cout_gamme_ma",
    "is_cout_gamme_mo_pk",
    "is_cout_gamme_mo",
    "is_cout_nomenclature",
    "is_cout",
    "is_ctrl_budget_ana_annee",
    "is_ctrl_budget_ana_product",
    "is_ctrl_budget_tdb_famille_rel",
    "is_ctrl_budget_tdb_famille",
    "is_ctrl_budget_tdb_intitule",
    "is_ctrl_budget_tdb_saisie",
    "is_ctrl_budget_tdb",
    "is_ctrl100_defaut_line",
    "is_ctrl100_defaut",
    "is_ctrl100_defautheque",
    "is_ctrl100_gamme_defautheque_line",
    "is_ctrl100_gamme_mur_qualite_formation",
    "is_ctrl100_gamme_mur_qualite",
    #"is_ctrl100_gamme_standard", #Le champ active a été renommé en is_active
    "is_ctrl100_operation_specifique",
    # #"is_ctrl100_operation_standard", #TODO  : A revoi car plantage à cause du 'order'

#psycopg2.errors.SyntaxError: ERREUR:  erreur de syntaxe sur ou près de « order »
#LINE 4:         COPY is_invest_cde (order,base,code_pg,create_date,c...

    "is_ctrl100_pareto",
    "is_ctrl100_rapport_controle",
    "is_ctrl100_typologie_produit",
    "is_deb_synthese",
    "is_deb",
    "is_demande_absence_type",
    "is_demande_absence",
    "is_demande_achat_fg_line",
    "is_demande_achat_fg",
    "is_demande_achat_invest_line",
    "is_demande_achat_invest",
    "is_demande_achat_moule_line",
    "is_demande_achat_moule",
    "is_demande_achat_serie_line",
    "is_demande_achat_serie",
    "is_demande_conges_autre",
    "is_demande_conges_export_cegid",
    "is_demande_conges",
    "is_demande_conges",
    "is_demande_transport",
    "is_donnee_machine_line",
    "is_donnee_machine",
    "is_dossier_appel_offre",
    "is_dossier_article_code_recyclage",
    "is_dossier_article_combustion",
    "is_dossier_article_durete",
    "is_dossier_article_gamme_commerciale",
    "is_dossier_article_producteur",
    "is_dossier_article_traitement",
    "is_dossier_article_type_article",
    "is_dossier_article_utilisation",
    "is_dossier_article",
    "is_dossierf",
    "is_droit_conges",
    "is_edi_cde_cli_line",
    "is_edi_cde_cli",
    "is_emb_emplacement",
    "is_emb_norme",
    "is_emplacement_outillage",
    "is_employe_absence",
    "is_employe_horaire",
    "is_equipement_champ_line",
    "is_equipement_type",
    "is_equipement",
    "is_equipement",
    "is_escompte",
    "is_etat_presse_regroupement",
    "is_etat_presse",
    "is_etuve_commentaire",
    "is_etuve_of",
    "is_etuve_rsp",
    "is_etuve_saisie",
    "is_etuve",
    "is_export_edi_histo",
    "is_export_edi",
    "is_facturation_fournisseur_justification",
    "is_facturation_fournisseur",
    "is_facture_proforma_line",
    "is_facture_proforma_outillage_line",
    "is_facture_proforma_outillage",
    "is_facture_proforma",
    "is_famille_achat",
    "is_famille_instrument",
    "is_fiche_tampographie_constituant",
    "is_fiche_tampographie_recette",
    "is_fiche_tampographie_reglage",
    "is_fiche_tampographie_type_reglage",
    "is_fiche_tampographie",
    "is_gabarit_controle",
    "is_galia_base_uc",
    "is_galia_base_um",
    "is_gestionnaire",
    "is_historique_controle",
    "is_ilot",
    "is_import_budget_pk",
    "is_indicateur_revue_jalon",
    "is_instruction_particuliere",
    "is_instrument_mesure",
    "is_inventaire_anomalie",
    "is_inventaire_ecart",
    "is_inventaire_feuille",
    "is_inventaire_inventory",
    "is_inventaire_line_tmp",
    "is_inventaire_line",
    "is_inventaire",

    #"is_invest_cde", #TODO  : A revoi car plantage à cause du 'order'

#psycopg2.errors.SyntaxError: ERREUR:  erreur de syntaxe sur ou près de « order »
#LINE 4:         COPY is_invest_cde (order,base,code_pg,create_date,c...

    "is_invest_compta",
    "is_invest_detail",
    "is_invest_global",
    "is_jour_ferie_country",
    "is_jour_ferie",
    "is_liste_servir_client",
    "is_liste_servir_line",
    "is_liste_servir_message",
    "is_liste_servir_uc",
    "is_liste_servir_um",
    "is_liste_servir",
    "is_mem_var",
    "is_mode_operatoire_menu",
    "is_mode_operatoire",
    "is_mold_bridage_rel",
    "is_mold_bridage",
    "is_mold_cycle",
    "is_mold_dateur",
    "is_mold_frequence_preventif",
    "is_mold_operation_specifique",
    "is_mold_operation_systematique",
    "is_mold_piece_specifique",
    "is_mold_project",
    "is_mold_specification_array",
    "is_mold_specification_particuliere",
    "is_mold_specifique_array",
    "is_mold_surface_aspect",
    "is_mold_systematique_array",
    "is_mold",
    "is_norme_certificats",
    "is_of_declaration",
    "is_of_rebut",
    "is_of_tps",
    "is_of",
    "is_operation_controle",
    "is_ot_affectation",
    "is_ot_indicateur",
    "is_ot_temps_passe",
    "is_ot",
    "is_outillage_constructeur",
    "is_pdc_mod",
    "is_pdc_mold",
    "is_pdc_workcenter",
    "is_pdc",
    "is_pic_3ans_saisie",
    "is_pic_3ans",
    "is_piece_montabilite",
    "is_plaquette_etalon",
    "is_pointage_commentaire",
    "is_pointage",
    "is_presse_arret",
    "is_presse_arret_of_rel",
    "is_presse_classe",
    "is_presse_cycle",
    "is_presse_cycle_of_rel",
    "is_presse_puissance",
    "is_preventif_equipement_heure",
    "is_preventif_equipement_saisie",
    "is_preventif_equipement_zone",
    "is_preventif_equipement",
    "is_preventif_moule",
    "is_product_client",
    "is_product_code_cas",
    "is_product_famille",
    "is_product_segment",
    "is_product_sous_famille",
    "is_proforma_chine_line",
    "is_proforma_chine",
    "is_raspberry_entree_sortie",
    "is_raspberry_zebra",
    "is_raspberry",
    "is_reach_product_cas",
    "is_reach_product_matiere",
    "is_reach_product",
    "is_reach",
    "is_rgpd_action",
    "is_rgpd_donnee_personnelle",
    "is_rgpd_lieu_stockage",
    "is_rgpd_service",
    "is_rgpd_traitement",
    "is_secteur_activite",
    "is_section_analytique",
    "is_segment_achat",
    "is_site",
    "is_tarif_cial",
    "is_theia_alerte_type",
    "is_theia_alerte",
    "is_theia_habilitation_operateur",
    "is_theia_lecture_ip",
    "is_theia_trs",
    "is_theia_validation_action_groupe_rel",
    "is_theia_validation_action",
    "is_theia_validation_groupe_employee_rel",
    "is_theia_validation_groupe",
    "is_type_contact",
    "is_type_controle_gabarit",
    "is_type_defaut",
    "is_type_etiquette",
    "is_vente_message",
    "mrp_prevision",
    #"is_deb_line",  TODO a revoir après la migration des factures car il y a un lien avec
    #"is_facturation_fournisseur_line", TODO A revoir après la migration des mouvements de stocks
    #"is_mode_operatoire_menu", TODO : A revoir car les liens avec les menus sont à revoir
    #"is_mode_operatoire",      TODO : A revoir car les liens avec les menus sont à revoir
    #"is_theia_habilitation_operateur_etat",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
    debut = Log(debut, table)

tables=[
    'hr_employee_is_demande_absence_rel',
    'hr_employee_is_demande_conges_rel',
    'is_article',
    'is_ctrl100_defaut_line_operateur',
    'is_ctrl100_defaut_operateur',
    'is_ctrl100_gamme_mur_qualite_formation_operateur_rel',
    'is_ctrl100_pareto_dossierf_rel',
    'is_ctrl100_pareto_typologie_rel',
    'is_ctrl100_risque_lie',
    'is_database_preventif_equipement_user_ids_rel',
    'is_deb_line',
    'is_facturation_fournisseur_line',
    'is_facturation_fournisseur_line_taxe_ids',
    'is_facture_pk',
    'is_facture_pk_line',
    'is_facture_pk_moule',
    'is_galia_base',
    'is_gestion_lot',
    'is_instruction_particuliere_dossierf_rel',
    'is_instruction_particuliere_groupe_rel',
    'is_instruction_particuliere_mold_rel',
    'is_instruction_particuliere_product_rel',
    'is_mold_dossierf_rel',
    'is_mold_presse_rel',
    'is_preventif_equipement_gamme_rel',
    'is_res_company_users_rel',
    'is_res_users',
    'is_sale_ar_contact_id_rel',
    'is_taux_rotation_stock_new',
    'is_theia_lecture_ip_of_rel',
    'is_ctrl100_operation_standard',
    'is_invest_cde',
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
    debut = Log(debut, table)
#******************************************************************************


#** is_ctrl100_gamme_standard *************************************************
rename={
    'active': 'is_active',
}
MigrationTable(db_src,db_dst,"is_ctrl100_gamme_standard",rename=rename)
#******************************************************************************


#** is_equipement_champ_line **************************************************
MigrationTable(db_src,db_dst,"is_equipement_champ_line")
SQL="""
    SELECT l.id,f.name
    FROM is_equipement_champ_line l join ir_model_fields f on l.name=f.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        SELECT id 
        from ir_model_fields 
        where name=%s and model='is.equipement' and ttype<>'boolean' limit 1
    """
    cr_dst.execute(SQL,[row["name"]])
    rows_dst = cr_dst.fetchall()
    for row_dst in rows_dst:
        SQL="update is_equipement_champ_line set name=%s where id=%s"
        cr_dst.execute(SQL,[row_dst["id"],row["id"]])
cnx_dst.commit()
debut = Log(debut, "is_equipement_champ_line")
#******************************************************************************


#** is_mem_var (uid admin est passé de 1 à 2) *********************************
SQL="update is_mem_var set user_id=2 where user_id=1"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** hr_employee ***************************************************************
default={
    "company_id": 1,
    "employee_type": "employee",
    "active": 1,
    "work_permit_scheduled_activity": False,
    "parent_id": None,
    'resource_calendar_id': 2,
}
MigrationTable(db_src,db_dst,'hr_employee', default=default)
SQL="""
    select rr.name, rr.active, he.id
    from resource_resource rr join hr_employee he on rr.id=he.resource_id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE hr_employee SET name=%s, active=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["name"],row["active"],row["id"]])
SQL="""
    select rr.user_id, he.id
    from resource_resource rr join hr_employee he on rr.id=he.resource_id
    where active=True
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE hr_employee SET  user_id=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["user_id"],row["id"]])
cnx_dst.commit()
debut = Log(debut, "hr_employee")
#******************************************************************************


# ** res_partner_bank et res_bank *****************************************
MigrationTable(db_src,db_dst,'res_bank')
default={
    'partner_id': 1,
    'active'    : True,
    }
rename={
    'bank': 'bank_id',
}
MigrationTable(db_src,db_dst,"res_partner_bank",default=default,rename=rename)
SQL="update res_bank rb set bic=(select is_bank_swift from res_partner_bank where bank_id=rb.id)"
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "res_partner_bank")
# *************************************************************************


#** init weight product_product (nouveau champ) ***************************
SQL="update product_product set weight=(select weight from product_template pt where pt.id=product_tmpl_id)"
cr_dst.execute(SQL)
cnx_dst.commit()
#**************************************************************************


#** product_template : detailed_type **************************************
SQL="UPDATE product_template SET detailed_type=type"
cr_dst.execute(SQL)
cnx_dst.commit()
#**************************************************************************


#** is_config_champ_line **************************************************
SQL="""
    SELECT 
        line.id,
        f.id field_id, 
        f.name fied_name,
        f.model
    from is_config_champ_line line join ir_model_fields f on line.name=f.id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    #print(row["id"], row["field_id"], row["fied_name"], row["model"])
    SQL="SELECT id from ir_model_fields where model='product.template' and name=%s"
    cr_dst.execute(SQL,[row["fied_name"]])
    rows_dst = cr_dst.fetchall()
    for row_dst in rows_dst:
        SQL="UPDATE is_config_champ_line SET name=%s WHERE id=%s"
        cr_dst.execute(SQL,[row_dst["id"],row["id"]])
cnx_dst.commit()
debut = Log(debut, "is_config_champ_line")
#**************************************************************************


#** res_partner_category **************************************************
MigrationTable(db_src,db_dst,'res_partner_category',text2jsonb=True)
tables=[
    "is_site_res_partner_rel",
    "partner_database_rel",
    "res_partner_res_partner_category_rel",
    "is_gabarit_dossierf_rel",
    "is_gabarit_mold_rel",
    "is_piece_montabilite_id",
    "equipement_dossierf_rel",
    "equipement_mold_rel",

]
for table in tables:
    MigrationTable(db_src,db_dst,table)
debut = Log(debut, "res_partner_category")
#**************************************************************************


#** purchase_order_stock_picking_rel **************************************
cr_dst.execute("delete from purchase_order_stock_picking_rel")
cnx_dst.commit()
SQL="""
    select distinct pol.order_id,sm.picking_id 
    from stock_move sm join purchase_order_line pol on sm.purchase_line_id=pol.id 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO purchase_order_stock_picking_rel (purchase_order_id,stock_picking_id)
        VALUES (%s,%s);
    """
    cr_dst.execute(SQL,[row["order_id"],row["picking_id"]])
cnx_dst.commit()
debut = Log(debut, "purchase_order_stock_picking_rel")
#******************************************************************************


#** Divers ********************************************************************
SQL="""
    update is_mode_operatoire_menu set menu_id=NULL;
    update stock_location set company_id=1;
    delete from mail_followers;
    update stock_picking set is_facture_pk_id=NULL;
    update is_ctrl100_gamme_standard set operation_standard_id=NULL;
    update is_edi_cde_cli_line set file_id=NULL;
    delete from stock_valuation_layer;
    delete from account_move_purchase_order_rel;
    update sale_order_line set currency_id=1 where currency_id is NULL;
    update account_move set message_main_attachment_id=NULL;
    update res_users set chatter_position='bottom';
    delete from mail_alias;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** stock_move : Suppression des mouvements annulés des composants des OF *****
debut = Log(debut, "Début suppression des mouvements annulés des composants des OF")
SQL="""
    delete from stock_move where raw_material_production_id is not null and state='cancel';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
debut = Log(debut, "Fin suppression des mouvements annulés des composants des OF")
#******************************************************************************


#** Qt Rcp et Qt Facturée sur les lignes des commandes fournisseur  ***********
debut = Log(debut, "Début Qt Rcp et Qt Facturée sur les réceptions")
SQL="""
    SELECT 
        pol.id,
        pol.product_id, 
        pol.product_uom, 
        pol.product_uom_qty, 
        pol.product_qty,
        pol.qty_received,
        pol.qty_received_manual, 
        pol.qty_invoiced, 
        pol.qty_to_invoice,
        (   SELECT sum(product_uom_qty)
            FROM stock_move
            where product_id=pol.product_id and purchase_line_id=pol.id and state='done'
            group by product_id
        ) qty_received,
        (   SELECT sum(product_uom_qty)
            FROM stock_move
            where product_id=pol.product_id and purchase_line_id=pol.id and state='done' and invoice_state='invoiced'
            group by product_id
        ) qty_invoiced
    FROM purchase_order_line pol
    order by pol.id
"""
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    #print(row["product_id"], row["product_qty"], row["product_uom_qty"], row["qty_received"], row["qty"])
    SQL="UPDATE purchase_order_line SET qty_received=%s, qty_invoiced=%s WHERE id=%s"
    cr_dst.execute(SQL,[row['qty_received'],row['qty_invoiced'],row['id']])
cnx_dst.commit()
debut = Log(debut, "Fin Qt Rcp et Qt Facturée sur les réceptions")
#********************************************************************


#** res_company ***************************************************************
#cr_dst.execute("update res_company set account_purchase_tax_id=Null")
#cnx_dst.commit()
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************


#** company_colors ************************************************************
company_colors={
    "0": '{"color_navbar_bg": "#0c94d4", "color_navbar_bg_hover": "#0c94d4", "color_navbar_text": "#000", "color_button_bg": "#eeeeec", "color_button_bg_hover": "#000000", "color_button_text": "#000000", "color_link_text": "#000000", "color_link_text_hover": "#000000"}',
    "1": '{"color_navbar_bg": "#0066cc", "color_navbar_bg_hover": "#0066cc", "color_navbar_text": "#000", "color_button_bg": "#f3f3f3", "color_button_bg_hover": "#000000", "color_button_text": "#000000", "color_link_text": "#000000", "color_link_text_hover": "#000000"}',
    "3": '{"color_navbar_bg": "#e70013", "color_navbar_bg_hover": "#e70013", "color_navbar_text": "#2e3436", "color_button_bg": "#ffffff", "color_button_bg_hover": "#2e3436", "color_button_text": "#2e3436", "color_link_text": "#2e3436", "color_link_text_hover": "#2e3436"}',
    "4": '{"color_navbar_bg": "#000000", "color_navbar_bg_hover": "#000000", "color_navbar_text": "#ffffff", "color_button_bg": "#ffffff", "color_button_bg_hover": "#000000", "color_button_text": "#fce94f", "color_link_text": "#0c94d4", "color_link_text_hover": "#0c94d4"}',
}
SQL="update res_company set company_colors=%s"
cr_dst.execute(SQL,[company_colors[soc]])
cnx_dst.commit()
#******************************************************************************


#** ir_attachment *************************************************************
tables=[
    "ir_attachment",
    "is_certificat_attachment_rel",
    "is_ctrl100_gamme_mur_qualite_attachment_rel",
    "is_demande_conges_attachment_rel",
    #"is_doc_attachment_rel",        TODO : N'existe pas !
    #"is_export_edi_attachment_rel", TODO : N'existe pas !
    "is_mode_operatoire_attachment_rel",
    "is_mold_attachment_rel",
    "is_preventif_equipement_saisie_attachment_rel",
    "is_preventif_moule_attachment_rel",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
    debut = Log(debut, table)
#******************************************************************************


#** Pièces jointes des factures ***********************************************
SQL="""
    SELECT 
        id,
        move_id
     from account_invoice
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="update ir_attachment set res_model='account.move', res_id=%s where res_id=%s and res_model='account.invoice'"
    cr_dst.execute(SQL,[row["move_id"], row["id"]])
cnx_dst.commit()
debut = Log(debut, "Pièces jointes des factures")
#******************************************************************************


#** Récupérer la ligne de ir_attachment pour faire fonctionner les PDF ********
table="ir_attachment"
where="name='res.company.scss'"
CopieTable(db_vierge,db_dst,table,where)
#******************************************************************************


# ** Convertir les images en pieces jointes ***********************************
print("Pour finaliser la migration, il faut démarrer Odoo avec cette commande : ")
print("/opt/odoo16/odoo-bin -c /etc/odoo/pg-odoo16.conf")
#name = input("Appuyer sur Entrée pour continuer") 
models,uid,password = XmlRpcConnection(db_dst)
fields=[
    ("image"                   ,"res.partner"),
    ("photo"                   ,"is.ctrl100.operation.specifique"),
    ("photo"                   ,"is.ctrl100.defautheque"),
    ("image_finale"            ,"is.fiche.tampographie"),
    ("image_encrier1"          ,"is.fiche.tampographie"),
    ("image_encrier2"          ,"is.fiche.tampographie"),
    ("image_encrier3"          ,"is.fiche.tampographie"),
    ("image_posage"            ,"is.fiche.tampographie"),
    ("contenu"                 ,"is.instruction.particuliere"),
    ("fichier"                 ,"is.inventaire.feuille"),
    ("is_logo"                 ,"res.company"),
    ("is_cachet_plastigray"    ,"res.company"),
    ("is_certificat"           ,"is.certifications.qualite"),
    ("is_signature"            ,"res.users"),
]
for line in fields:
    res_field=line[0]
    res_model=line[1]
    name = res_field
    if res_model=="res.partner":
        name=False
    ImageModel2IrAttachment(cr_src,models,db_dst,uid,password,res_model,res_field, name=name)
    debut = Log(debut, "ImageModel2IrAttachment : %s / %s (%s)"%(res_field, res_model, name))
#*******************************************************************************




debut = Log(debut, "** Fin migration %s ***********************************************"%(db_dst))
