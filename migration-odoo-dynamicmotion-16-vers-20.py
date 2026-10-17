#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Dynamic Motion : Odoo 16 (is_dynamicmotion) => Odoo 20 (is_dynamicmotion20)
# Documentation : Documentation/migration-odoo/migration-is_dynamicmotion16-vers-is_dynamicmotion20.md
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit
import re


#** Paramètres ****************************************************************
db_src = "dynamicmotion16"
db_dst = "dynamicmotion20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)

# Heures de début et de fin, durée : affichées aussi en cas d'arrêt (sys.exit, erreur)
debut = datetime.now()
print("Début : %s"%debut.strftime('%d/%m/%Y %H:%M:%S'))
@atexit.register
def AfficherDuree():
    fin = datetime.now()
    print("Fin   : %s"%fin.strftime('%d/%m/%Y %H:%M:%S'))
    print("Durée : %s"%str(fin-debut).split('.')[0])


# ** Mise en page des documents de la société 1 *******************************
# v16 : agencement « Striped », format A4 ; v20 : séparé en agencement (Light) et style des tableaux (Rayé)
# Sur une base suisse neuve, l10n_din5008 impose l'agencement DIN 5008 et son format de papier (marges 20 / 10 mm, 70 dpi)
# Pied de page v16 en citations (<blockquote>) avec texte forcé à 10 px : en v20, les citations ont une barre grise,
# de l'italique et des marges => pied de page trop haut, réduit et coupé par wkhtmltopdf => un paragraphe avec sauts de ligne, en 11 px
# (sans taille forcée, la ligne BANK passe sur 2 lignes et le n° de page est coupé)
# Taille sur le paragraphe et non sur les <span> : sinon la hauteur de ligne reste celle du texte normal (lignes espacées)
# Adresse de la société en titres <h6> (une ligne par titre) : grande marge sous chaque titre en v20 => un paragraphe
def MiseEnPageDocuments():
    cr_dst.execute("select res_id from ir_model_data where module='web' and name='external_layout_standard'")
    layout_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("select res_id from ir_model_data where module='base' and name='paperformat_euro'")
    paperformat_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("update res_company set external_report_layout_id=%s, report_tables_id='striped', paperformat_id=%s where id=1",[layout_id,paperformat_id])
    # Format A4 : marge haute et espace de l'en-tête de la v16 (40 / 35 mm au lieu de 52 / 52 => grand blanc sous l'en-tête)
    # Enregistrement en noupdate : non écrasé par un -u base
    cr_dst.execute("update report_paperformat set margin_top=40, header_spacing=35 where id=%s",[paperformat_id])
    cr_src.execute("select report_footer from res_company where id=1")
    footer = cr_src.fetchone()['report_footer']
    if footer:
        for lang in footer:
            texte = footer[lang]
            texte = re.sub(r'</blockquote>\s*<blockquote[^>]*>\s*', '<br>', texte)
            texte = re.sub(r'<blockquote[^>]*>\s*', '<p style="font-size: 11px;">', texte)
            texte = texte.replace('</blockquote>', '</p>')
            texte = re.sub(r'font-size:\s*10px;\s*', '', texte)
            texte = re.sub(r'\s*style=""', '', texte)
            footer[lang] = texte
        cr_dst.execute("update res_company set report_footer=%s where id=1",[json.dumps(footer)])
    cr_src.execute("select company_details from res_company where id=1")
    details = cr_src.fetchone()['company_details']
    if details:
        details = re.sub(r'</h6>\s*<h6>', '<br>', details)
        details = details.replace('<h6>', '<p style="font-size: 11px;">').replace('</h6>', '</p>')
        details = re.sub(r'<span style="font-size:\s*11px;">(.*?)</span>', r'\1', details)
        cr_dst.execute("update res_company set company_details=jsonb_build_object('en_US',%s::text,'fr_FR',%s::text) where id=1",[details,details])
    cnx_dst.commit()


