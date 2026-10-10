#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de Jurabotec : Odoo 16 (is_jurabotec) => Odoo 20 (is_jurabotec20)
# Documentation : Documentation/migration-odoo/migration-is_jurabotec16-vers-is_jurabotec20.md
from migration_fonction import *


#** Paramètres ****************************************************************
db_src = "jurabotec16"
db_dst = "jurabotec20"
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** res_partner et res_users *************************************************
# Copiés avec les ids de la source (6 064 partenaires, 27 utilisateurs dans jurabotec16)
# mobile (2 336 partenaires) et title (civilité, 20 partenaires) : supprimés d'Odoo en v20, remis par is_jurabotec20
# (civilité : res.partner.title => is.civilite, title => is_civilite)
# company_registry (2 partenaires, dont la société : « R.C.S. 810 944 835 ») : supprimé en v20, non repris
# Nouvelles colonnes en v20 : valeurs par défaut d'Odoo (autopost_bills, group_rfq et group_on sont obligatoires)
# Propriétés comptables (comptes, conditions de paiement, positions fiscales) : à reprendre avec la comptabilité
MigrationTable(db_src,db_dst,'res_partner_title','is_civilite')
# is_emplacement_charge_id (3 partenaires, WH/JURAWOOD) : emplacements pas encore repris (ids différents en v20),
# sinon « Enregistrement inexistant ou supprimé (stock.location(56,)) » sur la fiche => à reprendre avec le stock
MigrationTable(db_src,db_dst,'res_partner',rename={'title':'is_civilite'},exclure=['is_emplacement_charge_id'],default={
    'autopost_bills'  : 'ask',
    'group_rfq'       : 'default',
    'group_on'        : 'default',
    'suggest_based_on': '30_days',
    'suggest_days'    : 7,
    'suggest_percent' : 100,
})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# Dernière connexion de chaque utilisateur (une ligne par utilisateur, Odoo ne garde que la dernière) :
# sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé » (calculé d'après login_date)
MigrationTable(db_src,db_dst,'res_users_log')

# Type d'adresse « private » (adresse privée d'employé) supprimé en v17 => contact (1 partenaire)
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

# SIRET : colonne siret en v16 => identifiant FR_SIRET de additional_identifiers en v20 (47 partenaires, dont la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Étiquettes des partenaires (distribution, menuiserie, SETT)
MigrationTable(db_src,db_dst,'res_partner_category')
MigrationTable(db_src,db_dst,'res_partner_res_partner_category_rel')

# Groupes : correspondance par nom d'identifiant externe
# Les groupes des modules absents en v20 (hr, project, is_vllm2odoo) sont ignorés
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20 (3 et 4 au lieu de 4 et 5)
# => les identifiants externes base pointent sur les ids de la source et l'ancien default (id 3) perd ses groupes
MigrationUtilisateursTechniques(db_src,db_dst)
#******************************************************************************


# ** res_company **************************************************************
# Champs simples (nom, e-mail, téléphone, APE...) ; devise retrouvée par son code (EUR)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Vérification des TVA par VIES (activée en v16) : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont
# un n° de TVA (531, un appel à VIES toutes les 3 secondes, une seule transaction qui bloque les partenaires)
# => à réactiver après la bascule (Paramètres / Comptabilité) : les partenaires seront vérifiés au fil des modifications
cr_dst.execute("update res_company set vat_check_vies=false")
cnx_dst.commit()

# Adresse de la société dans les en-têtes, slogan (texte en v16, traduisible en v20) et pied de page (déjà traduisible)
cr_src.execute("select id,company_details,report_header,report_footer from res_company")
for row in cr_src.fetchall():
    for champ in ('company_details','report_header'):
        if row[champ]:
            cr_dst.execute("update res_company set "+champ+"=jsonb_build_object('en_US',%s::text,'fr_FR',%s::text) where id=%s",[row[champ],row[champ],row['id']])
    if row['report_footer']:
        cr_dst.execute("update res_company set report_footer=%s where id=%s",[json.dumps(row['report_footer']),row['id']])
cnx_dst.commit()

# Compte bancaire de la société (IBAN de la facture) : res.bank supprimé en v20 => nom et BIC de la banque sur le compte
# clearing_label_id : nouvelle colonne obligatoire en v20 => libellé par défaut (base.clearing_label_all, aucun libellé pour la France)
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


