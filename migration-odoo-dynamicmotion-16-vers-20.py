#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Dynamic Motion : Odoo 16 (is_dynamicmotion) => Odoo 20 (is_dynamicmotion20)
# Documentation : Documentation/migration-odoo/migration-is_dynamicmotion16-vers-is_dynamicmotion20.md
from migration_fonction import *
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
# Absences (resource_calendar_leaves, 745, toutes rattachées à une ressource) : congés des employés, hors périmètre
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
# Instructions des opérations (note, 28 opérations) : champ supprimé en v20, non repris (à décider)
MigrationTable(db_src,db_dst,'mrp_routing_workcenter',where=where_bom_id,default={'cost_mode':'actual'})
#******************************************************************************
