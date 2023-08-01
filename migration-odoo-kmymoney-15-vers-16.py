#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "kmymoney15"
db_dst = "kmymoney16"
#******************************************************************************

cnx,cr=GetCR(db_src)

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** Tables diverses **********************************************************
tables=[
    "res_partner",
    "kmn_account_move",
    "kmn_account_type",
    "kmn_accounts",
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