# ** Reprise 6 : CRM, projets, contenu des réparations ************************
def Reprise6():

    # ** CRM ******************************************************************
    # Étapes : 9 en v16 (les 4 standard, mêmes ids et identifiants externes, et 5 ajoutées) à la place des 4 de la v20
    # team_id (étape réservée à une équipe) => team_ids en v20 : aucune étape réservée en v16
    MigrationTable(db_src,db_dst,'crm_stage')
    # Motifs de perte : les 3 standard (mêmes ids) et « Pas d'intérêt » ; plans récurrents identiques
    MigrationTable(db_src,db_dst,'crm_lost_reason')
    MigrationTable(db_src,db_dst,'crm_recurring_plan')

    # Pistes (128 opportunités dont 1 perdue) : date_action_last renommée en v20
    # mobile (4 pistes, toutes avec un téléphone), email_cc et title (civilité) : supprimés en v20, non repris
    # Sources, supports et campagnes UTM : aucun sur les pistes
    MigrationTable(db_src,db_dst,'crm_lead',rename={'date_action_last':'date_automation_last'})
    MigrationTable(db_src,db_dst,'crm_tag_rel')

    # Langue : ids différents en v20 (fr_FR : 28 en v16, 30 en v20) => par le code
    cr_src.execute("select c.id,l.code from crm_lead c join res_lang l on l.id=c.lang_id")
    for row in cr_src.fetchall():
        cr_dst.execute("update crm_lead set lang_id=(select id from res_lang where code=%s) where id=%s",[row['code'],row['id']])
    cnx_dst.commit()

    # Colonnes calculées et stockées, nouvelles en v20 : même calcul que crm_lead.py
    # - won_status : gagnée (probabilité 100 et étape gagnée), perdue (archivée à probabilité 0) ou en cours
    # - recurring_revenue_prorated : revenu récurrent × probabilité
    # - email_domain_criterion (recherche des doublons) : « @domaine » de l'e-mail, e-mail complet pour les messageries
    #   grand public (_MAIL_PROVIDERS d'iap_tools : aucune dans les pistes, les plus courantes reprises ici par sécurité)
    SQL="""
        update crm_lead l set won_status=case
            when l.probability=100 and (select s.is_won from crm_stage s where s.id=l.stage_id) then 'won'
            when not l.active and l.probability=0 then 'lost'
            else 'pending' end;
        update crm_lead set recurring_revenue_prorated=coalesce(recurring_revenue,0)*coalesce(probability,0)/100;
        update crm_lead set email_domain_criterion=case
            when split_part(email_normalized,'@',2) in ('gmail.com','hotmail.com','hotmail.fr','outlook.com','outlook.fr',
                'yahoo.com','yahoo.fr','icloud.com','live.com','live.fr','bluewin.ch','gmx.ch','gmx.de','gmx.net','orange.fr',
                'free.fr','wanadoo.fr','sfr.fr','laposte.net','protonmail.com','protonmail.ch','proton.me') then email_normalized
            else '@'||split_part(email_normalized,'@',2) end
        where email_normalized like '%@%';
    """
    cr_dst.execute(SQL)
    cnx_dst.commit()
    #**************************************************************************


    # ** Projets **************************************************************
    # Comptes analytiques (39, un par projet, créés en v16 pour les feuilles de temps, non reprises) :
    # plan « Default » de la v16 => plan de projet de la v20 (même id 1)
    MigrationTable(db_src,db_dst,'account_analytic_account')

    # Étapes des projets (identiques), étiquettes (14)
    MigrationTable(db_src,db_dst,'project_project_stage')
    MigrationTable(db_src,db_dst,'project_tags')

    # Projets (46 dont 7 archivés) : analytic_account_id => account_id
    # allocated_hours, allow_timesheets, timesheet_product_id (feuilles de temps), allow_subtasks (toujours actif en v20),
    # partner_email / partner_phone (liés au client) et rating_* (évaluations, désactivées) : supprimés en v20
    MigrationTable(db_src,db_dst,'project_project',rename={'analytic_account_id':'account_id'},default={'is_template':False})
    # Alias e-mail des projets (obligatoire) : ids de la v16 absents en v20 => recréés
    MigrationMailAlias(db_src,db_dst,'project_project')
    MigrationTable(db_src,db_dst,'project_project_project_tags_rel')
    MigrationTable(db_src,db_dst,'project_favorite_user_rel')
    MigrationTable(db_src,db_dst,'project_milestone',default={'sequence':10})
    MigrationTable(db_src,db_dst,'project_update')

    # Étapes des tâches : 55 étapes de projet et 35 étapes personnelles (« Mes tâches » de 5 utilisateurs), à la place des
    # 7 étapes personnelles de l'administrateur créées par la v20 (recréées par Odoo à l'ouverture de « Mes tâches »)
    # auto_validation_kanban_state renommé ; légendes (legend_*) et description supprimées en v20 ; évaluations désactivées
    MigrationTable(db_src,db_dst,'project_task_type',rename={'auto_validation_kanban_state':'auto_validation_state'},default={
        'rating_active'       : False,
        'rating_status'       : 'stage',
        'rating_status_period': 'monthly',
    })
    MigrationTable(db_src,db_dst,'project_task_type_rel')

    # Tâches (27, dont 3 archivées), à la place de la tâche « Bienvenue Administrator ! » créée par la v20
    # planned_hours => allocated_hours ; date_deadline : date => date-heure
    # Aucune sous-tâche, tâche récurrente, dépendance ni tâche liée à un jalon ou à une ligne de commande
    # effective_hours, remaining_hours, progress, overtime... (feuilles de temps) : non repris
    MigrationTable(db_src,db_dst,'project_task',rename={'planned_hours':'allocated_hours'},default={
        'state'                : '01_in_progress',
        'display_in_project'   : True,
        'is_template'          : False,
        'has_template_ancestor': False,
    })
    # État (obligatoire en v20) : kanban_state et is_closed de la v16 (même correspondance que la migration d'Odoo 17)
    # normal => en cours, blocked => changements demandés, done => approuvé, étape fermée => fait (aucune en v16)
    cr_src.execute("select id,kanban_state,is_closed from project_task")
    for row in cr_src.fetchall():
        state = '1_done' if row['is_closed'] else {'blocked':'02_changes_requested','done':'03_approved'}.get(row['kanban_state'],'01_in_progress')
        cr_dst.execute("update project_task set state=%s where id=%s",[state,row['id']])
    cnx_dst.commit()
    # Personnes assignées, avec leur étape personnelle (stage_id), étiquettes
    MigrationTable(db_src,db_dst,'project_task_user_rel')
    MigrationTable(db_src,db_dst,'project_tags_project_task_rel')

    # Jalons, tâches récurrentes et dépendances : activés sur les 46 projets en v16 ; en v20, groupes donnés à tous les
    # utilisateurs internes à l'enregistrement d'un projet (_check_project_group_with_field), pas par une copie en SQL
    # => groupes impliqués par Utilisateur interne et donnés à ses membres, comme pour les entrepôts multiples
    SQL="""
        insert into res_groups_implied_rel (gid,hid)
        select u.res_id, p.res_id from ir_model_data u, ir_model_data p
        where u.module='base' and u.name='group_user'
        and p.module='project' and p.name in ('group_project_milestone','group_project_recurring_tasks','group_project_task_dependencies')
        on conflict do nothing;
        insert into res_groups_users_rel (gid,uid)
        select p.res_id, r.uid from ir_model_data p, ir_model_data u join res_groups_users_rel r on r.gid=u.res_id
        where u.module='base' and u.name='group_user'
        and p.module='project' and p.name in ('group_project_milestone','group_project_recurring_tasks','group_project_task_dependencies')
        on conflict do nothing;
    """
    cr_dst.execute(SQL)
    cnx_dst.commit()
    #**************************************************************************


    # ** Contenu des réparations **********************************************
    # Pièces : repair_line supprimé en v20, les pièces sont des mouvements de stock de la réparation (repair_line_type)
    # - 23 pièces faites : mouvement déjà repris avec les transferts (move_id de la ligne) => type « add »
    # - 1 pièce en brouillon (RO/00024, confirmée) : pas encore de mouvement => créé en brouillon, emplacements de la
    #   réparation (MAP_REPAIR_LINE_TYPE_TO_MOVE_LOCATIONS_FROM_REPAIR : « add » = location_id => location_dest_id)
    # Prix et taxes des pièces : plus sur la réparation en v20 (facturation par une commande de vente), non repris
    cr_src.execute("select move_id from repair_line where move_id is not null and type='add'")
    ids = [row['move_id'] for row in cr_src.fetchall()]
    if ids:
        cr_dst.execute("update stock_move set repair_line_type='add' where id in %s",[tuple(ids)])
    cr_dst.execute("delete from stock_move where repair_id is not null and repair_line_type='add' and state='draft'")
    cr_src.execute("select * from repair_line where move_id is null and type='add' and state='draft'")
    for row in cr_src.fetchall():
        SQL="""
            insert into stock_move (company_id,date,location_id,location_dest_id,procure_method,product_id,product_uom_qty,product_qty,
                uom_id,quantity,picked,state,sequence,repair_id,repair_line_type,picking_type_id,reference,
                create_uid,write_uid,create_date,write_date)
            select r.company_id,%s,r.location_id,r.location_dest_id,'make_to_stock',%s,%s,%s,%s,0,false,'draft',10,r.id,'add',
                r.picking_type_id,r.name,%s,%s,%s,%s
            from repair_order r where r.id=%s
        """
        cr_dst.execute(SQL,[row['create_date'],row['product_id'],row['product_uom_qty'],row['product_uom_qty'],row['product_uom'],
                            row['create_uid'],row['write_uid'],row['create_date'],row['write_date'],row['repair_id']])
    cnx_dst.commit()

    # Description (23), notes du devis (18), forfaits (repair_fee, 23 lignes) et facture (15) : supprimés en v20
    # (facturation par une commande de vente) => ajoutés en tête des notes internes, imprimées sur le rapport de réparation
    # Calculé à partir des notes internes de la v16 : relançable sans doublon
    cr_src.execute("""
        select r.id, r.description, r.quotation_notes, r.internal_notes, m.name as facture
        from repair_order r left join account_move m on m.id=r.invoice_id order by r.id
    """)
    for row in cr_src.fetchall():
        cr_src.execute("select name,product_uom_qty,price_unit,price_subtotal from repair_fee where repair_id=%s order by id",[row['id']])
        forfaits = cr_src.fetchall()
        notes = ""
        if row['description']:
            notes += "<p><strong>Description :</strong> %s</p>"%html.escape(row['description'])
        if row['quotation_notes'] and re.sub(r'<[^>]*>|&nbsp;|\s','',row['quotation_notes']):
            notes += "<p><strong>Notes du devis :</strong></p>%s"%row['quotation_notes']
        if forfaits:
            notes += "<p><strong>Forfaits :</strong></p><ul>"
            for f in forfaits:
                notes += "<li>%s : %g × %.2f = %.2f</li>"%(html.escape(f['name'] or ''),f['product_uom_qty'],f['price_unit'],f['price_subtotal'] or 0)
            notes += "</ul>"
        if row['facture']:
            notes += "<p><strong>Facture :</strong> %s</p>"%html.escape(row['facture'])
        if notes:
            cr_dst.execute("update repair_order set internal_notes=%s where id=%s",[notes+(row['internal_notes'] or ''),row['id']])
    cnx_dst.commit()

    # Garantie : date de fin de garantie (guarantee_limit, 5 réparations) => case « Sous garantie » si elle n'était pas
    # dépassée à la date de la réparation
    cr_src.execute("select id,guarantee_limit,coalesce(schedule_date,create_date::date) as date from repair_order where guarantee_limit is not null")
    for row in cr_src.fetchall():
        cr_dst.execute("update repair_order set under_warranty=%s where id=%s",[row['guarantee_limit']>=row['date'],row['id']])
    cnx_dst.commit()
    #**************************************************************************


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (749 partenaires, 16 utilisateurs dans dynamicmotion16)
# mobile (44 partenaires, dont 20 sans téléphone) et title (civilité, 163 partenaires) : supprimés d'Odoo en v20, non repris
# siret, company_registry : vides dans la source
# Nouvelles colonnes en v20 : valeurs par défaut d'Odoo (autopost_bills, group_rfq et group_on sont obligatoires)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : à reprendre avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner',default={
    'autopost_bills'  : 'ask',
    'group_rfq'       : 'default',
    'group_on'        : 'default',
    'suggest_based_on': '30_days',
    'suggest_days'    : 7,
    'suggest_percent' : 100,
})
MigrationTable(db_src,db_dst,'res_users')

# Société 2 « Delta Line » non reprise : aucune commande, aucun OF, aucune pièce comptable (1 utilisateur y a accès)
MigrationTable(db_src,db_dst,'res_company_users_rel',where="cid=1")

# Dernière connexion de chaque utilisateur (une ligne par utilisateur, Odoo ne garde que la dernière) :
# sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé » (calculé d'après login_date)
MigrationTable(db_src,db_dst,'res_users_log')

# Type d'adresse « private » (adresse privée d'employé) supprimé en v17 => contact (4 partenaires)
# Un contact doit avoir un nom (contrainte res_partner_check_name) : adresse privée sans nom (1 partenaire)
# => nom de l'employé lié (employés non repris, hors périmètre)
cr_src.execute("""
    select p.id,e.name from res_partner p join hr_employee e on e.address_home_id=p.id
    where p.type='private' and coalesce(p.name,'')=''
""")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set name=%s where id=%s",[row['name'],row['id']])
cr_dst.execute("update res_partner set type='contact' where type='private'")
cnx_dst.commit()

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v16 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

# Étiquettes des partenaires (39 étiquettes, 580 liens)
MigrationTable(db_src,db_dst,'res_partner_category')
MigrationTable(db_src,db_dst,'res_partner_res_partner_category_rel')

# Groupes : correspondance par nom d'identifiant externe
# Les groupes des modules absents en v20 (purchase, crm, hr, project, repair, is_vllm2odoo...) sont ignorés
# Hors périmètre (chiffrage) : feuilles de temps, présences, congés et tracker de liens, à ne pas reprendre
# (employés finalement repris, voir plus bas)
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
# => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone...) ; devise retrouvée par son code (CHF)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
# => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Adresse de la société dans les en-têtes, slogan (texte en v16, traduisible en v20) et pied de page (déjà traduisible)
cr_src.execute("select id,company_details,report_header,report_footer from res_company where id=1")
for row in cr_src.fetchall():
    for champ in ('company_details','report_header'):
        if row[champ]:
            cr_dst.execute("update res_company set "+champ+"=jsonb_build_object('en_US',%s::text,'fr_FR',%s::text) where id=%s",[row[champ],row[champ],row['id']])
    if row['report_footer']:
        cr_dst.execute("update res_company set report_footer=%s where id=%s",[json.dumps(row['report_footer']),row['id']])
