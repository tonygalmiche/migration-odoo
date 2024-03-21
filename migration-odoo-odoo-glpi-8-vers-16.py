#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from datetime import datetime
from migration_fonction import *


#** Paramètres ****************************************************************
db_src    = "odoo-glpi8"
db_dst    = "odoo-glpi16"
#******************************************************************************

cnx_src   , cr_src    = GetCR(db_src)
cnx_dst   , cr_dst    = GetCR(db_dst)
debut=datetime.now()


#TODO : 
#- Créer un groupe 'Admin odoo-glpi' car l'admin n'a plus aucun accès
#- Automatiser le processus de migration


tables=[
    'is_action',
    'is_action_globale',
    'is_action_globale_ordinateur_rel',
    'is_action_globale_utilisateur_rel',
    'is_bureau',
    'is_equipement_reseau',
    'is_identifiant',
    'is_logiciel',
    'is_ordinateur',
    'is_ordinateur_partage_rel',
    'is_partage',
    'is_pureftp',
    'is_save_mozilla',
    'is_save_serveur',
    'is_service',
    'is_site',
    'is_site_utilisateur_rel',
    'is_suivi_sauvegarde',
    'is_type_ordinateur',
    'is_utilisateur',
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
    debut = Log(debut, table)




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

#** res_company ***************************************************************
MigrationDonneesTable(db_src,db_dst,'res_company')
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
MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_position', field_dst='property_account_position_id')
debut = Log(debut, "res_users")
#******************************************************************************



tables=[
   'ir_attachment',
    #'email_template',
    #'ir_mail_server',
    #'ir_sequence',
    #'mail_alias',
    #'mail_followers',
    #'mail_followers_mail_message_subtype_rel',
    #'mail_group',
    #'mail_group_res_group_rel',
    'mail_mail',
    #'mass_field_rel',
    #'mass_object',
    'message_attachment_rel',
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
    debut = Log(debut, table)


#** mail_message *****************************************************************
#TODO : Consomme beacoup  de mémoire => Cela risque de planter si je lance les 4 migrations en même temps
table = 'mail_message'
default = {'message_type': 'notification'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************

#** mail_message_subtype ******************************************************
table = 'mail_message_subtype'
MigrationTable(db_src,db_dst,table,text2jsonb=True)
#******************************************************************************


# ** ir_filters ***************************************************************
# ** Si le filtre n'a pas d'action associée il sera visible dans tous les menus du modèle
# ** Et comme l'id de l'action change lors du changement de version, il est préférable de vider ce champ
default = {'sort': []}
MigrationTable(db_src,db_dst,"ir_filters", default=default)
SQL="""
    update ir_filters set action_id=NULL, active='t';
    update ir_filters set user_id=2 where user_id=1;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************

