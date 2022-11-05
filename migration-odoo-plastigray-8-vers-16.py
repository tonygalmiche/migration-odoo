#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "pg-odoo8-1"
db_dst = "pg-odoo16-1"
#******************************************************************************

cnx,cr=GetCR(db_src)
#db_vierge = db_dst+'-vierge'
#SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
#cde="""echo '"""+SQL+"""' | psql postgres"""
#lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)
#cnx_vierge,cr_vierge=GetCR(db_vierge)



tables=[
    "is_invest_global",
    "is_invest_detail",
    "is_invest_cde",
    "is_invest_compta",
    "is_demande_conges",
    "is_demande_conges_autre",
    "is_demande_absence_type",
    "is_demande_absence",
    "is_droit_conges",
    "is_demande_conges_export_cegid",
    "is_proforma_chine",
    "is_proforma_chine_line",
]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table)


sys.exit()





tables=[
    "is_ctrl_budget_tdb_famille",
    "is_ctrl_budget_tdb_famille_rel",
    "is_ctrl_budget_tdb_intitule",
    "is_ctrl_budget_tdb_saisie",
    "is_ctrl_budget_tdb",
    "is_ctrl_budget_ana_annee",
    "is_ctrl_budget_ana_product",
    "is_donnee_machine",
    "is_donnee_machine_line",

    "is_ctrl100_operation_standard",
    "is_mold_cycle",
    "is_preventif_moule",
    "is_mold_operation_systematique",
    "is_mold_operation_specifique",
    "is_mold_specification_particuliere",
    "is_mold_frequence_preventif",
    "is_mold_systematique_array",
    "is_mold_specifique_array",
    "is_mold_specification_array",
    "is_mold_piece_specifique",
    "is_mold_surface_aspect",
    "is_dossier_appel_offre",
    "is_ot_affectation",
    "is_ot_temps_passe",
    "is_ot",
    "is_ot_indicateur",
    "is_ctrl100_gamme_standard",
    "is_ctrl100_operation_specifique",
    "is_ctrl100_typologie_produit",
    "is_ctrl100_gamme_mur_qualite_formation",
    "is_ctrl100_gamme_mur_qualite",
    "is_ctrl100_gamme_defautheque_line",
    "is_ctrl100_defautheque",
    "is_ctrl100_defaut",
    "is_ctrl100_defaut_line",
    "is_ctrl100_rapport_controle",
    "is_ctrl100_pareto",


    "is_capteur",
    "is_fiche_tampographie_constituant",
    "is_fiche_tampographie_recette",
    "is_fiche_tampographie_type_reglage",
    "is_fiche_tampographie_reglage",
    "is_fiche_tampographie",
    "is_equipement_champ_line",
    "is_equipement_type",
    "is_equipement",
    "is_theia_validation_action",
    "is_theia_habilitation_operateur",
    #"is_theia_habilitation_operateur_etat",
    "is_theia_lecture_ip",
    "is_theia_alerte_type",
    "is_theia_alerte",
    "is_etat_presse_regroupement",
    "is_raspberry_entree_sortie",
    "is_raspberry_zebra",
    "is_raspberry",
    "is_of",
    "is_of_tps",
    "is_of_declaration",
    "is_presse_cycle",
    "is_presse_arret",
    "is_type_defaut",
    "is_theia_trs",
    "is_theia_validation_groupe",
    "is_preventif_equipement_zone",
    "is_preventif_equipement_heure",
    "is_preventif_equipement",
    "is_preventif_equipement_saisie",
    "is_equipement",
    "is_ilot",
    "is_etat_presse",
]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table)


sys.exit()






#** res_country ***************************************************************
MigrationTable(db_src,db_dst,'res_country',text2jsonb=True)
#******************************************************************************


#** res_partner ****************************************************************
MigrationTable(db_src,db_dst,'res_partner')
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


#** ir_sequence ***************************************************************
#MigrationTable(db_src,db_dst,'ir_sequence') # TODO  la relation « ir_sequence_071 » n'existe pas
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


#** hr_employee ***************************************************************
default={
    "company_id": 1,
    "employee_type": "employee",
    "active": 1,
    "work_permit_scheduled_activity": False,
    "parent_id": None,
}
MigrationTable(db_src,db_dst,'hr_employee', default=default)
SQL="""
    select rr.name, he.id
    from resource_resource rr join hr_employee he on rr.id=he.resource_id
"""
cr_src.execute(SQL)
rows = cr_src.fetchall()
for row in rows:
    SQL="UPDATE hr_employee SET name=%s WHERE id=%s"
    cr_dst.execute(SQL,[row["name"],row["id"]])
cnx_dst.commit()


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


# #** stock_quant ****************************************************************
# default={
#     "reserved_quantity": 0,
# }
# rename={
#    'qty':'quantity'
# }
# MigrationTable(db_src,db_dst,'stock_quant', default=default, rename=rename)
# #******************************************************************************


# #** stock_lot  ****************************************************************
# default={
#     "company_id": 1,
#     "name"      : "??",
# }
# MigrationTable(db_src,db_dst, table_src="stock_production_lot", table_dst="stock_lot", default=default)
# #******************************************************************************


# #** stock_location ***********************************************************
# default={
#     "warehouse_id": 1,
# }
# MigrationTable(db_src,db_dst,'stock_location', default=default, text2jsonb=True)
# parent_store_compute(cr_dst,cnx_dst,'stock_location','location_id')
# #******************************************************************************


# #** sale_order ****************************************************************
# MigrationTable(db_src,db_dst,'sale_order')
# default={
#     "customer_lead": 7,
# }
# MigrationTable(db_src,db_dst,'sale_order_line', default=default)
# #******************************************************************************