cnx_dst.commit()
MiseEnPageDocuments()

# URL utilisée par wkhtmltopdf pour charger les CSS et images des rapports : web.base.url n'est pas joignable depuis
# le serveur => PDF sans mise en page ; non écrasée si déjà présente (port ou hébergement différent)
cr_dst.execute("insert into ir_config_parameter (key,value) values ('report.url','http://localhost:8069') on conflict (key) do nothing")
cnx_dst.commit()

# Digest périodique (mail récapitulatif d'Odoo, hebdomadaire par défaut en v20) : désactivé
cr_dst.execute("update digest_digest set state='deactivated'")
cnx_dst.commit()

# Comptes bancaires de la société (2 comptes, Banque Cantonale Neuchâteloise) : res.bank supprimé en v20
# => nom et BIC de la banque sur le compte
# clearing_label_id : nouvelle colonne obligatoire en v20 => libellé par défaut (base.clearing_label_all)
# country_id : nouvelle colonne en v20 => pays du partenaire (même calcul qu'Odoo)
clearing_label_id = ExternalId2Id(cr_dst,'clearing_label_all',module='base',model='clearing.label')
MigrationTable(db_src,db_dst,'res_partner_bank',rename={
    'acc_number'          : 'account_number',
    'sanitized_acc_number': 'sanitized_account_number',
    'acc_holder_name'     : 'holder_name',
},default={'clearing_label_id': clearing_label_id})
cr_src.execute("select pb.id,b.name,b.bic from res_partner_bank pb join res_bank b on b.id=pb.bank_id")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner_bank set bank_name=%s,bank_bic=%s where id=%s",[row['name'],row['bic'],row['id']])
cr_dst.execute("update res_partner_bank b set country_id=p.country_id from res_partner p where p.id=b.partner_id and b.country_id is null")
cnx_dst.commit()
#******************************************************************************


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v16 (27 unités) : les tables qui les utilisent se copient ensuite sans conversion
# Chaque unité est rattachée à la référence de son ancienne catégorie ; identifiants externes uom.* repointés,
# unités v20 absentes de la v16 recréées (voir MigrationUnites)
# Longueurs : la référence est le mm en v16 (m = 1000 mm), nom français du mm = « m » (15 articles) : repris tels quels
# Unité maison « Unités » (id 27, catégorie « Unsorted/Imported Units ») : unité racine à part
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles *****************************************************************
# Devises : EUR active en v16 (2 listes de prix en euros), inactive dans une base v20 suisse => activée
cr_src.execute("select name from res_currency where active")
devises = [row['name'] for row in cr_src.fetchall()]
cr_dst.execute("update res_currency set active=true where name = any(%s)",[devises])
cnx_dst.commit()

# Catégories (8) : nom texte en v16, traduisible en v20 ; comptes des catégories : à reprendre avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Étiquettes (2, sur aucun article) : couleur = n° de la palette d'Odoo (0 à 11) en v16, code hexadécimal en v20
# => code de la palette v20 ($o-colors de web/static/src/scss/primary_variables.scss) ; 0 (sans couleur) => vide
MigrationTable(db_src,db_dst,'product_tag',exclure=['color'])
MigrationTable(db_src,db_dst,'product_tag_product_template_rel')
palette = ['#a2a2a2','#ee2d2d','#dc8534','#e8bb1d','#5794dd','#9f628f','#db8865','#41a9a2','#304be0','#ee2f8a','#61c36e','#9872e6']
cr_src.execute("select id, color from product_tag where color between 1 and 11")
for row in cr_src.fetchall():
    cr_dst.execute("update product_tag set color=%s where id=%s",[palette[row['color']],row['id']])
cnx_dst.commit()

# Attributs (1) et valeurs (4) ; les attributs d'exemple de la v20 sont remplacés
MigrationTable(db_src,db_dst,'product_attribute',default={'active':True})
MigrationTable(db_src,db_dst,'product_attribute_value',default={'active':True})

# Modèles d'articles (741), pas de favoris en v16
# sale_delay (délai de livraison client, 28 articles) : nombre en v16, entier jsonb par société en v20 => repris ci-dessous
# expense_policy => reinvoice_policy (tous à « no »)
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTable(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},exclure=['sale_delay'],
    default={'service_tracking':'no','base_unit_count':0})
cr_src.execute("select id,sale_delay from product_template where coalesce(sale_delay,0)<>0")
for row in cr_src.fetchall():
    cr_dst.execute("update product_template set sale_delay=jsonb_build_object('1',%s::int) where id=%s",[int(row['sale_delay']),row['id']])
# Type « Article stockable » (product, 564 articles) supprimé en v18 => consommable (consu) avec « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
cnx_dst.commit()

# Variantes (741, une par modèle)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})

# Attributs des articles et combinaisons des variantes
for table in [
    'product_attribute_product_template_rel',
    'product_template_attribute_line',
    'product_attribute_value_product_template_attribute_line_rel',
    'product_template_attribute_value',
    'product_variant_combination',
]:
    MigrationTable(db_src,db_dst,table)

# Prix de vente des variantes (lst_price) : calculé et stocké en v20 (prix du modèle + suppléments des attributs)
SQL="""
    update product_product p set lst_price = t.list_price + coalesce((
        select sum(v.price_extra)
        from product_variant_combination c join product_template_attribute_value v on v.id=c.product_template_attribute_value_id
        where c.product_product_id=p.id
    ),0)
    from product_template t where t.id=p.product_tmpl_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Coût des variantes (233 valeurs, 3 autres sur des variantes supprimées en v16) et responsable des articles (741) : propriétés en v16, champs jsonb par société en v20
# Propriétés de la société 2 (Delta Line, non reprise) ignorées
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price',where="p.company_id=1")
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id',where="p.company_id=1")

# Listes de prix (5 : 3 en CHF, 2 en EUR) et lignes (148, toutes actives) ; discount_policy supprimé en v20
# Odoo 20 recrée une liste « Par défaut » (société 1, séquence 10, _activate_or_create_pricelists) : après « Prix EUR » et
# « Prix CH » (séquence 1), elle ne change pas la liste par défaut des clients
MigrationTable(db_src,db_dst,'product_pricelist')
MigrationTable(db_src,db_dst,'product_pricelist_item')
# Liste de prix des clients (29 partenaires ; la 30e valeur est la valeur par défaut de la société 2) : propriété en v16, champ jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist',where="p.company_id=1")

# Prix fournisseurs (317) : unité d'achat de l'article (uom_po_id, supprimé en v20) => unité du prix fournisseur (obligatoire)
MigrationTable(db_src,db_dst,'product_supplierinfo',default={'uom_id':1,'discount':0})
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
for row in cr_src.fetchall():
    cr_dst.execute("update product_supplierinfo set uom_id=%s where id=%s",[row['uom_po_id'],row['id']])
cnx_dst.commit()

# Ids des devises : ids de la v16 => ids de la v20
MigrationDevisesParCode(db_src,db_dst,['product_template','product_pricelist','product_pricelist_item','product_supplierinfo'])

# Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...),
# attributs d'exemple de la v20 (pa_brand, pa_color...) supprimés
cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
MigrationIrModelData(db_src,db_dst,['product.category','product.attribute','product.pricelist'],correspondances={
    'product.category': {
        'product_category_goods'   : categories.get('product_category_all'),
        'product_category_expenses': categories.get('cat_expense'),
        'product_category_services': categories.get('product_category_1'),
    },
})

# A reprendre avec la comptabilité : taxes des articles (product_taxes_rel, product_supplier_taxes_rel : ids des taxes
# différents en v20), comptes des articles et des catégories
# A reprendre avec les pièces jointes : images des articles
#******************************************************************************


# ** Calendriers de travail ***************************************************
# Copiés avec les ids de la v16 (5 calendriers, 40 horaires) : les postes de travail utilisent les calendriers 1 et 6,
# l'id 1 n'est pas le même calendrier en v20 (40 h) qu'en v16 (« Standard 17 hours/week », renommé)
# Horaires : structure v20 (récurrence, durée) => horaire hebdomadaire fixe à heures fixes, comme en v16
# tz et two_weeks_calendar supprimés en v20 (tous les calendriers en Europe/Paris, aucun sur deux semaines)
# Absences (resource_calendar_leaves, 745) : 739 blocages du planning des postes de travail par les ordres de travail,
# repris avec eux (Fabrication) ; 6 congés d'employés, hors périmètre
# Doit précéder les employés et les postes de travail (MigrationHrEmployee remplace les calendriers absents)
# Calendrier 4 « Standard 40 heures/semaine » de la société 2 (Delta Line, non reprise), utilisé par elle seule : non repris
where_calendrier = "t.company_id is distinct from 2"
MigrationTable(db_src,db_dst,'resource_calendar',where=where_calendrier,default={'calendar_type':'fixed'})
MigrationTable(db_src,db_dst,'resource_calendar_attendance',where="t.calendar_id in (select id from resource_calendar t where "+where_calendrier+")",default={
    'duration_based'     : False,
    'recurrency_type'    : 'weeks',
    'recurrency_interval': 1,
    'recurrency_end_type': 'forever',
    'recurrency_count'   : 1,
})
# Colonnes calculées et stockées en v20 (même calcul qu'Odoo : _compute_duration_hours, _compute_hours_per_week...)
cr_dst.execute("update resource_calendar_attendance set duration_hours=hour_to-hour_from")
SQL="""
    update resource_calendar c set
        hours_per_week = coalesce((select sum(a.duration_hours) from resource_calendar_attendance a where a.calendar_id=c.id),0),
        days_per_week  = (select count(distinct a.dayofweek) from resource_calendar_attendance a where a.calendar_id=c.id);
    update resource_calendar set hours_per_day = case when days_per_week>0 then hours_per_week/days_per_week else 0 end;
