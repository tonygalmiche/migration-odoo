#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "france-filets10"
db_dst = "france-filets15"
#******************************************************************************

cnx,cr=GetCR(db_src)
# db_migre = db_dst+'_migre'
# SQL="DROP DATABASE "+db_migre+";CREATE DATABASE "+db_migre+" WITH TEMPLATE "+db_dst
# cde='echo "'+SQL+'" | psql postgres'
# lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
#db_dst = db_migre

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)



# MigrationTable(db_src,db_dst,'mail_message_subtype')



# sys.exit()



# ** purge des tests **********************************************************
SQL="""
    delete from account_partial_reconcile ;
    delete from account_move;
    delete from mail_channel;
    delete from mail_alias;
    delete from mail_mail;
    delete from mail_message;
    delete from mail_message_subtype;
    delete from mail_followers;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** res_partner ***************************************************************
#MigrationTable(db_src,db_dst,'res_partner_title')
MigrationTable(db_src,db_dst,'res_partner')
#******************************************************************************


#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** res_users (id=2) **********************************************************
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


# ** Tables diverses **********************************************************
tables=[
    "is_chantier",
    #"is_chantier_equipe_rel",  # TODO : A prioir, cette table n'est plus utilisée et n'existe plus
    "is_chantier_fin_chantier_attachment_rel",
    "is_chantier_piece_jointe_attachment_rel",
    "is_chantier_planning",
    "is_chantier_planning_equipe_rel",
    "is_chantier_user_rel",
    "is_controle_gestion",
    "is_creation_planning",
    "is_creation_planning_preparation",
    "is_equipe",
    "is_equipe_absence",
    "is_equipe_message",
    "is_export_compta",
    "is_export_compta_ligne",
    "is_filet",
    "is_filet_mouvement",
    "is_groupe_client",
    "is_motif_archivage",
    "is_nacelle",
    "is_origine",
    "is_planning",
    "is_planning_line",
    "is_planning_pdf",
    "is_region",
    "is_sale_order_controle_gestion",
    "is_sale_order_planning",
    "is_sale_order_planning_equipe_rel",
    "is_secteur_activite",
    "is_suivi_budget",
    "is_suivi_budget_groupe_client",
    "is_suivi_budget_mois",
    "is_suivi_budget_secteur_activite",
    "is_suivi_budget_top_client",
    "is_type_prestation",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


#** product *******************************************************************
#default={
#    'detailed_type': 'consu',
#}
rename={
    'type':'detailed_type'
}
MigrationTable(db_src,db_dst,'product_template',rename=rename)
MigrationTable(db_src,db_dst,'product_product')
#******************************************************************************



#** Traductions account_payment_term ******************************************
SQL="SELECT id,name FROM product_template"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    res_id = row["id"]
    value=GetTraduction(cr_src,'product.template','name', res_id)
    if value:
        SQL="update product_template set name=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
    value=GetTraduction(cr_src,'product.template','note', res_id)
    if value:
        SQL="update product_template set note=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
SQL="delete from ir_translation where name like 'product.template,%'"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************









#** sale_order ***************************************************************
MigrationTable(db_src,db_dst,'sale_order')
MigrationTable(db_src,db_dst,'sale_order_line')
#******************************************************************************


#** account_account ***********************************************************
table='account_account'
rename={
    'user_type': 'user_type_id',
}
MigrationTable(db_src,db_dst,table,rename=rename)
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


# account_account : set user_type_id et internal_type *************************
cr_dst.execute("update account_account set user_type_id=18 ,internal_type='other'")                               # Hors bilan
cr_dst.execute("update account_account set user_type_id=1  ,internal_type='receivable' where code like '411___'") # Recevable
cr_dst.execute("update account_account set user_type_id=2  ,internal_type='payable'    where code like '401___'") # Payable
cr_dst.execute("update account_account set user_type_id=5  ,internal_type='other'      where code like '471___'") # Actif circulant
cr_dst.execute("update account_account set user_type_id=5  ,internal_type='other'      where code like '4456__'") # Actif circulant
cr_dst.execute("update account_account set user_type_id=9  ,internal_type='other'      where code like '4457__'") # Passif circulant
cr_dst.execute("update account_account set user_type_id=13 ,internal_type='other'      where code like '7_____'") # Revenus
cr_dst.execute("update account_account set user_type_id=15 ,internal_type='other'      where code like '6_____'") # Dépenses
cr_dst.execute("update account_account set user_type_id=8  ,internal_type='other'      where code like '2_____'") # Immobilisations
cr_dst.execute("update account_account set user_type_id=3  ,internal_type='other'      where code like '512___'") # Banque et liquidités
cr_dst.execute("update account_account set user_type_id=9  ,internal_type='receivable' where code like '512101'") # Passif circulant
cnx_dst.commit()
#******************************************************************************


#** product_template **************************************************************
MigrationIrProperty(db_src,db_dst,'product.template', 'property_account_income_id')
MigrationIrProperty(db_src,db_dst,'product.template', 'property_account_expense_id')
#******************************************************************************


#** account_tax **************************************************************
SQL="""
    delete from account_tax_repartition_line;
    delete from account_account_tag_account_tax_repartition_line_rel;
    -- update res_company set account_purchase_tax_id=11;
    -- update res_company set account_sale_tax_id=1;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
