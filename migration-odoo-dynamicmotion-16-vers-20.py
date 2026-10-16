#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Dynamic Motion : Odoo 16 (is_dynamicmotion) => Odoo 20 (is_dynamicmotion20)
# Documentation : Documentation/migration-odoo/migration-is_dynamicmotion16-vers-is_dynamicmotion20.md
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


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