"""
cr_dst.execute(SQL)
# Calendrier de la société (6, « Standard 40 hours/week ») ; temps plein = heures du calendrier de la société
cr_src.execute("select id,resource_calendar_id from res_company where id=1")
for row in cr_src.fetchall():
    cr_dst.execute("update res_company set resource_calendar_id=%s where id=%s",[row['resource_calendar_id'],row['id']])
SQL="""
    update resource_calendar c set full_time_required_hours = coalesce((
        select r.hours_per_week from res_company rc join resource_calendar r on r.id=rc.resource_calendar_id where rc.id=c.company_id
    ), c.hours_per_week);
    update resource_calendar set work_time_rate = case when full_time_required_hours>0 then hours_per_week/full_time_required_hours else 1 end;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
# Identifiants externes : resource_calendar_std (1), _35h (2), _38h (3) de la v16 ; mrp.mrp_workcenter_calendar (absent de
# la v16) supprimé, recréé au -u de mrp
MigrationIrModelData(db_src,db_dst,['resource.calendar'])
#******************************************************************************


# ** Employés *****************************************************************
# Repris (décision du 16/10/2026, contrairement au chiffrage) : les ordres de travail et temps passés des OF y font
# référence ; feuilles de temps, présences et congés restent hors périmètre
# 6 employés, ressources (employés et postes de travail), départements, postes, catégories, une hr_version par employé
# (voir MigrationHrEmployee) ; nécessite hr en v20, sinon seules les ressources des postes de travail sont reprises
cr_dst.execute("select 1 from information_schema.tables where table_name='hr_employee'")
if cr_dst.fetchone():
    MigrationHrEmployee(db_src,db_dst)
else:
    print("ATTENTION : hr non installé en v20 => employés non repris")
    MigrationTable(db_src,db_dst,'resource_resource',where="t.resource_type='material' and t.id in (select resource_id from mrp_workcenter)")
#******************************************************************************


# ** Postes de travail, nomenclatures, opérations *****************************

# Postes de travail (14) : default_capacity (1, supprimé en v20) et costs_hour_account_id (vide) non repris
MigrationTable(db_src,db_dst,'mrp_workcenter')

# Nomenclatures (95, dont 1 de sous-traitance) : product_uom_id => uom_id ; consumption (supprimé en v20) non repris
# Sous-traitance : nécessite mrp_subcontracting en v20 (type « subcontract », sous-traitants) ; sinon nomenclature non reprise
cr_dst.execute("select 1 from information_schema.tables where table_name='mrp_bom_subcontractor'")
sous_traitance = bool(cr_dst.fetchone())
where_bom = "" if sous_traitance else "t.type<>'subcontract'"
where_bom_id = "" if sous_traitance else "t.bom_id in (select id from mrp_bom where type<>'subcontract')"
if not sous_traitance:
    print("ATTENTION : mrp_subcontracting non installé en v20 => nomenclature de sous-traitance non reprise")
MigrationTable(db_src,db_dst,'mrp_bom',rename={'product_uom_id':'uom_id'},where=where_bom)
MigrationTable(db_src,db_dst,'mrp_bom_line',rename={'product_uom_id':'uom_id'},where=where_bom_id)
if sous_traitance:
    MigrationTable(db_src,db_dst,'mrp_bom_subcontractor')

# Délais de fabrication et de préparation des OF : sur l'article en v16 (produce_delay : 71 articles), sur la
# nomenclature en v20 => valeurs de l'article reportées sur ses nomenclatures (19)
cr_src.execute("""
    select b.id,t.produce_delay,t.days_to_prepare_mo from mrp_bom b join product_template t on t.id=b.product_tmpl_id
    where coalesce(t.produce_delay,0)<>0 or coalesce(t.days_to_prepare_mo,0)<>0
""")
for row in cr_src.fetchall():
    cr_dst.execute("update mrp_bom set produce_delay=%s,days_to_prepare_mo=%s where id=%s",
        [int(row['produce_delay'] or 0),int(row['days_to_prepare_mo'] or 0),row['id']])
cnx_dst.commit()

# Opérations (148, dont 1 archivée) ; cost_mode : nouvelle colonne en v20 (valeur par défaut d'Odoo : temps réel)
# Instructions des opérations (note, 29 opérations, fiche de travail de type texte) : champ supprimé en v20
# => is_instructions d'is_dynamicmotion20, affiché aussi sur les ordres de travail
MigrationTable(db_src,db_dst,'mrp_routing_workcenter',where=where_bom_id,rename={'note':'is_instructions'},default={'cost_mode':'actual'})
#******************************************************************************


# ** Configuration du stock ***************************************************
# Entrepôts, emplacements, types d'opérations, routes, règles copiés avec les ids de la v16 ; correspondance par rôle
# avec ceux créés par la v20 (entrepôt WH) pour recaler ses références ; voir MigrationConfigurationStock
# Société 1 seulement : 3 entrepôts (WH, M24, DM) ; la configuration de la société 2 (entrepôt Delta, ses emplacements,
# types d'opérations, routes et règles) n'est pas reprise
MigrationConfigurationStock(db_src,db_dst,societes=[1])
# Routes des entrepôts (12, sans l'entrepôt Delta), des articles (761), règles de rangement (5)
MigrationTable(db_src,db_dst,'stock_route_warehouse',where="t.warehouse_id in (select id from stock_warehouse where company_id=1)")
MigrationTable(db_src,db_dst,'stock_route_product',where="t.route_id in (select id from stock_route where company_id is null or company_id=1)")
MigrationTable(db_src,db_dst,'stock_putaway_rule',default={'sublocation':'no'})
#******************************************************************************


# ** Stock ********************************************************************
# Pas de lots en v16
# Colis (11, tous livrés chez des clients) : stock_quant_package => stock_package (mêmes colonnes, package_use supprimé)
MigrationTable(db_src,db_dst,'stock_quant_package','stock_package')
# Quants (1 259 : 376 sur WH/Stock, 4 sur Stock DM universel, 2 sur DM/Stock, 1 sur DM/Stock/Stock Archivé, les autres
# sur les emplacements virtuels) ; storage_category_id supprimé en v20 ; réservations à vérifier avec les mouvements
MigrationTable(db_src,db_dst,'stock_quant')

# Règles de réapprovisionnement (56, dont 53 automatiques) : qty_to_order => qty_to_order_manual ; nouvelles colonnes
# obligatoires en v20 : valeurs par défaut d'Odoo ; qty_multiple (0 ou 1 partout) et vendor_id (supplier_id) supprimés
MigrationTable(db_src,db_dst,'stock_warehouse_orderpoint',rename={'qty_to_order':'qty_to_order_manual'},default={
    'min_max_based_on'       : 'one_month',
    'min_max_based_on_factor': 100,
    'daily_demand'           : 0,
})