table='account_tax'
rename={
    'type':'amount_type'
}
default={
    'tax_group_id': 1,
    'country_id'  : 75, # France
}
MigrationTable(db_src,db_dst,table,rename=rename,default=default)
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
#******************************************************************************


#** Ajouter les comptes sur les taxes *****************************************
SQL="SELECT id FROM account_tax"
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
       INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, invoice_tax_id, company_id, sequence, use_in_tax_closing)
       VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True])
    SQL="""
       INSERT INTO account_tax_repartition_line (factor_percent,repartition_type, refund_tax_id, company_id, sequence, use_in_tax_closing)
       VALUES (%s,%s,%s,%s,%s,%s);
    """
    cr_dst.execute(SQL,[100,'tax',id,1,1,True])
cnx_dst.commit()
#******************************************************************************


#** account_journal ***********************************************************
default={
    'active'                 : True,
    'invoice_reference_type' :'invoice',
    'invoice_reference_model': 'odoo',
}
MigrationTable(db_src,db_dst,"account_journal",default=default)
#******************************************************************************


#** Position fiscale **********************************************************
MigrationTable(db_src,db_dst,'account_fiscal_position')
MigrationTable(db_src,db_dst,'account_fiscal_position_tax')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_position_id', field_dst='property_account_position_id')
#******************************************************************************


#** account_payment_term ******************************************************
table="account_payment_term"
default = {'sequence': 10}
MigrationTable(db_src,db_dst,table,default=default)
table="account_payment_term_line"
default = {'option': "day_after_invoice_date"}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** Traductions account_payment_term ******************************************
SQL="SELECT id,name FROM account_payment_term"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    res_id = row["id"]
    value=GetTraduction(cr_src,'account.payment.term','name', res_id)
    if value:
        SQL="update account_payment_term set name=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
    value=GetTraduction(cr_src,'account.payment.term','note', res_id)
    if value:
        SQL="update account_payment_term set note=%s where id=%s"
        cr_dst.execute(SQL,[value,res_id])
