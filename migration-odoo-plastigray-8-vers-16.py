#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
from datetime import datetime
import os

# TODO : 
# - Mettre 4 coeurs sur la VM + 8 Go + ajout index sur is_account_invoice_line_id  => Je suis passé de 3H à 5mn pour migrer les facutres (surtout account_move_line_account_tax_rel)
# - Installer base Postres 15
# - Recalculer les qt livrées et facturées sur les commandes achats et ventes
# - Relancer l'anlyse des contraintes
# - Refaire une migration complète depuis une base Odoo 8 récente
# - Faire un script python pour tester les contraintes, car la requete acutelle s'arrete sur chaque anomalie et il faut la relancer

# TODO : A revoir : 
# pg-odoo16-0=# alter table stock_rule validate constraint stock_rule_route_id_fkey;
# ERREUR:  une instruction insert ou update sur la table « stock_rule » viole la contrainte de clé
# étrangère « stock_rule_route_id_fkey »
# DÉTAIL : La clé (route_id)=(7) n'est pas présente dans la table « stock_route ».

# TODO : Permet de récupérer les tables d'origine d'une base vierge
#db_src = "pg-odoo16"
#db_dst = "pg-odoo16-1"
#MigrationTable(db_src,db_dst,'stock_route')
#MigrationTable(db_src,db_dst,'stock_rule')
# sys.exit()


# pg-odoo16-0=# select * from  ;
#  partner_id | site_id 
# ------------+---------
# (0 ligne)

# pg-odoo16-0=# select * from  ;



#socs=[0,1,3,4]
socs=[1]


for soc in socs:


    #** Paramètres ************************************************************
    db_src = "pg-odoo8-%s"%soc
    db_dst = "pg-odoo16-%s"%soc
    #**************************************************************************

    #cnx,cr=GetCR(db_src)
    #db_vierge = db_dst+'-vierge'
    #SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
    #cde="""echo '"""+SQL+"""' | psql postgres"""
    #lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue

    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    #cnx_vierge,cr_vierge=GetCR(db_vierge)






# pg-odoo16-1=# select id,name,scheduled_date, date_deadline, date, date_done from stock_picking where id=105818;
#    id   |   name   | scheduled_date | date_deadline |        date         | date_done 
# --------+----------+----------------+---------------+---------------------+-----------
#  105818 | R-185511 |                |               | 2023-05-12 14:03:08 | 
# (1 ligne)

# pg-odoo8-1=# select id,name,max_date,date from stock_picking where id=105818;
#    id   |   name   |      max_date       |        date         
# --------+----------+---------------------+---------------------
#  105818 | R-185511 | 2023-06-01 10:00:00 | 2023-05-12 14:03:08
# (1 ligne)



    #** scheduled_date et date_deadline de stock_picking **********************
    SQL="SELECT id,max_date FROM stock_picking"
    cr_src.execute(SQL)
    rows = cr_src.fetchall()
    for row in rows:
        SQL="UPDATE stock_picking SET scheduled_date=%s,date_deadline=%s WHERE id=%s"
        cr_dst.execute(SQL,[row["max_date"],row["max_date"],row["id"]])
    cnx_dst.commit()
    #******************************************************************************







sys.exit()