# Entrepôts multiples : option automatique en v20 à la création d'un 2e entrepôt (stock_warehouse.py), non déclenchée
# par une copie en SQL => groupe impliqué par Utilisateur interne et donné à ses membres, comme le fait Odoo (_apply_group)
SQL="""
    insert into res_groups_implied_rel (gid,hid)
    select u.res_id, w.res_id from ir_model_data u, ir_model_data w
    where u.module='base' and u.name='group_user' and w.module='stock' and w.name='group_stock_multi_warehouses'
    on conflict do nothing;
    insert into res_groups_users_rel (gid,uid)
    select w.res_id, r.uid from ir_model_data w, ir_model_data u join res_groups_users_rel r on r.gid=u.res_id
    where u.module='base' and u.name='group_user' and w.module='stock' and w.name='group_stock_multi_warehouses'
    on conflict do nothing;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** Équipes commerciales *****************************************************
# 6 équipes (Ventes, R&D, Prod, et 3 archivées) : ids identiques pour les 3 standard ; eBay, R&D, Prod en plus en v16
# Étiquettes CRM (58) : reprises ici, utilisées aussi par les devis ; pistes CRM avec la reprise 6
MigrationTable(db_src,db_dst,'crm_team')
# Alias e-mail des équipes (obligatoire) : ids de la v16 absents en v20 => recréés
MigrationMailAlias(db_src,db_dst,'crm_team')
MigrationTable(db_src,db_dst,'crm_team_member')
MigrationTable(db_src,db_dst,'crm_tag')
MigrationIrModelData(db_src,db_dst,['crm.team'])
#******************************************************************************


# ** Conditions de paiement ***************************************************
# 6 conditions copiées avec les ids de la v16, échéances converties au format v20 (voir MigrationConditionsPaiement)
MigrationConditionsPaiement(db_src,db_dst)
# Conditions des clients et des fournisseurs : propriétés en v16, champs jsonb par société en v20 (société 1 seulement)
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id',where="p.company_id=1")
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id',where="p.company_id=1")
#******************************************************************************


# ** Ventes *******************************************************************
# Modèle de devis « Devis DM V1 » (utilisé par 231 commandes, sans lignes ni options) : groupe supprimé en v20, modèles
# toujours disponibles ; template_type : nouvelle colonne obligatoire (valeur par défaut d'Odoo) ; name : texte en v16,
# traduisible (jsonb) en v20
MigrationTable(db_src,db_dst,'sale_order_template',text2jsonb=True,default={'template_type':'quotation'})
MigrationTable(db_src,db_dst,'sale_order_template_line')

# Méthodes de livraison (5, prix fixe : Poste A 15.-, Express International...), utilisées par 3 commandes et 1 transfert
MigrationTable(db_src,db_dst,'delivery_carrier')
MigrationIrModelData(db_src,db_dst,['delivery.carrier'])

# Commandes (397) ; procurement_group_id => stock_reference (plus bas)
# Positions fiscales (384 commandes) : avec la comptabilité (ids différents en v20, l10n_ch)
# document_tax_mode : obligatoire en v20, réglage de la société (prix hors taxe)
MigrationTable(db_src,db_dst,'sale_order',default={'document_tax_mode':'tax_excluded','locked':False})
# État « done » (verrouillée, 9 commandes) supprimé en v17 => « sale » verrouillée (locked)
cr_dst.execute("update sale_order set state='sale', locked=true where state='done'")
cnx_dst.commit()
# Lignes (1 266) : product_uom => product_uom_id ; customer_lead (délai client, 60 lignes) : décimal en v16, entier en v20
# Taxes des lignes (account_tax_sale_order_line_rel) : avec la comptabilité (ids des taxes différents)
MigrationTable(db_src,db_dst,'sale_order_line',rename={'product_uom':'product_uom_id'},exclure=['customer_lead'],default={'customer_lead':0})
cr_src.execute("select id,customer_lead from sale_order_line where coalesce(customer_lead,0)<>0")
execute_values(cr_dst,"update sale_order_line l set customer_lead=s.customer_lead from (values %s) as s(id, customer_lead) where s.id=l.id",
    [(r['id'],int(round(r['customer_lead']))) for r in cr_src.fetchall()])
# Prix technique (nouveau, prix unitaire avant modification manuelle) et entrepôt de la ligne (stocké en v20)
cr_dst.execute("update sale_order_line set technical_price_unit=price_unit where technical_price_unit is null")
cr_dst.execute("update sale_order_line l set warehouse_id=o.warehouse_id from sale_order o where o.id=l.order_id")
cnx_dst.commit()
MigrationDevisesParCode(db_src,db_dst,['sale_order','sale_order_line'])
# Incoterm des commandes (2, EXW) : ids différents en v20 => par le code
cr_src.execute("select s.id,i.code from sale_order s join account_incoterms i on i.id=s.incoterm")
for row in cr_src.fetchall():
    cr_dst.execute("update sale_order set incoterm=(select id from account_incoterms where code=%s) where id=%s",[row['code'],row['id']])
cnx_dst.commit()
#******************************************************************************


# ** Achats *******************************************************************
# Commandes (195) : notes => note ; pas d'état « done » en v16
MigrationTable(db_src,db_dst,'purchase_order',rename={'notes':'note'},default={'document_tax_mode':'tax_excluded','locked':False})
cr_dst.execute("update purchase_order set state='purchase', locked=true where state='done'")
cnx_dst.commit()
# Lignes (377) : product_uom => uom_id ; remise (nouvelle) à 0 ; prix technique = prix unitaire
MigrationTable(db_src,db_dst,'purchase_order_line',rename={'product_uom':'uom_id'},default={'discount':0})
SQL="""
    update purchase_order_line l set
        technical_price_unit   = l.price_unit,
        price_unit_product_uom = case when l.display_type is null then l.price_unit * pu.factor / lu.factor end,
        qty_to_invoice_raw     = l.product_qty - coalesce(l.qty_invoiced,0)
    from product_product p, product_template t, uom_uom pu, uom_uom lu
    where p.id=l.product_id and t.id=p.product_tmpl_id and pu.id=t.uom_id and lu.id=l.uom_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationTable(db_src,db_dst,'purchase_order_stock_picking_rel')
MigrationDevisesParCode(db_src,db_dst,['purchase_order','purchase_order_line'])
#******************************************************************************


# Les mises à jour qui suivent la copie se font sans contrôle des clés étrangères, comme la copie (MigrationTable) :
# PostgreSQL revérifie tous les liens d'une ligne modifiée deux fois dans la même transaction (ex : mouvement d'un OF
# pas encore copié) ; les liens orphelins sont contrôlés après le lancement
sans_controle = set()
def ControleCles(tables,actif):
    for table in tables:
        cr_dst.execute("alter table "+table+(" enable" if actif else " disable")+" trigger all")
        (sans_controle.discard if actif else sans_controle.add)(table)
    cnx_dst.commit()
@atexit.register
def RetablirControleCles():
    # Le script s'est arrêté (erreur) avant de réactiver les contrôles : réactivés avec une nouvelle connexion
    if sans_controle:
        cnx,cr = GetCR(db_dst)
        for table in sans_controle:
            cr.execute("alter table "+table+" enable trigger all")
        cnx.commit()
        print("Contrôles des clés étrangères réactivés : %s"%sorted(sans_controle))


# ** Fabrication **************************************************************
# Ordres de fabrication (287) : product_uom_id => uom_id ; date_planned_start / finished => date_start / date_finished
# (date_start obligatoire en v20) ; pas de lots ; procurement_group_id => production_group_id
# Champs d'is_dynamicmotion20 (is_date_planifiee, is_duree, is_date_livraison, is_sale_id) repris avec la table ;
# is_date_fin (calculé et stocké, nouveau) calculé plus bas
MigrationTable(db_src,db_dst,'mrp_production',rename={'product_uom_id':'uom_id'},default={'date_start':'1970-01-01'})
ControleCles(['mrp_production'],False)
cr_src.execute("select id, date_planned_start, date_planned_finished, date_start, date_finished, procurement_group_id from mrp_production")
productions = cr_src.fetchall()
cr_dst.execute("delete from mrp_production_stock_lot_rel; delete from mrp_production_group_rel; update mrp_production set production_group_id=null; delete from mrp_production_group;")
for p in productions:
    cr_dst.execute("update mrp_production set date_start=%s, date_finished=%s where id=%s",
        [p['date_start'] or p['date_planned_start'], p['date_finished'] or p['date_planned_finished'], p['id']])
# Groupe de production (reliquats d'un même OF) : un par groupe d'approvisionnement de la v16 (même id, même nom)
cr_src.execute("select distinct g.id, g.name, g.create_uid, g.create_date, g.write_uid, g.write_date from procurement_group g join mrp_production p on p.procurement_group_id=g.id")
for g in cr_src.fetchall():
    cr_dst.execute("insert into mrp_production_group (id,name,create_uid,create_date,write_uid,write_date) values (%s,%s,%s,%s,%s,%s)",
        [g['id'],g['name'],g['create_uid'],g['create_date'],g['write_uid'],g['write_date']])
for p in productions:
    if p['procurement_group_id']:
        cr_dst.execute("update mrp_production set production_group_id=%s where id=%s",[p['procurement_group_id'],p['id']])
# Date de fin planifiée du calendrier des OF (is_date_fin, is_dynamicmotion20) : même calcul que _compute_is_date_fin
cr_dst.execute("update mrp_production set is_date_fin = case when is_date_planifiee is not null then is_date_planifiee + coalesce(is_duree,0) * interval '1 hour' end")
cnx_dst.commit()
ControleCles(['mrp_production'],True)
SetSequence(cr_dst,cnx_dst,'mrp_production_group')

# Ordres de travail (838) : date_planned_start / finished => date_start / date_finished (dates réelles si commencé, sinon
# planifiées, comme les OF) ; product_id, product_uom_id : liés à l'OF en v20 ; dépendances entre ordres de travail (596)
MigrationTable(db_src,db_dst,'mrp_workorder')
ControleCles(['mrp_workorder'],False)
cr_src.execute("select id, date_planned_start, date_planned_finished, date_start, date_finished from mrp_workorder")
execute_values(cr_dst,"update mrp_workorder w set date_start=s.date_start, date_finished=s.date_finished from (values %s) as s(id, date_start, date_finished) where s.id=w.id",
    [(r['id'], r['date_start'] or r['date_planned_start'], r['date_finished'] or r['date_planned_finished']) for r in cr_src.fetchall()],
    template="(%s, %s::timestamp, %s::timestamp)")
cnx_dst.commit()
ControleCles(['mrp_workorder'],True)
MigrationTable(db_src,db_dst,'mrp_workorder_dependencies_rel')
# Blocages du planning des postes de travail par les ordres de travail (mrp_workorder.leave_id) : absences des
# ressources des postes (739 des 745 resource_calendar_leaves ; les 6 autres sont des congés d'employés, hors périmètre)
# holiday_id et time_type supprimés en v20
MigrationTable(db_src,db_dst,'resource_calendar_leaves',where="t.id in (select leave_id from mrp_workorder where leave_id is not null)")

# Suivi des temps des ordres de travail (3 436) : types de pertes identiques en v20 (mêmes ids et identifiants
# externes mrp.block_reason*) ; loss_type (lié au type de perte en v20) et cost_already_recorded non repris
MigrationTable(db_src,db_dst,'mrp_workcenter_productivity')
#******************************************************************************


