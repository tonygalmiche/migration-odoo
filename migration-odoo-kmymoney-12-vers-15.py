#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "kmymoney12"
db_dst = "kmymoney15"
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
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************