for soc in socs:


    #** Paramètres ****************************************************************
    db_src = "pg-odoo8-%s"%soc
    db_dst = "pg-odoo16-%s"%soc
    #******************************************************************************

    #cnx,cr=GetCR(db_src)
    #db_vierge = db_dst+'-vierge'
    #SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
    #cde="""echo '"""+SQL+"""' | psql postgres"""
    #lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue

    cnx_src,cr_src=GetCR(db_src)
    cnx_dst,cr_dst=GetCR(db_dst)
    #cnx_vierge,cr_vierge=GetCR(db_vierge)




    debut=datetime.now()

    debut = Log(debut, "** Début migration %s ***********************************************"%(db_dst))

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
    #**************************************************************************

    #** Affecter les bonnes séquences dans stock_picking_type *****************
    cr_dst.execute("update stock_picking_type set sequence_id=11 where code='incoming'")
    cr_dst.execute("update stock_picking_type set sequence_id=12 where code='outgoing'")
    cnx_dst.commit()
    #**************************************************************************

    debut = Log(debut, "ir_sequence")





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
    #*******************************************************************************


    debut = Log(debut, "res_partner")











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

    debut = Log(debut, "res_users")




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
    #******************************************************************************

    debut = Log(debut, "product")









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
    #******************************************************************************

    debut = Log(debut, "account")










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
    #******************************************************************************

    debut = Log(debut, "mrp")











    #** purchase_order ************************************************************
    MigrationTable(db_src,db_dst,'purchase_order')
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
    default_location_src_id  = 8
    default_location_dest_id = 8
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


    #** stock_picking *************************************************************
    default={
        "location_id"     : 7,  #TODO A Revoir => Mettre les données de stock_picking_type
        "location_dest_id": 7,  #TODO A Revoir
    }
    MigrationTable(db_src,db_dst,'stock_picking', default=default)
    debut = Log(debut, "stock_picking")
    # #******************************************************************************



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


    #** stock_route ******************************************************
    #TODO : Ne pas migrer cette table => Laisser la table par défaut
    #MigrationTable(db_src,db_dst,'stock_location_route',table_dst='stock_route',text2jsonb=True)
    #MigrationTable(db_src,db_dst,'stock_route_product')
    #debut = Log(debut, "stock_route")
    #MigrationTable(db_src,db_dst,'stock_rule')           #TODO : Ne pas migrer cette table => Laisser la table par défaut
    #MigrationTable(db_src,db_dst,'stock_location_route') #TODO : Ne pas migrer cette table => Laisser la table par défaut
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

    #** Initialisation location_src_id et location_dest_id dans stock_rule ********
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
        print(row["action"])
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
    MigrationTable(db_src,db_dst,'stock_move')
    debut = Log(debut, "stock_move")
    #******************************************************************************


    #** stock_move_line (45 mn de traitement pour odoo1) **************************
    debut = Log(debut, "debut stock_move_line (prévoir 45mn pour odoo1)")
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
    debut = Log(debut, "account_move_line")
    #******************************************************************************


    #** account_invoice_line => account_move **************************************
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
            ai.payment_term
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
                    invoice_payment_term_id=%s
                where id=%s
            """
            # order_id=%s,

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
                move_id
            ))
            SQL="""
                SELECT 
                    ail.id,
                    ail.product_id,
                    ail.name,
                    ail.price_unit,
                    ail.price_subtotal,
                    ail.sequence
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
                        sequence=%s
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
    debut = Log(debut, "account_invoice_line => account_move")
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


    #** Enlever les écritures de TVA des lignes de factures ***********************
    SQL="""
        update account_move_line set display_type='payment_term' 
        where account_id in (select id from account_account where account_type in ('asset_receivable', 'liability_payable'));
        update account_move_line set display_type='tax' where tax_line_id is not null;
    """
    cr_dst.execute(SQL)
    cnx_dst.commit()
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
        "is_ctrl100_gamme_standard",
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
        "is_presse_classe",
        "is_presse_cycle",
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
    # *************************************************************************




    #** init weight product_product (nouveau champ) ***************************
    SQL="update product_product set weight=(select weight from product_template pt where pt.id=product_tmpl_id)"
    cr_dst.execute(SQL)
    cnx_dst.commit()
    #**************************************************************************


    #** stock_route ***********************************************************
    MigrationTable(db_src,db_dst,'stock_location_route',table_dst='stock_route',text2jsonb=True)
    MigrationTable(db_src,db_dst,'stock_route_product')
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
        print(row["id"], row["field_id"], row["fied_name"], row["model"])
        SQL="SELECT id from ir_model_fields where model='product.template' and name=%s"
        cr_dst.execute(SQL,[row["fied_name"]])
        rows_dst = cr_dst.fetchall()
        for row_dst in rows_dst:
            SQL="UPDATE is_config_champ_line SET name=%s WHERE id=%s"
            cr_dst.execute(SQL,[row_dst["id"],row["id"]])
    cnx_dst.commit()
    #**************************************************************************



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
        #print(row)

        SQL="""
            INSERT INTO purchase_order_stock_picking_rel (purchase_order_id,stock_picking_id)
            VALUES (%s,%s);
        """
        cr_dst.execute(SQL,[row["order_id"],row["picking_id"]])
    cnx_dst.commit()
    #**************************************************************************






    debut = Log(debut, "** Fin migration %s ***********************************************"%(db_dst))
