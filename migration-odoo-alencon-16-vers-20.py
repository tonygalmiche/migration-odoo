#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *


#** Paramètres ****************************************************************
db_src = "alencon16"
db_dst = "alencon20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** Tables diverses **********************************************************
tables=[
    "is_suivi_sante",
    "is_badge",
    "is_database",
    "is_equipement",
    "is_equipement_champ_line",
    "is_equipement_type",
    "is_etat_presse",
    "is_etat_presse_regroupement",
    "is_ilot",
    "is_mem_var",
    "is_of",
    "is_of_declaration",
    "is_of_rebut",
    "is_of_tps",
    "is_outillage_constructeur",
    "is_presse_arret",
    "is_presse_arret_of_rel",
    "is_presse_classe",
    "is_presse_cycle",
    "is_presse_cycle_of_rel",
    "is_presse_puissance",
    "is_raspberry",
    "is_raspberry_entree_sortie",
    "is_raspberry_zebra",
    "is_releve_qt_produite",
    "is_releve_qt_produite_ligne",
    "is_res_company_indicateur",
    "is_res_company_indicateur_affichage",
    "is_res_company_users_rel",
    "is_res_users",
    "is_theia_alerte",
    "is_theia_alerte_type",
    "is_theia_habilitation_operateur",
    "is_theia_trs",
    "is_theia_validation_action",
    "is_theia_validation_action_groupe_rel",
    "is_theia_validation_groupe",
    "is_theia_validation_groupe_employee_rel",
    "is_type_defaut",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************
