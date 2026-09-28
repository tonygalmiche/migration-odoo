#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de France Filets : Odoo 15 (is_france_filets15) => Odoo 20 (is_france_filets20)
# Documentation : Documentation/migration-odoo/migration-is_france_filets15-vers-is_france_filets20.md (étape 9)
from migration_fonction import *
import os


#** Paramètres ****************************************************************
db_src = "france-filets15"
db_dst = "france-filets20"
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# france-filets20-vierge : base v20 avec is_france_filets20 installé, sans données (à créer par Tony)
# db_vierge = db_dst+'-vierge'
# SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
# cde="""echo '"""+SQL+"""' | psql postgres"""
# lines=os.popen(cde).readlines()
#******************************************************************************

cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)


# ** 9.b Contacts, utilisateurs, société **************************************
# Civilités (supprimées d'Odoo en v20, recréées par is_france_filets20) : libellés français pris dans ir_translation
MigrationTable(db_src,db_dst,'res_partner_title')
cr_src.execute("select id from res_partner_title")
for row in cr_src.fetchall():
    for champ in ('name','shortcut'):
        fr = GetTraduction(cr_src,'res.partner.title',champ,row['id'])
        if fr:
            cr_dst.execute("update res_partner_title set "+champ+"=%s where id=%s",[fr,row['id']])
cnx_dst.commit()

# Tables de référence des partenaires (régions, secteurs d'activité, origines, groupes clients) : à reprendre
# avant eux, sinon Odoo refuse d'afficher les listes de partenaires (lien vers un enregistrement inexistant)
for table in ['is_region','is_secteur_activite','is_origine','is_groupe_client']:
    MigrationTable(db_src,db_dst,table)

# Partenaires (3 127), avec les ids de la source : is_company (case « Société »), mobile et title repris tels quels
# credit_limit : nombre en v15, jsonb (par société) en v20, toujours à 0 => non repris
# autopost_bills : nouvelle colonne obligatoire en v20 (valeur par défaut d'Odoo)
MigrationTable(db_src,db_dst,'res_partner',exclure=['credit_limit'],default={'autopost_bills':'ask'})
MigrationTable(db_src,db_dst,'res_users')
MigrationTable(db_src,db_dst,'res_company_users_rel')

# Type d'adresse « private » (adresse privée d'employé) supprimé en v17 => contact
cr_dst.execute("update res_partner set type='contact' where type='private'")
cnx_dst.commit()

# commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
cnx_dst.commit()

# complete_name n'existe pas en v15 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

# SIRET : colonne siret en v15 => identifiant FR_SIRET de additional_identifiers en v20 (1 partenaire : la société)
cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
for row in cr_src.fetchall():
    cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
cnx_dst.commit()

# Groupes : correspondance par nom d'identifiant externe (is_france_filets15.xxx => is_france_filets20.xxx)
MigrationResGroups(db_src,db_dst)

# base.default_user supprimé en v19 : utilisateurs techniques décalés (anomalie 15 : l'ancien default perd ses droits)
MigrationUtilisateursTechniques(db_src,db_dst)

# Société : champs simples (nom, e-mail, téléphone, SMS, affacturage, conditions générales, APE, registre du commerce...)
# Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents : non repris ici
cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
exclure = [row['column_name'] for row in cr_dst.fetchall()]
MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

# Agencement des documents « Light » (web.external_layout_standard) : sinon l'en-tête France Filets ne s'applique pas
SQL="""
    update res_company set external_report_layout_id=(
        select res_id from ir_model_data where module='web' and name='external_layout_standard'
    )
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Anomalie 14 : inscription libre au portail fermée (b2c en v15)
SQL="""
    insert into ir_config_parameter (key,value) values ('auth_signup.invitation_scope','b2b')
    on conflict (key) do update set value='b2b'
