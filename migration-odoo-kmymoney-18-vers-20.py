#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "kmymoney18"
db_dst = "kmymoney20"
#******************************************************************************

cnx,cr=GetCR(db_src)

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** res_partner **************************************************************
default={
#    'autopost_bills': 'ask',
}
MigrationTable(db_src,db_dst,'res_partner',default=default)
#SQL="""
#    update res_partner set complete_name=name where complete_name is null;
#"""
#cr_dst.execute(SQL)
#cnx_dst.commit()
# *****************************************************************************


# ** Tables diverses **********************************************************
tables=[
    "kmn_account_type",
    "kmn_accounts",
    "kmn_account_move",
    "is_suivi_sante",
    "ir_filters",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** ir_filters ***************************************************************
# ** Si le filtre n'a pas d'action associée il sera visible dans tous les menus du modèle
# ** Et comme l'id de l'action change lors du changement de version, il est préférable de vider ce champ
SQL="""
    update ir_filters set action_id=NULL;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************
