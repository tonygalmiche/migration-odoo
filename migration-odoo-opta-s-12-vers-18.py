#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os

#** Paramètres ****************************************************************
db_src = "opta-s12"
db_dst = "opta-s18"
#******************************************************************************

cnx,cr=GetCR(db_src)
cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


#** res_partner ***************************************************************
MigrationTable(db_src,db_dst,'res_partner_title',text2jsonb=True)
default={
    'autopost_bills': 'ask',
}
MigrationTable(db_src,db_dst,'res_partner',text2jsonb=True,default=default)
#******************************************************************************


#** res_users *****************************************************************
table = 'res_users'
default = {'notification_type': 'email'}
MigrationTable(db_src,db_dst,table,default=default)
#******************************************************************************


#** product *******************************************************************
default={
    "service_tracking": "no",
    #"sale_line_warn": "no-message",
}
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True, default=default)
MigrationTable(db_src,db_dst,'product_product')
#property_account_income_id  = JsonAccountCode2Id(cr_dst,'706000')
#set_json_property(cr_dst,cnx_dst,'product_template', 1, 'property_account_income_id' , 1, property_account_income_id)
#property_account_income_id  = JsonAccountCode2Id(cr_dst,'706100')
#set_json_property(cr_dst,cnx_dst,'product_template', 2, 'property_account_income_id' , 1, property_account_income_id)
#******************************************************************************




sys.exit()





# ** Tables diverses **********************************************************
tables=[
    'is_activite',
    'is_activite_dynacase_rel',
    'is_activite_pieces_jointes_rel',
    'is_affaire',
    'is_affaire_attachment_rel',
    'is_affaire_consultant_rel',
    'is_affaire_convention_rel',
    'is_affaire_dynacase_rel',
    'is_affaire_forfait_jour',
    'is_affaire_intervenant',
    'is_affaire_phase',
    'is_affaire_phase_activite',
    'is_affaire_propositions_rel',
    'is_affaire_taux_journalier',
    'is_affaire_vendue_par',
    'is_cause',
    'is_compte_banque',
    'is_depense_effectuee_par',
    'is_dynacase',
    'is_export_compta',
    'is_export_compta_ana',
    'is_export_compta_ana_attachment_rel',
    'is_export_compta_ana_ligne',
    'is_export_compta_attachment_rel',
    'is_export_compta_ligne',
    'is_facture_st',
    'is_frais',
    'is_frais_dynacase_rel',
    'is_frais_justificatif_rel',
    'is_frais_lignes',
    'is_secteur',
    'is_suivi_production_affaire',
    'is_suivi_production_affaire_line',
    'is_suivi_temps',
    'is_suivi_temps_simplifie_wizard',
    'is_type_intervention',
    'is_type_offre',
    'is_type_societe',
]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table)
#******************************************************************************