# ** Tables de paramétrage is_* ***********************************************
# Colonnes identiques en v16 et en v20, pas de lien vers les tables standard (sauf create_uid / write_uid)
tables=[
    "is_bareme_valobat",        #   4 lignes
    "is_bois",                  #  23 lignes
    "is_calculateur_operation", #  15 lignes
    "is_qualite_bois",          # 404 lignes
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Unités de mesure *********************************************************
# Copiées avec les ids de la v16 (34 unités) : les tables qui les utilisent se copient ensuite sans conversion
# Chaque unité est rattachée à la référence de son ancienne catégorie (mlinéaire => 1 m, Boite (1600) => 1600 Unités...)
# Identifiants externes uom.* repointés ; Pack de 6, Minutes, ml et KWH (absents de la v16) recréés en 35 à 38 ;
# barcode_rule.associated_uom_id converti (voir MigrationUnites)
# Attention : l'unité « mètre » de la v16 est le yard (uom.product_uom_yard, 21 articles), gardée telle quelle (à décider)
MigrationUnites(db_src,db_dst)
#******************************************************************************


# ** Articles *****************************************************************
# Catégories (67) : nom texte en v16, traduisible en v20 ; comptes des catégories : à reprendre avec la comptabilité
MigrationTableJsonb(db_src,db_dst,'product_category')
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

# Étiquettes (25) : couleur entière en v16, code hexadécimal en v20 => non reprise
MigrationTable(db_src,db_dst,'product_tag',exclure=['color'])
MigrationTable(db_src,db_dst,'product_tag_product_template_rel')

# Attributs (Longueur, Traitement, Dimension) et valeurs (229) ; les 5 attributs d'exemple de la v20 sont remplacés
MigrationTable(db_src,db_dst,'product_attribute',default={'active':True})
MigrationTable(db_src,db_dst,'product_attribute_value',default={'active':True})

# Modèles d'articles (4 379)
# sale_delay : nombre en v16, jsonb en v20, toujours à 0 => non repris ; expense_policy => reinvoice_policy (tous à « no »)
# Nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count (valeurs par défaut d'Odoo)
MigrationTable(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},exclure=['sale_delay'],
    default={'service_tracking':'no','base_unit_count':0})
# Type « Article stockable » (product) supprimé en v18 => consommable (consu) avec la case « Suivre l'inventaire » (is_storable)
cr_dst.execute("update product_template set is_storable=(type='product'), type=case when type='product' then 'consu' else type end")
# Suivi « none » supprimé en v20 (seulement lot et serial) => vide ; sinon « Wrong value for product.template.store_by: 'none' »
cr_dst.execute("update product_template set tracking=null where tracking='none'")
# Favoris : priority='1' en v16 => is_favorite en v20 (469 articles)
cr_src.execute("select id from product_template where priority='1'")
ids = [row['id'] for row in cr_src.fetchall()]
cr_dst.execute("update product_template set is_favorite=(id = any(%s))",[ids])
cnx_dst.commit()

# Variantes (10 000)
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
cr_dst.execute("update product_product p set is_favorite=t.is_favorite from product_template t where t.id=p.product_tmpl_id")
cnx_dst.commit()

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

# Coût des variantes (1 754 valeurs) et responsable des articles : propriétés en v16, champs jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')
MigrationIrPropertyJsonb(db_src,db_dst,'product.template','responsible_id')

# Listes de prix (12) et lignes : toutes à prix fixe ; discount_policy supprimé en v20
# Lignes archivées (248) non reprises : plus d'archivage des lignes en v20, elles redeviendraient actives
MigrationTable(db_src,db_dst,'product_pricelist')
MigrationTable(db_src,db_dst,'product_pricelist_item',where="t.active")
# Liste de prix des clients (5 872 partenaires) : propriété en v16, champ jsonb par société en v20
MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_product_pricelist','specific_property_product_pricelist')

# Prix fournisseurs (745) : unité d'achat de l'article (uom_po_id, supprimé en v20) => unité du prix fournisseur (obligatoire)
MigrationTable(db_src,db_dst,'product_supplierinfo',default={'uom_id':1,'discount':0})
cr_src.execute("select s.id,t.uom_po_id from product_supplierinfo s join product_template t on t.id=s.product_tmpl_id")
for row in cr_src.fetchall():
    cr_dst.execute("update product_supplierinfo set uom_id=%s where id=%s",[row['uom_po_id'],row['id']])
cnx_dst.commit()