# ** Démontages ***************************************************************
# Repris avant les mouvements : 23 mouvements de la v16 pointent vers un démontage (unbuild_id, consume_unbuild_id)
# 3 démontages ; product_uom_id => uom_id ; pas de lots
# Rebuts (stock_scrap, 2) : modèle supprimé en v20, le rebut est le mouvement lui-même (scrapped => is_scrap, repris
# avec les mouvements)
MigrationTable(db_src,db_dst,'mrp_unbuild',rename={'product_uom_id':'uom_id'})
#******************************************************************************


# ** Réparations (en-têtes) ***************************************************
# Reprises avant les mouvements : 47 mouvements de la v16 pointent vers une réparation (stock_move.repair_id)
# 26 réparations, toutes sur WH/Stock ; product_uom => uom_id
# Nouvelles colonnes obligatoires en v20 : type d'opération « Réparations » de l'entrepôt de l'emplacement de la v16 et
# emplacements de ce type (comme les calculs d'Odoo : location_dest_id, parts_location_id, recycle_location_id) ;
# produit réparé pris et remis sur l'emplacement de la v16 (product_location_src_id / dest_id)
# A reprendre avec la reprise 6 : pièces (repair_line, 24) et prestations (repair_fee, 23), description (23) et notes du
# devis (18) (champs supprimés en v20), garantie (guarantee_limit => under_warranty), facturation (invoice_id, 15)
# schedule_date : obligatoire en v20, vide sur 5 réparations => date de création (valeur par défaut d'Odoo : maintenant)
MigrationTable(db_src,db_dst,'repair_order',rename={'product_uom':'uom_id'},default={
    'schedule_date'           : '1970-01-01',
    'picking_type_id'         : 0,
    'location_dest_id'        : 0,
    'parts_location_id'       : 0,
    'recycle_location_id'     : 0,
    'product_location_src_id' : 0,
    'product_location_dest_id': 0,
})
ControleCles(['repair_order'],False)
SQL="""
    update repair_order r set
        picking_type_id          = t.id,
        product_location_src_id  = r.location_id,
        product_location_dest_id = r.location_id,
        location_dest_id         = t.default_location_dest_id,
        parts_location_id        = t.default_remove_location_dest_id,
        recycle_location_id      = t.default_recycle_location_dest_id
    from stock_picking_type t join stock_warehouse w on w.id=t.warehouse_id
    where t.code='repair_operation' and w.lot_stock_id=r.location_id
"""
cr_dst.execute(SQL)
cr_src.execute("select id,create_date from repair_order where schedule_date is null")
for row in cr_src.fetchall():
    cr_dst.execute("update repair_order set schedule_date=%s where id=%s",[row['create_date'],row['id']])
cr_dst.execute("select name from repair_order where picking_type_id=0")
sans_type = [row['name'] for row in cr_dst.fetchall()]
if sans_type:
    print("ATTENTION : réparations sans type d'opération (emplacement hors stock d'un entrepôt) : %s"%sans_type)
cnx_dst.commit()
ControleCles(['repair_order'],True)
#******************************************************************************


# ** Transferts et mouvements de stock ****************************************
# Transferts (749) : group_id => stock_reference (plus bas), date et immediate_transfer supprimés
MigrationTable(db_src,db_dst,'stock_picking')
# Retour de (return_id, nouveau en v20) : transfert d'origine des mouvements retournés
SQL_RETOUR="""
    update stock_picking p set return_id=r.picking_id
    from (
        select m.picking_id as id, min(om.picking_id) as picking_id
        from stock_move m join stock_move om on om.id=m.origin_returned_move_id
        where m.picking_id is not null and om.picking_id is not null group by m.picking_id
    ) r
    where r.id=p.id
"""

# Mouvements (4 345) : product_uom => uom_id ; quantity_done => quantity + picked (calculés plus bas avec les lignes) ;
# scrapped => is_scrap ; description_picking => description_picking_manual (libellé saisi, ex : ligne de commande)
# Non repris (supprimés en v20) : name, product_packaging_id, created_purchase_line_id, manual_consumption, package_level_id
MigrationTable(db_src,db_dst,'stock_move',rename={'product_uom':'uom_id','scrapped':'is_scrap','description_picking':'description_picking_manual'})

# Lignes de mouvement (3 835) : product_uom_id => uom_id ; qty_done (fait) et reserved_uom_qty (réservé) => quantity,
# picked si une quantité est faite (en v20, une seule quantité : réservée tant que picked est faux)
MigrationTable(db_src,db_dst,'stock_move_line',rename={'product_uom_id':'uom_id'})
ControleCles(['stock_picking','stock_move','stock_move_line'],False)
cr_dst.execute(SQL_RETOUR) # return_id des transferts (mouvements nécessaires)
cnx_dst.commit()
cr_src.execute("select id, qty_done, reserved_uom_qty from stock_move_line")
lignes = cr_src.fetchall()
execute_values(cr_dst,"""
    update stock_move_line l set
        quantity = case when s.qty_done<>0 then s.qty_done else s.reserved_uom_qty end,
        picked   = s.qty_done<>0
    from (values %s) as s(id, qty_done, reserved_uom_qty)
    where s.id=l.id
""",[(r['id'],r['qty_done'] or 0,r['reserved_uom_qty'] or 0) for r in lignes],page_size=5000)
cnx_dst.commit()
# Mouvements : quantité = quantité faite si le mouvement est fait, sinon somme de ses lignes (dans l'unité du mouvement)
cr_src.execute("select id, quantity_done from stock_move where state='done'")
execute_values(cr_dst,"""
    update stock_move m set quantity=s.quantity_done, picked=true
    from (values %s) as s(id, quantity_done) where s.id=m.id
""",[(r['id'],r['quantity_done'] or 0) for r in cr_src.fetchall()],page_size=5000)
SQL="""
    update stock_move m set
        quantity = coalesce((select sum(l.quantity * lu.factor / mu.factor)
                             from stock_move_line l join uom_uom lu on lu.id=l.uom_id where l.move_id=m.id),0),
        picked   = exists (select 1 from stock_move_line l where l.move_id=m.id and l.picked)
    from uom_uom mu
    where mu.id=m.uom_id and m.state<>'done'
"""
cr_dst.execute(SQL)
# Quantités dans l'unité de l'article (stockées en v20)
precision = "(select digits from decimal_precision where name='Product Unit')"
for table in ['stock_move','stock_move_line']:
    SQL="""
        update """+table+""" x set quantity_product_uom = round((x.quantity * xu.factor / pu.factor)::numeric, """+precision+""")
        from uom_uom xu, product_product p, product_template t, uom_uom pu
        where xu.id=x.uom_id and p.id=x.product_id and t.id=p.product_tmpl_id and pu.id=t.uom_id
    """
    cr_dst.execute(SQL)
cnx_dst.commit()
ControleCles(['stock_picking','stock_move','stock_move_line'],True)
MigrationTable(db_src,db_dst,'stock_move_move_rel')
MigrationTable(db_src,db_dst,'stock_move_line_consume_rel')
#******************************************************************************


# ** Valorisation des stocks **************************************************
# stock_valuation_layer (3 490 couches, supprimé en v20) => valeur du mouvement (stock_move.value) ; voir
# MigrationValorisationStock ; catégorie en coût standard, valorisation manuelle (périodique) en v16
MigrationValorisationStock(db_src,db_dst)
#******************************************************************************


# ** Groupes d'approvisionnement => références de stock ***********************
# procurement_group (807, supprimé en v20) => stock_reference (mêmes ids) et ses liens avec les mouvements, les
# commandes de vente et d'achat et les ordres de fabrication
MigrationTable(db_src,db_dst,'procurement_group','stock_reference')
cr_dst.execute("delete from stock_reference_move_rel; delete from stock_reference_sale_rel; delete from stock_reference_purchase_rel; delete from stock_reference_production_rel;")
liens = [
    ("stock_reference_move_rel",       "move_id",       "select id, group_id from stock_move where group_id is not null"),
    ("stock_reference_sale_rel",       "sale_id",       "select id, procurement_group_id from sale_order where procurement_group_id is not null union select sale_id, id from procurement_group where sale_id is not null"),
    ("stock_reference_purchase_rel",   "purchase_id",   "select id, group_id from purchase_order where group_id is not null"),
    ("stock_reference_production_rel", "production_id", "select id, procurement_group_id from mrp_production where procurement_group_id is not null"),
]
for table,colonne,SQL in liens:
    cr_src.execute(SQL)
    lignes = [tuple(row.values()) for row in cr_src.fetchall()]
    if lignes:
        execute_values(cr_dst,"insert into "+table+" ("+colonne+",reference_id) values %s on conflict do nothing",lignes,page_size=5000)
    print("%s : %s liens"%(table,len(lignes)))
cnx_dst.commit()
#******************************************************************************


# ** Séquences ****************************************************************
# Commandes de vente et d'achat (les OF et transferts ont la séquence de leur type d'opération, déjà recalée)
for code in ['sale.order','purchase.order']:
    cr_src.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_src = cr_src.fetchone()
    cr_dst.execute("select id from ir_sequence where code=%s order by id limit 1",[code])
    seq_dst = cr_dst.fetchone()
    if seq_src and seq_dst:
        MigrationIrSequence(db_src,db_dst,id_src=seq_src['id'],id_dst=seq_dst['id'])
    else:
        print("Séquence %s : absente (source %s, destination %s)"%(code,seq_src,seq_dst))