"""
cr_dst.execute(SQL)
cnx_dst.commit()
#******************************************************************************


# ** 9.c Employés *************************************************************
# 15 employés, 2 départements : employés, départements, postes, catégories et une hr_version par employé
# Les liens avec les chantiers et le planning (hr_employee_is_chantier_rel...) sont repris avec les tables is_* (9.f)
MigrationHrEmployee(db_src,db_dst)
#******************************************************************************


# ** 9.d Paramètres comptables ************************************************
# Plan comptable, taxes, journaux, conditions de paiement et positions fiscales de la v15 repris à l'identique
# (mêmes ids) à la place de ceux créés par l10n_fr en v20. Seuls les types de comptes et les identifiants externes
# sont corrigés ; la facturation électronique sera préparée après la migration (doc générale § 8 et § 5.4)

# Tables de la v20 liées aux anciens comptes et taxes, sans équivalent repris (vides ou non utilisées en v15)
for table in [
    'account_account_account_tag',                          # étiquettes des comptes (rapports de flux)
    'account_account_tag_account_tax_repartition_line_rel', # étiquettes de la déclaration de TVA (aucune en v15)
    'account_account_tax_default_rel',                      # taxes par défaut des comptes (aucune en v15)
    'account_tax_filiation_rel',                            # taxes groupées (aucune en v15)
    'account_fiscal_position_account',                      # correspondances de comptes (aucune en v15)
    'account_fiscal_position_account_tax_rel',              # recréées plus bas à partir de la v15
    'account_tax_alternatives',                             # recréées plus bas à partir de la v15
    'account_reconcile_model_line',                         # modèles de rapprochement : pas de relevés bancaires
    'account_reconcile_model',
]:
    cr_dst.execute("delete from "+table)
cnx_dst.commit()

# Comptes (775) : code => code_store (par société), deprecated => active, type recalculé d'après le code
# (en v15, 290 comptes des classes 1 à 5, jamais utilisés, sont « hors bilan »)
MigrationTable(db_src,db_dst,'account_account',text2jsonb=True,default={'account_type':'income'})
cr_src.execute("select id,code,deprecated from account_account")
comptes = cr_src.fetchall()
modeles = [
    '/opt/odoo20/addons/l10n_fr_account/data/template/account.account-fr.csv',
    '/opt/odoo20/addons/l10n_fr_account/data/template/account.account-fr_comp.csv',
]
types = AccountTypeParCode([row['code'] for row in comptes],modeles)
cr_dst.execute("delete from account_account_res_company_rel")
for row in comptes:
    SQL="update account_account set code_store=jsonb_build_object('1',%s::text), active=%s, account_type=%s where id=%s"
    cr_dst.execute(SQL,[row['code'],not row['deprecated'],types[row['code']],row['id']])
    cr_dst.execute("insert into account_account_res_company_rel (account_account_id,res_company_id) values (%s,1)",[row['id']])
cnx_dst.commit()

# Groupes de taxes et taxes (15) ; lignes de répartition : invoice_tax_id / refund_tax_id => tax_id + document_type
MigrationTable(db_src,db_dst,'account_tax_group',text2jsonb=True,default={'company_id':1})
MigrationTable(db_src,db_dst,'account_tax',text2jsonb=True)
MigrationTable(db_src,db_dst,'account_tax_repartition_line',default={'document_type':'invoice'})
cr_src.execute("select id,invoice_tax_id,refund_tax_id from account_tax_repartition_line")
for row in cr_src.fetchall():
    if row['invoice_tax_id']:
        tax_id,document_type = row['invoice_tax_id'],'invoice'
    else:
        tax_id,document_type = row['refund_tax_id'],'refund'
    cr_dst.execute("update account_tax_repartition_line set tax_id=%s, document_type=%s where id=%s",[tax_id,document_type,row['id']])
cnx_dst.commit()

# Positions fiscales (3) ; correspondances de taxes (16) : en v20, portées par la taxe de remplacement
# (fiscal_position_ids : positions où elle s'applique, original_tax_ids : taxes qu'elle remplace)
MigrationTable(db_src,db_dst,'account_fiscal_position',text2jsonb=True,default={'company_id':1})
cr_src.execute("select position_id,tax_src_id,tax_dest_id from account_fiscal_position_tax where tax_dest_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("insert into account_fiscal_position_account_tax_rel (account_tax_id,account_fiscal_position_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['position_id']])
    cr_dst.execute("insert into account_tax_alternatives (dest_tax_id,src_tax_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['tax_src_id']])
cr_dst.execute("update account_tax t set is_domestic = not exists (select 1 from account_fiscal_position_account_tax_rel r where r.account_tax_id=t.id)")
cr_dst.execute("update account_fiscal_position set is_domestic=false")
cnx_dst.commit()

# Journaux (7) et modes de paiement des journaux
MigrationTable(db_src,db_dst,'account_journal',text2jsonb=True,default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'})
cr_dst.execute("update account_journal set alias_id=null") # alias de messagerie non repris
cnx_dst.commit()
MigrationTable(db_src,db_dst,'account_payment_method_line')

# Devises : EUR = 1 en v15, 126 en v20 (1 = USD en v20) => conversion par le code
MigrationDevisesParCode(db_src,db_dst,['account_account','account_journal'])

# Conditions de paiement (13) : toutes les lignes v15 sont des soldes => 100 %
# day_after_invoice_date => days_after (+ jour du mois => days_end_of_month_on_the), after_invoice_month => days_after_end_of_month
MigrationTable(db_src,db_dst,'account_payment_term',text2jsonb=True)
MigrationTable(db_src,db_dst,'account_payment_term_line',rename={'days':'nb_days'},default={'delay_type':'days_after'})
cr_src.execute("select id,value,value_amount,option,day_of_the_month from account_payment_term_line")
for row in cr_src.fetchall():
    delay_type,days_next_month = 'days_after',None
    if row['option']=='after_invoice_month':
        delay_type = 'days_after_end_of_month'
    elif row['day_of_the_month']:
        delay_type,days_next_month = 'days_end_of_month_on_the',str(row['day_of_the_month'])
    value,value_amount = ('percent',100) if row['value']=='balance' else (row['value'],row['value_amount'])
    SQL="update account_payment_term_line set delay_type=%s, days_next_month=%s, value=%s, value_amount=%s where id=%s"
    cr_dst.execute(SQL,[delay_type,days_next_month,value,value_amount,row['id']])
cnx_dst.commit()

# Champs comptables de la société (comptes, journaux, taxes, positions fiscales) : valeur de la v15 si le champ
# existait, sinon vidé (il pointait sur les ids de la v20)
SQL="""
    select a.attname as colonne
    from pg_constraint c join pg_class t on t.oid=c.conrelid join pg_class cf on cf.oid=c.confrelid
    join pg_attribute a on a.attrelid=c.conrelid and a.attnum=c.conkey[1]
    where c.contype='f' and t.relname='res_company'
    and cf.relname in ('account_account','account_journal','account_tax','account_fiscal_position','account_payment_term')