# #** purchase_order ****************************************************************
# MigrationTable(db_src,db_dst,'purchase_order')
# cr_src.execute("DELETE FROM purchase_order_line where product_id is null") # TODO : A revoir
# cnx_src.commit()
# default={
# }
# MigrationTable(db_src,db_dst,'purchase_order_line', default=default)
# #******************************************************************************


# #** account_payment_term ******************************************************
# table="account_payment_term"
# default = {'sequence': 10}
# MigrationTable(db_src,db_dst,table,default=default,text2jsonb=True)
# table="account_payment_term_line"
# default = {'months': 0}
# MigrationTable(db_src,db_dst,table,default=default)
# #******************************************************************************


# # ** Property res_parter ******************************************************
# MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_payment_term'         , field_dst='property_payment_term_id') 
# MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_supplier_payment_term', field_dst='property_supplier_payment_term_id') 
# #MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_receivable', field_dst='property_account_receivable_id')
# #MigrationIrProperty(db_src,db_dst,'res.partner', field_src='property_account_payable'   , field_dst='property_account_payable_id')
# #******************************************************************************


# #** stock_picking_type ********************************************************
# default={
#     "company_id"        : 1,
#     "sequence_code"     : "x",
#     "reservation_method": "at_confirm",
#     "create_backorder"  : "ask",
# }
# MigrationTable(db_src,db_dst,'stock_picking_type', default=default, text2jsonb=True)
# #******************************************************************************


# #** stock_move ****************************************************************
# MigrationTable(db_src,db_dst,'stock_move')
# #******************************************************************************


# #** stock_picking *************************************************************
# default={
#     "location_id"     : 7,  #TODO A Revoir => Mettre les données de stock_picking_type
#     "location_dest_id": 7,  #TODO A Revoir
# }
# MigrationTable(db_src,db_dst,'stock_picking', default=default)
# #******************************************************************************




tables=[
    "is_liste_servir",
    "is_liste_servir_message",
    "is_liste_servir_client",
    "is_liste_servir_line",
    "is_liste_servir_um",
    "is_liste_servir_uc",
    "is_bon_transfert",
    "is_bon_transfert",
    "is_bon_transfert_line",
    "is_bl_manuel",
    "is_bl_manuel_line",
    "is_demande_transport",
    "is_galia_base_um",
    "is_galia_base_uc",

    "is_tarif_cial",
    "is_etuve",
    "is_etuve_rsp",
    "is_etuve_commentaire",
    "is_etuve_saisie",
    "is_etuve_of",
    "is_gabarit_controle",
    "is_emplacement_outillage",
    "is_type_controle_gabarit",
    "is_historique_controle",
    "is_operation_controle",
    "is_instrument_mesure",
    "is_famille_instrument",
    "is_piece_montabilite",
    "is_presse_classe",
    "is_presse_puissance",
    "is_outillage_constructeur",
    "is_presse",


    "is_mold",
    "is_dossierf",
    "is_mold_project",
    "is_mold_dateur",
    "is_section_analytique",
    "is_config_champ",
    "is_config_champ_line",
    "is_category",
    "is_gestionnaire",
    "is_budget_responsable",
    "is_budget_nature",
    "is_product_segment",
    "is_product_famille",
    "is_product_sous_famille",
    "is_emb_emplacement",
    "is_emb_norme",
    "is_product_client",
    "is_type_etiquette",
    "is_code_cas",
    "is_product_code_cas",


    "is_commande_externe",
    "is_demande_achat_serie",
    "is_demande_achat_serie_line",
    "is_demande_achat_fg",
    "is_demande_achat_fg_line",
    "is_demande_achat_invest",
    "is_demande_achat_invest_line",
    "is_demande_achat_moule",
    "is_demande_achat_moule_line",
    "is_badge",
    "is_jour_ferie",
    "is_pointage_commentaire",
    "is_pointage",
    "is_rgpd_service",
    "is_rgpd_traitement",
    "is_rgpd_lieu_stockage",
    "is_rgpd_action",
    "is_rgpd_donnee_personnelle",

    "is_deb",
    "is_deb_line",
    "is_deb_synthese",
    "is_reach",
    "is_reach_product",
    "is_reach_product_matiere",
    "is_reach_product_cas",
    "is_cde_ouverte_fournisseur",
    "is_cde_ouverte_fournisseur_product",
    "is_cde_ouverte_fournisseur_tarif",
    "is_cde_ouverte_fournisseur_line",
    "is_cde_ouverte_fournisseur_histo",
    "is_cde_ouverte_fournisseur_message",
    "is_mem_var",
    "is_cout_calcul",
    "is_cout_calcul_log",
    "is_cout_calcul_niveau",
    "is_cout_calcul_actualise",
    "is_cout",
    "is_cout_nomenclature",
    "is_cout_gamme_ma",
    "is_cout_gamme_mo",
    "is_cout_gamme_ma_pk",
    "is_cout_gamme_mo_pk",

    "is_vente_message",
    "is_jour_ferie_country",
    "is_pdc",
    "is_pdc_mold",
    "is_pdc_workcenter",
    "is_pdc_mod",
    "is_cde_ferme_cadencee",
    "is_cde_ferme_cadencee_order",
    "is_cde_ferme_cadencee_histo",
    "is_pic_3ans_saisie",
    "is_pic_3ans",
    "is_facturation_fournisseur",
    "is_facturation_fournisseur_line",
    "is_facturation_fournisseur_justification",
    "mrp_prevision",
    "is_bon_achat_ville",
    "is_bon_achat_ville_line",

]
for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table)


sys.exit()