#******************************************************************************


# ** Paramètres comptables ****************************************************
# Comptabilité de la société 1 seulement (la société 2 n'en a pas) ; comptabilité et déclaration de TVA tenues hors
# d'Odoo chez Dynamic Motion => reprise au plus simple, à l'identique (décision du 16/10/2026)
# Plan comptable suisse (l10n_ch, 185 comptes), groupes de taxes (12), taxes (29), positions fiscales (2), journaux (8)
# de la v16 copiés avec leurs ids à la place de ceux créés par l10n_ch en v20 (ids différents) ; colonnes ajoutées par
# la v20 reprises de l'enregistrement v20 équivalent (même identifiant externe) ; références de la v20 recalées
# Taxes : copiées telles quelles, y compris les 2 taxes à 8,1 % créées à la main en v16 (sans identifiant externe, cases
# de TVA 302 pour la vente, sans compte ni case pour l'achat) ; taxes v20 à 2,6 %, 3,8 %, 8,1 % non reprises
# Voir Documentation/migration-odoo/migration-vers-odoo20.md § 3.7 et § 5.4

# Lignes v20 et correspondance par identifiant externe, avant la copie
avant, corr = {}, {}
for table,suffixes in [('account_account',[]),('account_tax_group',[]),('account_tax',[]),('account_fiscal_position',[])]:
    avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table,suffixes)
avant['account_journal'], _ = LireAvantCopie(db_src,db_dst,'account_journal')
# Journaux : pas d'identifiant externe en v16 => correspondance par code (FAC, OD, EXCH, CABA, BNK1, STJ), sinon par type
# s'il n'y en a qu'un (achats : FACTU en v16, FACTURE en v20)
cr_src.execute("select id,code,type from account_journal")
journaux_src = cr_src.fetchall()
corr['account_journal'] = {}
for j20 in avant['account_journal'].values():
    j16 = [j for j in journaux_src if j['code']==j20['code']] or [j for j in journaux_src if j['type']==j20['type']]
    if len(j16)==1 and j16[0]['id'] not in corr['account_journal']:
        corr['account_journal'][j16[0]['id']] = j20['id']
print("Journaux (id v16 : id v20) : %s"%corr['account_journal'])
inverse = {t:{id20:id_src for id_src,id20 in sorted(c.items(),reverse=True)} for t,c in corr.items()} # id v20 => id v16

# Tables de la v20 liées aux anciens comptes et taxes, sans équivalent repris
for table in [
    'account_tax_filiation_rel',                # taxes groupées
    'account_fiscal_position_account',          # correspondances de comptes
    'account_fiscal_position_account_tax_rel',  # recréées plus bas à partir de la v16
    'account_tax_alternatives',                 # recréées plus bas à partir de la v16
    'account_reconcile_model_line',             # modèles de rapprochement : ceux de la v16 (invoice_matching) n'existent
    'account_reconcile_model',                  # plus en v20, pas de relevés bancaires
]:
    cr_dst.execute("delete from "+table)
cnx_dst.commit()

# Comptes : nom traduisible, code => code_store (par société), deprecated => active, société => account_account_res_company_rel
MigrationTableJsonb(db_src,db_dst,'account_account')
# Colonnes ajoutées par la v20 (description, comptes de stock...) d'abord : code_store et active sont posés juste après
CompleterColonnesV20(db_src,db_dst,'account_account',avant['account_account'],corr['account_account'],inverse)
cr_src.execute("select id,code,deprecated,company_id from account_account")
comptes = cr_src.fetchall()
cr_dst.execute("delete from account_account_res_company_rel")
execute_values(cr_dst,"""
    update account_account a set code_store=jsonb_build_object('1',s.code), active=not s.deprecated
    from (values %s) as s(id,code,deprecated) where s.id=a.id
""",[(row['id'],row['code'],bool(row['deprecated'])) for row in comptes],page_size=5000)
execute_values(cr_dst,"insert into account_account_res_company_rel (account_account_id,res_company_id) values %s",
    [(row['id'],row['company_id'] or 1) for row in comptes])
cnx_dst.commit()
parent_store_compute(cr_dst,cnx_dst,'account_account','parent_id') # hiérarchie des comptes (parent_path avec les ids v16)
MigrationTable(db_src,db_dst,'account_account_tax_default_rel')

# Groupes de taxes (société obligatoire en v20) et taxes : price_include => price_include_override (vide = réglage de la société)
MigrationTableJsonb(db_src,db_dst,'account_tax_group',default={'company_id':1})
CompleterColonnesV20(db_src,db_dst,'account_tax_group',avant['account_tax_group'],corr['account_tax_group'],inverse)
MigrationTableJsonb(db_src,db_dst,'account_tax')
# Colonnes ajoutées par la v20 (codes Factur-X, mentions) d'abord : price_include_override posé juste après,
# is_domestic recalculé avec les positions fiscales
CompleterColonnesV20(db_src,db_dst,'account_tax',avant['account_tax'],corr['account_tax'],inverse)
cr_src.execute("select id from account_tax where price_include")
cr_dst.execute("update account_tax set price_include_override=case when id = any(%s) then 'tax_included' end",[[row['id'] for row in cr_src.fetchall()]])
cnx_dst.commit()
# Lignes de répartition : invoice_tax_id / refund_tax_id => tax_id + document_type
MigrationTable(db_src,db_dst,'account_tax_repartition_line',default={'document_type':'invoice'})
cr_src.execute("select id,invoice_tax_id,refund_tax_id from account_tax_repartition_line")
execute_values(cr_dst,"""
    update account_tax_repartition_line r set tax_id=s.tax_id, document_type=s.document_type
    from (values %s) as s(id,tax_id,document_type) where s.id=r.id
""",[(row['id'],row['invoice_tax_id'] or row['refund_tax_id'],'invoice' if row['invoice_tax_id'] else 'refund') for row in cr_src.fetchall()])
cnx_dst.commit()