SQL="delete from ir_translation where name like 'account.payment.term,%'"
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Property res_parter ******************************************************
MigrationIrProperty(db_src,db_dst,'res.partner','property_payment_term_id')
MigrationIrProperty(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_receivable_id', field_dst='property_account_receivable_id')
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_payable_id'   , field_dst='property_account_payable_id')
#******************************************************************************


















# ** account_bank_statement ****************************************************
MigrationTable(db_src,db_dst,'account_bank_statement')
rename={'name':'payment_ref'}
default={'move_id': 2}
MigrationTable(db_src,db_dst,'account_bank_statement_line',rename=rename,default=default)
SQL="""
    update account_bank_statement set state='open';
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


#** account_move_line *********************************************************
MigrationTable(db_src,db_dst,'account_full_reconcile')
rename={}
default={
    'move_type'  : 'entry',
    'currency_id': 1,
}
MigrationTable(db_src,db_dst,'account_move'     , table_dst='account_move'     , rename=rename,default=default)
default={
    'currency_id': 1,
    'debit': 0,
    'credit': 0,
    'amount_currency': 0,
}
#rename={
#    'tax_amount': 'tax_base_amount',
#    'reconcile_partial_id': 'full_reconcile_id',
#}
rename={}
MigrationTable(db_src,db_dst,'account_move_line', table_dst='account_move_line', rename=rename,default=default)
#******************************************************************************




#** account_invoice_line => account_move **************************************
SQL="""
    SELECT 
        ai.id,
        ai.move_id,
        ai.number,
        ai.date_invoice,
        ai.type,
        rp.name,
        ai.date_due,
        ai.amount_untaxed,
        ai.amount_untaxed_signed,
        ai.amount_tax,
        ai.amount_total,
        ai.residual,
        ai.user_id,
        ai.fiscal_position_id,
        ai.name move_name,
        ai.origin,
        ai.payment_term_id
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
        cr_dst.execute(SQL,(
            row['date_invoice'],
            row['type'],
            row['name'],
            row['date_due'],
            row['amount_untaxed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['amount_untaxed_signed'],
            row['amount_tax'],
            row['amount_total'],
            row['residual'],
            row['user_id'],
            row['fiscal_position_id'],
            row['origin'],
            row['payment_term_id'],
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
#cr_dst.execute(SQL)
#cnx_dst.commit()
#******************************************************************************


#** Enlever les écritures de TVA des lignes de factures ***********************
SQL="""UPDATE account_move_line set exclude_from_invoice_tab='t' WHERE product_id is null"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Migration tax_code_id ****************************************************
cr_dst.execute("update account_move_line set payment_id=Null")
cr_dst.execute("update account_move_line set amount_currency=(debit-credit)")
cr_dst.execute("update account_move_line set company_currency_id=currency_id")
cnx_dst.commit()
SQL="""
    select 
        aml.id move_line_id,
        aml.name,
        aml.debit,
        aml.credit,
        at.id tax_line_id
    from account_move_line aml inner join account_tax at on aml.tax_line_id=at.id 
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
#******************************************************************************


#** Migration des taxes sur les factures **************************************
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





# Recherche du compte 512001 pour le reglement ci-dessous *********************
SQL="select id from account_account where code='512001'"
destination_account_id=False
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    destination_account_id = row["id"]
if not destination_account_id:
    print("Compte 512001 non trouvé !")
    sys.exit()
 #******************************************************************************


#** account_payment ***********************************************************
cr_dst.execute("DELETE FROM account_payment")
cnx_dst.commit()
SQL="""
    select 
        am.id,
        am.name, 
        l.credit,
        a2.code,
        am.partner_id
    from account_move am join account_move_line l on am.id=l.move_id join account_journal aj on am.journal_id=aj.id 
                         join account_account a2 on l.account_id=a2.id  
    where aj.type='bank' and a2.code like '4%' ;
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    debit = row["credit"]
    SQL="""
    INSERT INTO account_payment (move_id, is_reconciled, is_matched, is_internal_transfer, payment_method_id, amount, payment_type, partner_type, currency_id, partner_id, destination_account_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """
    cr_dst.execute(SQL,[row['id'],True,False,False,1,debit,'inbound','customer',1,row["partner_id"],destination_account_id])
    cr_dst.execute("update account_payment set payment_method_line_id=3")
cnx_dst.commit()

#******************************************************************************




#** Lien entre account_move et account_payment ********************************
SQL="select id,move_id from account_payment"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    move_id = row["move_id"]
    SQL="update account_move set payment_id=%s,state='posted' where id=%s"
    cr_dst.execute(SQL,[row["id"],row["move_id"]])
    SQL="update account_move_line set payment_id=%s where move_id=%s"
    cr_dst.execute(SQL,[row["id"],row["move_id"]])
cnx_dst.commit()
#******************************************************************************


#** Factures fournisseurs => inverser les signes => pour réglements ***********
SQL="""
    update account_move set amount_untaxed_signed=-amount_untaxed where move_type='in_invoice';
    update account_move set amount_tax_signed=-amount_tax where move_type='in_invoice';
    update account_move set amount_total_signed=-amount_total where move_type='in_invoice';
    update account_move set amount_residual_signed=-amount_residual where move_type='in_invoice';

    update account_move set posted_before='t' where move_type='in_invoice';
    update account_move set is_move_sent='f' where move_type='in_invoice';

    update account_move_line set price_unit=-price_unit, price_subtotal=-price_subtotal, price_total=-price_total 
    where 
        move_id in (select id from account_move m where m.move_type='in_invoice') and 
        account_id in (select id from account_account where code like '4%');

    update account_move_line set amount_residual=price_total, amount_residual_currency=price_total 
    where 
        move_id in (select id from account_move m where m.move_type='in_invoice') and 
        account_id in (select id from account_account where code like '401%');
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************












#** account_move_line_check_amount_currency_balance_sign **********************
SQL="""
    SELECT
        id,
        debit,
        credit,
        amount_currency
    FROM account_move_line 
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
nb=len(rows)
ct=0
for row in rows:
    ct+=1
    SQL="""
        UPDATE account_move_line 
        SET 
            debit=%s,
            credit=%s,
            amount_currency=%s
        WHERE id=%s
    """
    amount_currency = -(row["credit"] - row["debit"])
    cr_dst.execute(SQL,[
        row["debit"],
        row["credit"],
        amount_currency,
        row["id"],
    ])
cnx_dst.commit()
#******************************************************************************


#** account_move / payment_state **********************************************
SQL="select id,move_id,state from account_invoice"
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    if row["state"]=="open":
        cr_dst.execute("update account_move set payment_state='not_paid' where id=%s",[row["move_id"]])
    if row["state"]=="paid":
        cr_dst.execute("update account_move set payment_state='paid' where id=%s",[row["move_id"]])
cnx_dst.commit()
#******************************************************************************



#** Requetes diverses pour résoudre des anomalies *****************************
SQL="""
    update sale_order set procurement_group_id=Null where procurement_group_id is not null;
    update account_move_line set exclude_from_invoice_tab='f' where exclude_from_invoice_tab is null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************




# ** account_bank_statement ****************************************************
SQL="""
    select *
    from account_bank_statement_line 
    order by id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="""
        INSERT INTO account_move(
            name,
            ref,
            date,
            state,
            move_type,
            to_check,
            journal_id,
            company_id,
            currency_id,
            is_move_sent,
            statement_line_id,
            auto_post,
            amount_total,
            amount_total_signed,
            create_date,
            create_uid,
            write_date,
            write_uid
        )        
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """
    cr_dst.execute(SQL,[
        row['name'],
        row['ref'],
        row['date'],
        'draft',
        'entry',
        False,
        8,
        1,
        1,
        False,
        row['id'],
        False,
        row['amount'],
        row['amount'],
        row['create_date'],
        row['create_uid'],
        row['write_date'],
        row['write_uid'],
    ])
    cr_dst.execute('SELECT LASTVAL()')
    lastid = cr_dst.fetchone()['lastval']
    SQL="update account_bank_statement_line set move_id=%s where id=%s"
    cr_dst.execute(SQL,[lastid,row['id']])
cnx_dst.commit()
#******************************************************************************










#** account_partial_reconcile (Lien entre les factures et les paiements) ******

MigrationTable(db_src,db_dst,'account_partial_reconcile')


# cr_dst.execute("DELETE FROM account_partial_reconcile")
# cnx_dst.commit()
# SQL="select full_reconcile_id,count(*) from account_move_line where full_reconcile_id is not null  group by full_reconcile_id having count(*)=2"
# cr_src.execute(SQL)
# rows = cr_src.fetchall()
# for row in rows:
#     SQL="""
#         select l1.reconcile_id, l1.id debit_move_id,l2.id credit_move_id,l1.debit,l2.credit 
#         from account_move_line l1 join  account_move_line l2 on l1.reconcile_id=l2.reconcile_id and l1.debit>0 and l2.credit>0
#         where l1.reconcile_id="""+str(row["reconcile_id"])
#     cr_src.execute(SQL)
#     rows2 = cr_src.fetchall()
#     for row2 in rows2:
#         full_reconcile_id = row2["full_reconcile_id"]
#         debit_move_id     = row2["debit_move_id"]
#         credit_move_id    = row2["credit_move_id"]
#         credit = row2["credit"]
#         debit  = row2["debit"]
#         SQL="""
#             INSERT INTO account_partial_reconcile (debit_move_id, credit_move_id, full_reconcile_id, debit_currency_id, credit_currency_id, amount, debit_amount_currency, credit_amount_currency,company_id,max_date)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         """
#         cr_dst.execute(SQL,[debit_move_id,credit_move_id,full_reconcile_id,1,1,credit,debit,credit,1,"1990-01-01"])
# cnx_dst.commit()
#******************************************************************************
















#** mail **********************************************************************
DumpRestoreTable(db_src,db_dst,"mail_message_subtype")
MigrationTable(db_src,db_dst,'mail_alias')
MigrationTable(db_src,db_dst,'mail_followers', where="partner_id is not null")
MigrationTable(db_src,db_dst,'mail_followers_mail_message_subtype_rel')
default={
    'message_type'  : 'notification',
}
MigrationTable(db_src,db_dst,'mail_message', default=default)
cr_dst.execute("update mail_message set body='' where body is null") # Sans cela, l'affichage de la facture plante
cnx_dst.commit()
#******************************************************************************


#** mail_message sur les factures (account_invoice_line => account_move) ******
cr_dst.execute("update mail_message set model='account.move' where model='account.invoice'")
cnx_dst.commit()
SQL="SELECT id, move_id FROM account_invoice"
cr_src.execute(SQL)
rows = cr_src.fetchall()
ids={}
for row in rows:
    ids[row["id"]]=row["move_id"]
SQL="SELECT id,res_id FROM mail_message where model='account.move'"
cr_dst.execute(SQL)
rows = cr_dst.fetchall()
for row in rows:
    id=row["id"]
    res_id=row["res_id"]
    res_id=ids.get(res_id,False)
    if res_id:
        SQL="UPDATE mail_message set res_id=%s where id=%s"
        cr_dst.execute(SQL,[res_id,id])
cnx_dst.commit()
#******************************************************************************
