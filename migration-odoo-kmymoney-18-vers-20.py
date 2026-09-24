#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *


#** Paramètres ****************************************************************
db_src = "kmymoney18"
db_dst = "kmymoney20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** res_partner **************************************************************
MigrationTable(db_src,db_dst,'res_partner')

# ** commercial_partner_id vide (héritage des anciennes migrations) : un partenaire sans parent est son propre partenaire commercial
SQL="""
    update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
# *****************************************************************************


# ** Tables diverses **********************************************************
tables=[
    "kmn_account_type",
    "kmn_accounts",
    "kmn_account_move",
    "is_suivi_sante",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** ir_filters ***************************************************************
MigrationIrFilters(db_src,db_dst,modules={'is_kmymoney18': 'is_kmymoney20'})
#******************************************************************************