"""
cr_dst.execute(SQL)
colonnes_src = GetTypesChamps(cr_src,'res_company')
for row in cr_dst.fetchall():
    colonne = row['colonne']
    valeur = None
    if colonne in colonnes_src:
        cr_src.execute("select "+colonne+" from res_company where id=1")
        valeur = cr_src.fetchone()[colonne]
    cr_dst.execute("update res_company set "+colonne+"=%s where id=1",[valeur])
cnx_dst.commit()

# Valeurs par défaut des champs dépendant de la société (compte client, compte fournisseur, comptes des catégories...) :
# propriétés sans res_id de la v15, sinon supprimées (elles pointaient sur les ids de la v20)
SQL="""
    select d.id, f.model, f.name
    from ir_default d join ir_model_fields f on f.id=d.field_id
    where f.relation in ('account.account','account.journal','account.tax','account.fiscal.position','account.payment.term')
"""
cr_dst.execute(SQL)
for row in cr_dst.fetchall():
    cr_src.execute("""
        select p.value_reference from ir_property p join ir_model_fields f on f.id=p.fields_id
        where f.model=%s and f.name=%s and p.res_id is null and p.value_reference is not null
    """,[row['model'],row['name']])
    prop = cr_src.fetchone()
    if prop:
        cr_dst.execute("update ir_default set json_value=%s where id=%s",[prop['value_reference'].split(',')[1],row['id']])
    else:
        cr_dst.execute("delete from ir_default where id=%s",[row['id']])
cnx_dst.commit()

# Propriétés des partenaires (ir_property en v15 => colonnes jsonb par société en v20)
for champ in [
    'property_account_receivable_id',    # 161 comptes clients individuels (411xxx)
    'property_account_payable_id',
    'property_payment_term_id',          # 1 316
    'property_supplier_payment_term_id', # 738
    'property_account_position_id',      # 459
]:
    MigrationIrProperty2JsonField(db_src,db_dst,'res.partner',property_src=champ,field_dst=champ)

# Identifiants externes des modèles repris (doc générale § 5.4)
MigrationIrModelData(db_src,db_dst,[
    'account.account',
    'account.tax.group',
    'account.tax',
    'account.fiscal.position',
    'account.journal',
    'account.payment.term',
    'account.reconcile.model',
])
#******************************************************************************


# ** 9.e Articles et ventes ***************************************************
# 9.e et 9.f sont à lancer ensemble : les commandes pointent sur les tables is_* (nacelles, types de prestation,
# motifs d'archivage, planning...) et Odoo 20 refuse d'afficher une liste qui pointe sur une ligne absente

# Catégories (3), liste de prix (1, celle de tous les clients : pas de propriété à reprendre), équipes commerciales (4)
MigrationTable(db_src,db_dst,'product_category',text2jsonb=True)
parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')
MigrationTable(db_src,db_dst,'product_pricelist',text2jsonb=True)
MigrationTable(db_src,db_dst,'crm_team',text2jsonb=True)
MigrationTable(db_src,db_dst,'crm_team_member')
MigrationDevisesParCode(db_src,db_dst,['product_pricelist'])

# Articles (16, tous des prestations) : type vide pour 13 articles en v15 => repris de detailed_type
# sale_delay : nombre en v15, jsonb en v20, toujours à 0 => non repris
MigrationTable(db_src,db_dst,'product_template',text2jsonb=True,exclure=['sale_delay'],
    default={'service_tracking':'no','base_unit_count':0,'type':'service'}) # type obligatoire en v20 : corrigé juste après
cr_src.execute("select id,detailed_type from product_template")
for row in cr_src.fetchall():
    type_article = 'service' if row['detailed_type']=='service' else 'consu'
    cr_dst.execute("update product_template set type=%s, is_storable=%s where id=%s",[type_article,row['detailed_type']=='product',row['id']])
cnx_dst.commit()
MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
MigrationTable(db_src,db_dst,'product_taxes_rel')
MigrationTable(db_src,db_dst,'product_supplier_taxes_rel')
MigrationIrProperty2JsonField(db_src,db_dst,'product.template',property_src='property_account_income_id',field_dst='property_account_income_id')

# Commandes (4 666) et lignes (7 017) : aucune commande « done » (état supprimé en v17)
# Lignes : product_uom => product_uom_id ; sale_order_line_invoice_rel (lien avec les lignes de factures) : en 9.g
MigrationTable(db_src,db_dst,'sale_order',default={'document_tax_mode':'tax_excluded'})
# customer_lead : décimal en v15, entier en v20, toujours à 0 => 0
MigrationTable(db_src,db_dst,'sale_order_line',rename={'product_uom':'product_uom_id'},exclure=['customer_lead'],default={'customer_lead':0})
MigrationTable(db_src,db_dst,'account_tax_sale_order_line_rel')
MigrationDevisesParCode(db_src,db_dst,['sale_order','sale_order_line'])
# Devise vide sur 1 726 commandes (2018 à 2023) et 17 lignes en v15 : champ calculé et stocké en v20
# (liste de prix, sinon société) => devise de la société (EUR, comme l'unique liste de prix)
cr_dst.execute("update sale_order o set currency_id=(select currency_id from res_company c where c.id=o.company_id) where currency_id is null")
cr_dst.execute("update sale_order_line l set currency_id=o.currency_id from sale_order o where o.id=l.order_id and l.currency_id is null")
cnx_dst.commit()

# Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...)
cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
MigrationIrModelData(db_src,db_dst,['product.category','crm.team','product.pricelist'],correspondances={
    'product.category': {
        'product_category_goods'   : categories.get('product_category_all'), # catégorie par défaut des articles
        'product_category_expenses': categories.get('cat_expense'),
        'product_category_services': categories.get('product_category_1'),
    },
})
#******************************************************************************


# ** 9.f Tables métier is_* ***************************************************
# Colonnes identiques en v15 et en v20. Déjà reprises en 9.b : is_region, is_secteur_activite, is_origine, is_groupe_client
# Non reprises : is_export_compta* (Export Ciel abandonné, question 8)
# Tables de relation des pièces jointes (*_attachment_rel) : en 9.j, avec les pièces jointes
tables=[
    'is_departement',
    'is_equipe',
    'is_departement_equipe_rel',
    'is_equipe_absence',
    'is_equipe_message',
    'is_motif_archivage',
    'is_nacelle',
    'is_type_prestation',
    'is_type_document',
    'is_controle_gestion',
    'is_sale_order_controle_gestion',
    'is_sale_order_zone',
    'is_sale_order_planning',
    'is_sale_order_planning_employee_rel',
    'is_sale_order_planning_equipe_rel',
    'is_creation_planning',
    'is_creation_planning_preparation',
    'is_planning',
    'is_planning_line',
    'is_planning_pdf',
    'is_chantier',
    'is_chantier_is_equipe_rel',
    'is_chantier_res_users_rel',
    'is_chantier_user_rel',
    'hr_employee_is_chantier_rel',
    'is_chantier_planning',
    'is_chantier_planning_employee_rel',
    'is_chantier_planning_equipe_rel',
    'is_chantier_document',
    'is_filet',
    'is_filet_mouvement',
    'is_suivi_budget',
    'is_suivi_budget_mois',
    'is_suivi_budget_groupe_client',
    'is_suivi_budget_secteur_activite',
    'is_suivi_budget_top_client',
    'is_document_employe',
]
for table in tables:
    MigrationTable(db_src,db_dst,table)
#******************************************************************************


# ** 9.g Pièces comptables ***************************************************
# 3 971 pièces (1 984 factures, 9 avoirs, 1 978 pièces de paiement), 9 485 lignes, 1 978 paiements, lettrages
# v15 : aucune pièce « à vérifier », aucune comptabilisation automatique, aucun doublon de numéro, aucun hachage

# Pièces : to_check => review_state, auto_post (booléen, toujours faux) => 'no', payment_id => origin_payment_id
# document_tax_mode : obligatoire pour les factures et avoirs (contrainte), vide pour les autres pièces (comme _compute_document_tax_mode)
MigrationTable(db_src,db_dst,'account_move',exclure=['auto_post'],default={'auto_post':'no','review_state':'no_review','document_tax_mode':'tax_excluded'})
SQL="""
    update account_move set
        amount_untaxed_in_currency_signed = amount_untaxed_signed,
        invoice_currency_rate = 1,
        document_tax_mode = case when move_type in ('out_invoice','out_refund','out_receipt','in_invoice','in_refund','in_receipt')
                                 then (select account_price_include from res_company c where c.id=account_move.company_id) end