# Nomenclatures (429, dont 333 de type « Commande client » d'is_jurabotec20) : product_uom_id => uom_id
# Non repris (supprimés en v20) : consumption (toutes à « warning »), manual_consumption (33 lignes)
MigrationTable(db_src,db_dst,'mrp_bom',rename={'product_uom_id':'uom_id'})
MigrationTable(db_src,db_dst,'mrp_bom_line',rename={'product_uom_id':'uom_id'})
MigrationTable(db_src,db_dst,'mrp_bom_byproduct',rename={'product_uom_id':'uom_id'})

# Tables is_* liées aux articles
for table in [
    'is_product_template_calculateur_operation',
    'is_qualite_bois_product_template_rel',
    'is_contrat_fournisseur',
    'is_contrat_fournisseur_ligne',
]:
    MigrationTable(db_src,db_dst,table)

# Ids des devises : ids de la v16 => ids de la v20 (EUR = 1 en v16, 126 en v20)
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
# A reprendre avec les pièces jointes : images, plans (product_template_is_plan_rel), FDS (product_template_is_fds_rel)
#******************************************************************************


# ** Configuration du stock ***************************************************
# Entrepôt, emplacements (60), types d'opérations (9), routes (7), règles (10) copiés avec les ids de la v16 (ids
# différents en v20 : WH/Stock = 8 en v16, 6 en v20) ; correspondance par rôle avec ceux créés par la v20 pour recaler
# ses références (société, emplacements par défaut, identifiants externes) ; types Contrôle qualité, Stockage et
# Correspondance de la v20 recréés (utilisés par l'entrepôt v20) ; séquences des types recalées sur la v16 (RCP, BL...)
# Emplacements vues Physical Locations, Partners, Virtual Locations (supprimés en v18) retirés
MigrationConfigurationStock(db_src,db_dst,correspondances_xmlids={'stock_location_inter_company':'stock_location_inter_wh'})
MigrationTable(db_src,db_dst,'stock_route_warehouse')
MigrationTable(db_src,db_dst,'stock_route_product')                               # routes des articles (4 428)
MigrationTable(db_src,db_dst,'stock_putaway_rule',default={'sublocation':'no'})   # règles de rangement (10)

# Emplacement des charges des partenaires (3, WH/JURAWOOD) : non repris avec les partenaires (emplacements pas encore là)
cr_src.execute("select id,is_emplacement_charge_id from res_partner where is_emplacement_charge_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set is_emplacement_charge_id=%s where id=%s",[row['is_emplacement_charge_id'],row['id']])
cnx_dst.commit()
#******************************************************************************


# ** Lots et stock ************************************************************
# Lots (5 714) : product_uom_id supprimé en v20
MigrationTable(db_src,db_dst,'stock_lot')
# Quants (16 597, dont 80 avec une quantité réservée : à vérifier avec la reprise des mouvements)
MigrationTable(db_src,db_dst,'stock_quant')
# Emplacement du lot (nouveau en v20, stocké) : l'emplacement de ses quantités positives s'il n'y en a qu'un (calcul d'Odoo)
SQL="""
    update stock_lot l set location_id=q.location_id
    from (
        select lot_id, min(location_id) as location_id from stock_quant
        where quantity>0 and lot_id is not null group by lot_id having count(distinct location_id)=1
    ) q
    where q.lot_id=l.id
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Règles de réapprovisionnement (370) : qty_to_order => qty_to_order_manual ; nouvelles colonnes obligatoires en v20 :
# valeurs par défaut d'Odoo ; vendor_id supprimé (même fournisseur que supplier_id)
# Non repris : qty_multiple (« Multiple » : unité en v20) : 2 règles à revoir (ROULEAU 330 POINTES par 20, EPICEA DU NORD 25*75 par 2)
MigrationTable(db_src,db_dst,'stock_warehouse_orderpoint',rename={'qty_to_order':'qty_to_order_manual'},default={
    'min_max_based_on'       : 'one_month',
    'min_max_based_on_factor': 100,
    'daily_demand'           : 0,
})

# Inventaires (module is_jurabotec20) et tables is_* du stock (charges, scans)
for table in [
    'is_inventaire',
    'stock_inventory',
    'stock_inventory_line',
    'is_creation_charge',
    'is_deplacement_charge',
    'is_scan_inventaire',
    'is_scan_inventaire_ligne',
    'is_scan_inventaire_ligne_stock_location_rel',
    'is_scan_deplacement_charge',
]:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** Thème de l'entreprise (is_theme_entreprise) ******************************
# Couleurs choisies dans jurabotec20 le 10/10/2026 (pas de thème en v16)
SQL="""
    update res_company set is_theme_couleur='#007859', is_theme_eclaircissement=80;
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************