# Positions fiscales (2 : intérieur, import/export) ; correspondances de taxes : en v20, portées par la taxe de remplacement
# Les commandes de vente (384) et d'achat (139) déjà reprises pointent sur ces ids
MigrationTableJsonb(db_src,db_dst,'account_fiscal_position')
CompleterColonnesV20(db_src,db_dst,'account_fiscal_position',avant['account_fiscal_position'],corr['account_fiscal_position'],inverse)
cr_src.execute("select position_id,tax_src_id,tax_dest_id from account_fiscal_position_tax where tax_dest_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("insert into account_fiscal_position_account_tax_rel (account_tax_id,account_fiscal_position_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['position_id']])
    cr_dst.execute("insert into account_tax_alternatives (dest_tax_id,src_tax_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['tax_src_id']])
cr_dst.execute("update account_tax t set is_domestic = not exists (select 1 from account_fiscal_position_account_tax_rel r where r.account_tax_id=t.id)")
cr_dst.execute("update account_fiscal_position set is_domestic=false")
cnx_dst.commit()

# Journaux (8, dont la caisse CSH1 absente de la v20) : alias de messagerie non repris ; modes de paiement des journaux
MigrationTableJsonb(db_src,db_dst,'account_journal',default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'})
cr_dst.execute("update account_journal set alias_id=null")
cnx_dst.commit()
CompleterColonnesV20(db_src,db_dst,'account_journal',avant['account_journal'],corr['account_journal'],inverse)
MigrationTable(db_src,db_dst,'account_payment_method_line')

# Étiquettes des comptes et des lignes de taxes (déclaration de TVA) : étiquettes de la v20, liens convertis par nom
MigrationEtiquettesTaxes(db_src,db_dst,[
    ('account_account_account_tag','account_account_id'),
    ('account_account_tag_account_tax_repartition_line_rel','account_tax_repartition_line_id'),
])

# Devises (ids différents entre v16 et v20)
MigrationDevisesParCode(db_src,db_dst,['account_account','account_journal'])

# Champs comptables de la société et valeurs par défaut (comptes clients / fournisseurs, comptes des catégories,
# journal de stock...) : valeur de la v16 (colonne de la société, propriété sans res_id), sinon valeur de la v20
# convertie par la correspondance (champs ajoutés en v20), sinon vidée
tables_compta = {'account_account','account_tax','account_journal','account_fiscal_position','account_tax_group'}
colonnes_src = GetTypesChamps(cr_src,'res_company')
cr_src.execute("select * from res_company where id=1")
societe_src = cr_src.fetchone()
cr_dst.execute("select * from res_company where id=1")
societe_dst = cr_dst.fetchone()
# Sans contrôle des clés pendant ces mises à jour : la société est modifiée plusieurs fois dans la même transaction et
# PostgreSQL revérifie alors toutes ses clés, y compris les colonnes pas encore recalées (comptes v20 supprimés)
ControleCles(['res_company'],False)
for colonne,ref in GetClesEtrangeres(cr_dst,'res_company').items():
    if ref in tables_compta:
        valeur = societe_src[colonne] if colonne in colonnes_src else inverse.get(ref,{}).get(societe_dst[colonne])
        cr_dst.execute("update res_company set "+colonne+"=%s where id=1",[valeur])
# Incoterm par défaut de la société (EXW) : ids différents en v20 => par le code
cr_src.execute("select i.code from res_company c join account_incoterms i on i.id=c.incoterm_id where c.id=1")
row = cr_src.fetchone()
if row:
    cr_dst.execute("update res_company set incoterm_id=(select id from account_incoterms where code=%s) where id=1",[row['code']])
cnx_dst.commit()
ControleCles(['res_company'],True)
SQL="""
    select d.id, f.model, f.name, f.relation, d.json_value
    from ir_default d join ir_model_fields f on f.id=d.field_id
    where f.relation in ('account.account','account.journal','account.tax','account.fiscal.position')
"""
cr_dst.execute(SQL)
for row in cr_dst.fetchall():
    cr_src.execute("""
        select p.value_reference from ir_property p join ir_model_fields f on f.id=p.fields_id
        where f.model=%s and f.name=%s and p.res_id is null and p.value_reference is not null and p.company_id is distinct from 2
    """,[row['model'],row['name']])
    prop = cr_src.fetchone()
    valeur = int(prop['value_reference'].split(',')[1]) if prop else inverse.get(row['relation'].replace('.','_'),{}).get(json.loads(row['json_value']))
    if valeur:
        cr_dst.execute("update ir_default set json_value=%s where id=%s",[json.dumps(valeur),row['id']])
    else:
        cr_dst.execute("delete from ir_default where id=%s",[row['id']])
cnx_dst.commit()

# Propriétés par enregistrement (ir_property en v16 => colonnes jsonb par société en v20)
# Comptes d'entrée et de sortie de stock des catégories (3) : supprimés en v20 (valorisation périodique), non repris
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_position_id',where="p.company_id=1")      # 2 partenaires
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_income_id',where="p.company_id=1")   # 1 article
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_expense_id',where="p.company_id=1")  # 1 article
MigrationIrPropertyJsonb(db_src,db_dst,'product.category','property_stock_valuation_account_id',where="p.company_id=1") # 3 catégories

# Taxes des articles, des lignes de commande de vente et d'achat (ids des taxes de la v16)
for table in ['product_taxes_rel','product_supplier_taxes_rel','account_tax_sale_order_line_rel','account_tax_purchase_order_line_rel']:
    MigrationTable(db_src,db_dst,table)

# Identifiants externes des modèles repris (journaux : par la correspondance par code, sans identifiant en v16)
MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'])
cr_dst.execute("select id,res_id from ir_model_data where model='account.journal'")
for row in cr_dst.fetchall():
    id16 = inverse['account_journal'].get(row['res_id'])
    if id16:
        cr_dst.execute("update ir_model_data set res_id=%s where id=%s",[id16,row['id']])
    else:
        cr_dst.execute("delete from ir_model_data where id=%s",[row['id']])
cr_dst.execute("delete from ir_model_data where model in ('account.reconcile.model','account.reconcile.model.line')")
cnx_dst.commit()
#******************************************************************************


# ** Pièces comptables ********************************************************
# 954 pièces (412 factures, 5 avoirs, 106 factures fournisseurs, 1 avoir fournisseur, 428 autres pièces, dont les
# paiements), 3 057 lignes ; 86 pièces en EUR ou USD ; aucune pièce « à vérifier »
# to_check => review_state ; payment_id => origin_payment_id (après la copie des paiements) ; document_tax_mode :
# obligatoire pour les factures et avoirs, vide pour les autres pièces (comme _compute_document_tax_mode)
MigrationTable(db_src,db_dst,'account_move',default={'review_state':'no_review','document_tax_mode':'tax_excluded'})
# Montant hors taxe dans la devise de la pièce (signé) et taux de la pièce (devise de la pièce par unité de devise de la
# société), stockés en v20 : calculés à partir des montants de la pièce (1 si la pièce est dans la devise de la société)
SQL="""
    update account_move set
        amount_untaxed_in_currency_signed = case when amount_untaxed_signed<0 then -amount_untaxed else amount_untaxed end,
        invoice_currency_rate = case when amount_total_signed<>0 then abs(amount_total/amount_total_signed) else 1 end,
        document_tax_mode = case when move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt')
                                 then (select account_price_include from res_company c where c.id=account_move.company_id) end
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Lignes : display_type déjà renseigné en v16 ; invoice_date stockée sur la ligne en v20
MigrationTable(db_src,db_dst,'account_move_line')
cr_dst.execute("update account_move_line l set invoice_date=m.invoice_date from account_move m where m.id=l.move_id")
cnx_dst.commit()
MigrationTable(db_src,db_dst,'account_move_line_account_tax_rel')
MigrationEtiquettesTaxes(db_src,db_dst,[('account_account_tag_account_move_line_rel','account_move_line_id')])

# Lettrages (414 complets, 417 partiels)
MigrationTable(db_src,db_dst,'account_full_reconcile')
MigrationTable(db_src,db_dst,'account_partial_reconcile')

# Paiements (427) : nom, date, journal, société et mémo portés par la pièce en v16 ; état : draft / canceled selon la
# pièce, sinon comme Odoo 20 (_compute_state) : reconciled si les lignes de liquidité sont soldées, sinon paid
MigrationTable(db_src,db_dst,'account_payment',default={'company_id':1,'date':'2000-01-01','journal_id':1,'state':'draft'})
SQL="""
    update account_payment p set
        name       = m.name,
        date       = m.date,
        journal_id = m.journal_id,
        company_id = m.company_id,
        memo       = m.ref,
        currency_id = m.currency_id,
        commercial_partner_id = (select commercial_partner_id from res_partner r where r.id=p.partner_id),
        amount_company_currency_signed = case when p.payment_type='outbound' then -m.amount_total_signed else m.amount_total_signed end,
        is_sent    = false,
        state = case
            when m.state='draft'  then 'draft'
            when m.state='cancel' then 'canceled'
            when coalesce((
                select sum(l.amount_residual) from account_move_line l join account_journal j on j.id=m.journal_id
                where l.move_id=m.id and l.account_id=coalesce(p.outstanding_account_id,j.default_account_id)
            ),0)=0 then 'reconciled'
            else 'paid'
        end
    from account_move m
    where m.id=p.move_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Pièce de chaque paiement : payment_id de la pièce en v16 => origin_payment_id
cr_src.execute("select id,payment_id from account_move where payment_id is not null")
execute_values(cr_dst,"update account_move m set origin_payment_id=s.payment_id from (values %s) as s(id,payment_id) where s.id=m.id",
    [(row['id'],row['payment_id']) for row in cr_src.fetchall()])
cnx_dst.commit()

# Factures réglées par chaque paiement (invoice_ids du paiement) : d'après les lettrages de la v16
cr_dst.execute("delete from account_move__account_payment")
SQL="""
    select distinct l_facture.move_id invoice_id, m.payment_id
    from account_partial_reconcile r
    join account_move_line ld on ld.id=r.debit_move_id
    join account_move_line lc on lc.id=r.credit_move_id
    join account_move m on m.id in (ld.move_id,lc.move_id) and m.payment_id is not null
    join account_move_line l_facture on l_facture.id in (ld.id,lc.id) and l_facture.move_id<>m.id
    join account_move f on f.id=l_facture.move_id and f.move_type<>'entry'
"""
cr_src.execute(SQL)
lignes = [(row['invoice_id'],row['payment_id']) for row in cr_src.fetchall()]
if lignes:
    execute_values(cr_dst,"insert into account_move__account_payment (invoice_id,payment_id) values %s on conflict do nothing",lignes)
cnx_dst.commit()

# Paiements « paid » => « reconciled » comme Odoo 20 (_compute_state) quand le compte d'attente n'est pas un compte de
# trésorerie et que toutes les factures réglées par le paiement sont payées
SQL="""
    update account_payment p set state='reconciled'
    from account_journal j
    where j.id=p.journal_id and p.state='paid'
    and (select account_type from account_account a where a.id=coalesce(p.outstanding_account_id,j.default_account_id))<>'asset_cash'
    and exists (select 1 from account_move__account_payment r where r.payment_id=p.id)
    and not exists (select 1 from account_move__account_payment r join account_move f on f.id=r.invoice_id
                    where r.payment_id=p.id and f.payment_state<>'paid')
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Pièce jointe principale des pièces : vidée tant que les pièces jointes ne sont pas reprises (elle pointerait sur une
# pièce jointe absente ou sur une autre pièce jointe de la v20) => à remettre avec les pièces jointes (reprise 7)
cr_dst.execute("update account_move set message_main_attachment_id=null")
cnx_dst.commit()

# Incoterm des factures (15, EXW) : ids différents en v20 => par le code
cr_src.execute("select m.id,i.code from account_move m join account_incoterms i on i.id=m.invoice_incoterm_id")
for row in cr_src.fetchall():
    cr_dst.execute("update account_move set invoice_incoterm_id=(select id from account_incoterms where code=%s) where id=%s",[row['code'],row['id']])
cnx_dst.commit()

# Liens avec les commandes : lignes de commande de vente => lignes de factures, commandes d'achat => factures
MigrationTable(db_src,db_dst,'sale_order_line_invoice_rel')
MigrationTable(db_src,db_dst,'account_move_purchase_order_rel')

# Devises (ids différents entre v16 et v20)
MigrationDevisesParCode(db_src,db_dst,['account_move','account_move_line','account_payment','account_partial_reconcile','account_full_reconcile'])
#******************************************************************************


# ** Reprise 6 : CRM, projets, contenu des réparations (voir Reprise6) *********
Reprise6()
#******************************************************************************


# Contrôle final (lecture seule) : clés étrangères qui ne pointent sur rien
ControleOrphelins(db_dst)