"""
cr_dst.execute(SQL)
cnx_dst.commit()

# Lignes : display_type obligatoire en v20 (v15 : vide, sauf sections ; exclude_from_invoice_tab pour les lignes
# de taxes et d'échéances des factures) ; invoice_date stockée sur la ligne en v20
MigrationTable(db_src,db_dst,'account_move_line',default={'display_type':'product'})
SQL="""
    update account_move_line l set
        display_type = case
            when l.display_type in ('line_section','line_note') then l.display_type
            when l.tax_line_id is not null then 'tax'
            when m.move_type in ('out_invoice','out_refund','in_invoice','in_refund') and a.account_type in ('asset_receivable','liability_payable') then 'payment_term'
            else 'product'
        end,
        invoice_date = m.invoice_date
    from account_move m, account_account a
    where m.id=l.move_id and a.id=l.account_id
"""
cr_dst.execute(SQL)
cnx_dst.commit()
MigrationTable(db_src,db_dst,'account_move_line_account_tax_rel')
cr_dst.execute("delete from account_account_tag_account_move_line_rel") # étiquettes de TVA des lignes : aucune en v15
cnx_dst.commit()

# Lettrages
MigrationTable(db_src,db_dst,'account_full_reconcile')
MigrationTable(db_src,db_dst,'account_partial_reconcile')

# Paiements : nom, date, journal, société et mémo portés par la pièce en v15 ; état : draft / canceled selon la pièce,
# sinon comme Odoo 20 (_compute_state) : reconciled si les lignes de liquidité sont soldées, sinon paid
# (en v15, 1 247 paiements ont le compte client 411LOT comme compte d'attente des encaissements : repris tel quel)
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

# Pièce de chaque paiement : payment_id de la pièce en v15 => origin_payment_id (après la copie des paiements : clé étrangère)
cr_src.execute("select id,payment_id from account_move where payment_id is not null")
for row in cr_src.fetchall():
    cr_dst.execute("update account_move set origin_payment_id=%s where id=%s",[row['payment_id'],row['id']])
cnx_dst.commit()

# Factures réglées par chaque paiement (Many2many invoice_ids du paiement) : d'après les lettrages de la v15
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
for row in cr_src.fetchall():
    cr_dst.execute("insert into account_move__account_payment (invoice_id,payment_id) values (%s,%s) on conflict do nothing",[row['invoice_id'],row['payment_id']])
cnx_dst.commit()

# Lien entre les lignes de commande et les lignes de factures
MigrationTable(db_src,db_dst,'sale_order_line_invoice_rel')

# Devises : EUR = 1 en v15, 126 en v20
MigrationDevisesParCode(db_src,db_dst,['account_move','account_move_line','account_payment','account_partial_reconcile','account_full_reconcile'])
#******************************************************************************


# ** 9.h Séquences, filtres, valeurs par défaut *******************************
#******************************************************************************


# ** 9.i Chatter **************************************************************
#******************************************************************************


# ** 9.j Pièces jointes (données seulement, fichiers à l'étape 11) ************
#******************************************************************************
