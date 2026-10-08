#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *


#** Paramètres ****************************************************************
db_src = "alencon16"
db_dst = "alencon20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (99 partenaires, 15 utilisateurs dans alencon16)
MigrationTable(db_src,db_dst,'res_partner')
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# ** commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
SQL="""
    update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# ** complete_name n'existe pas en v16 => à calculer (même logique que _get_complete_name d'Odoo 20) :
# ** contact avec parent (pas une société) : "nom du partenaire commercial (ou du parent), nom", sinon : nom
SQL="""
    update res_partner p set complete_name = case
        when p.parent_id is not null and not coalesce(p.is_company,false)
            then trim(coalesce(
                (select nullif(c.name,'') from res_partner c where c.id=p.commercial_partner_id),
                (select name from res_partner where id=p.parent_id),
                ''
            ) || ', ' || coalesce(p.name,''))
        else trim(coalesce(p.name,''))
    end;
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# ** Groupes : correspondance par nom d'identifiant externe (is_plastigray16.xxx => is_alencon20.xxx)
# ** Les groupes absents en v20 (ventes, achats, stock...) sont ignorés
MigrationResGroups(db_src,db_dst)

# ** base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20 (3 et 4 au lieu de 4 et 5)
# ** => les identifiants externes base pointent sur les ids de la source et l'ancien default (id 3) perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)
#******************************************************************************


# ** res_company **************************************************************
# Nom, adresse (partenaire 1), e-mail, téléphone, paramètres THEIA (is_*)... ; devise retrouvée par son code (EUR)
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************


# ** hr_employee **************************************************************
# Employés, départements, postes, catégories et une hr_version par employé (voir MigrationHrEmployee)
MigrationHrEmployee(db_src,db_dst)
#******************************************************************************


# ** Séquence du relevé des quantités produites *******************************
# Dernier relevé en v16 : 00471 => le prochain doit être 00472 (sinon la v20 repart à 00001)
cr_src.execute("select id from ir_sequence where code='is.releve.qt.produite'")
id_src = cr_src.fetchone()['id']
cr_dst.execute("select id from ir_sequence where code='is.releve.qt.produite'")
id_dst = cr_dst.fetchone()['id']
MigrationIrSequence(db_src,db_dst,id_src=id_src,id_dst=id_dst)
#******************************************************************************


# ** Valeur par défaut : langue des nouveaux partenaires (fr_FR) **************
SQL="""
    insert into ir_default (field_id, json_value)
    select id, '"fr_FR"' from ir_model_fields where model='res.partner' and name='lang'
    and not exists (select 1 from ir_default d join ir_model_fields f on f.id=d.field_id
                    where f.model='res.partner' and f.name='lang' and d.user_id is null and d.company_id is null)
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Filtres favoris **********************************************************
MigrationIrFilters(db_src,db_dst,modules={'is_plastigray16': 'is_alencon20', 'is_alencon': 'is_alencon20'})
#******************************************************************************


# ** Chatter ******************************************************************
# ~290 messages (surtout des créations) et leurs abonnés ; suivi des modifications ajouté au corps (format v20)
MigrationChatter(db_src,db_dst,['res.partner','res.company','hr.employee','hr.department','is.releve.qt.produite'])
#******************************************************************************


# ** Pièces jointes ***********************************************************
# Le filestore de production (odoo16) est copié par rsync directement dans le filestore d'alencon20
# (migration-odoo-alencon-16-vers-20.sh) => données seulement, store_fname conservé (copier_fichiers=False)
# CSV des relevés des quantités produites : ~1430, un par relevé
MigrationPiecesJointes(db_src,db_dst,"res_model='is.releve.qt.produite'",copier_fichiers=False)
# Images des partenaires (logo de la société sur le partenaire 1, avatar de l'administrateur), mêmes ids de partenaires
# Non repris : is_logo (champ d'is_plastigray16, absent en v20, même image que le partenaire 1), favicon (champ absent
# en v20), images des icônes de paiement, des menus et des vues (techniques)
MigrationPiecesJointes(db_src,db_dst,"res_model='res.partner' and res_field like 'image_%'",copier_fichiers=False)
#******************************************************************************





# A supprimer à la fin
sys.exit()


# ** Tables diverses (5mn) ****************************************************
# Volumes dans alencon16 (ubuntu2604, copie ancienne, relevés le 27/09/2026) :
#   is_presse_cycle            12,7 M lignes  1,8 Go
#   is_presse_cycle_of_rel     13,8 M lignes  1,1 Go
#   is_theia_trs                352 k lignes   85 Mo
# => is_presse_cycle et sa table de relation font ~97 % du volume

tables=[
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


# ** Grosses tables des cycles presse *****************************************
# Vidées ensemble (TRUNCATE) puis rechargées par COPY FREEZE : voir MigrationTablesTruncate
# is_presse_cycle_of_rel référence is_of : is_of doit donc être reprise avant (liste ci-dessus)
MigrationTablesTruncate(db_src,db_dst,["is_presse_cycle","is_presse_cycle_of_rel"])
#******************************************************************************
