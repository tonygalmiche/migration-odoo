#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de DGET : Odoo 12 (is_dget) => Odoo 20 (is_dget20)
# Documentation : Documentation/migration-odoo/migration-is_dget12-vers-is_dget20.md
# Étape 1 : contacts, utilisateurs, société, unités, articles, conditions de paiement, tables du module qui ne dépendent
# pas de la comptabilité
# Étape 2 : comptabilité (plan comptable, taxes, positions fiscales, journaux, propriétés)
# Étape 3 : tables du module liées à la comptabilité (TVA DGET, contrats, lignes de contrats, heures)
# Étape 4 : factures (account_invoice v12 => account_move), paiements, rapprochements
# A faire ensuite : pièces jointes, chatter, filtres
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit
import re


#** Paramètres ****************************************************************
db_src = "dget12"
db_dst = "dget20"
# Reprise relancée à partir de l'étape N : option --depart N (2 : comptabilité, 3 : tables du module liées à la
# comptabilité) => dget20 gardée telle quelle, étapes précédentes sautées ; chaque étape vide et recopie ses tables
depart = int(sys.argv[sys.argv.index('--depart')+1]) if '--depart' in sys.argv else 1
#******************************************************************************


# ** Repartir d'une base vierge à chaque lancement ****************************
# dget20-vierge : base v20 avec is_dget20 installé et le plan comptable fr_comp chargé (677 comptes, 48 taxes,
# 7 journaux), sans données (créée par Tony le 29/10/2026)
# Ni dget20 ni dget20-vierge ne doivent être ouvertes (Odoo arrêté ou sur une autre base) : sinon DROP / CREATE refusés
if depart==1:
    db_vierge = db_dst+'-vierge'
    SQL='DROP DATABASE "'+db_dst+'";CREATE DATABASE "'+db_dst+'" WITH TEMPLATE "'+db_vierge+'"'
    cde="""echo '"""+SQL+"""' | psql postgres"""
    lines=os.popen(cde).readlines()
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

# Contrôle des clés étrangères désactivé sur une table le temps de la recaler, réactivé même en cas d'erreur
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


# ** Étape 1 : sautée si départ à l'étape 2 ou plus (base gardée telle quelle) ****
if depart<=1:


    # ** res_partner et res_users *************************************************
    # Titres (res_partner_title, supprimé d'Odoo en v20) => is.titre du module, mêmes ids (86 titres, 1 030 contacts) ;
    # nom et abréviation traduisibles (traduction de ir_translation)
    MigrationTable(db_src,db_dst,'res_partner_title',table_dst='is_titre',text2jsonb=True)

    # Contacts copiés avec les ids de la source (7 768, tous de type contact)
    # Recréés dans le module (décisions de la doc) : customer => is_client (5 419), supplier => is_fournisseur (2 345),
    # title => is_titre_id, mobile => is_mobile (1 921) ; is_company repris tel quel (case à cocher dans le module)
    # barcode : texte en v12, jsonb (par société) en v20, jamais rempli => non repris ; credit_limit : toujours à 0
    # autopost_bills : nouvelle colonne obligatoire en v20 (valeur par défaut d'Odoo)
    # Propriétés comptables (comptes, conditions de paiement, positions fiscales) : reprises avec la comptabilité
    MigrationTable(db_src,db_dst,'res_partner',
        rename={'customer':'is_client','supplier':'is_fournisseur','title':'is_titre_id','mobile':'is_mobile'},
        exclure=['credit_limit','barcode'],default={'autopost_bills':'ask'})
    MigrationTable(db_src,db_dst,'res_users')
    MigrationTable(db_src,db_dst,'res_company_users_rel')

    # Dernière connexion de chaque utilisateur : sans elle, le statut des utilisateurs est « Invité » au lieu de « Confirmé »
    MigrationTable(db_src,db_dst,'res_users_log')

    # commercial_partner_id vide : un partenaire sans parent est son propre partenaire commercial
    cr_dst.execute("update res_partner set commercial_partner_id=id where parent_id is null and commercial_partner_id is null")
    cnx_dst.commit()

    # complete_name n'existe pas en v12 => à calculer (même logique que _get_complete_name d'Odoo 20)
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

    # SIRET : colonne siret en v12 => identifiant FR_SIRET de additional_identifiers en v20 (4 partenaires, dont la société :
    # SIRET du pied de page des documents)
    cr_src.execute("select id,replace(siret,' ','') siret from res_partner where coalesce(siret,'')<>''")
    for row in cr_src.fetchall():
        cr_dst.execute("update res_partner set additional_identifiers=coalesce(additional_identifiers,'{}'::jsonb)||jsonb_build_object('FR_SIRET',%s::text) where id=%s",[row['siret'],row['id']])
    cnx_dst.commit()

    # Groupes : correspondance par nom d'identifiant externe (is_dget.is_gestionnaire_adjudicataire_group =>
    # is_dget20.is_gestionnaire_adjudicataire_group) ; les groupes des modules absents en v20 sont ignorés
    MigrationResGroups(db_src,db_dst)

    # base.default_user supprimé en v19 : public et portaltemplate ont un id de moins en v20
    # => les identifiants externes base pointent sur les ids de la source et l'ancien default perd ses groupes
    MigrationUtilisateursTechniques(db_src,db_dst)

    # Utilisateur système __system__ : inactif, comme dans une base Odoo standard
    cr_dst.execute("update res_users set active=false where id=1")
    cnx_dst.commit()
    #******************************************************************************


    # ** res_company **************************************************************
    # Champs simples (nom, e-mail, téléphone, APE...) ; company_registry (supprimé en v20) : texte écrit en dur dans le pied
    # de page du module. Les liens vers d'autres tables (comptes, journaux, taxes, mise en page...) ont des ids différents :
    # non repris ici
    cr_dst.execute("select column_name from information_schema.columns where table_name='res_company' and column_name like '%%\\_id' and column_name<>'currency_id'")
    exclure = [row['column_name'] for row in cr_dst.fetchall()]
    MigrationDonneesTable(db_src,db_dst,'res_company',exclure=exclure)

    # Vérification des TVA par VIES : désactivée, sinon Odoo 20 vérifie tous les partenaires repris qui ont un n° de TVA
    # => à réactiver après la bascule si besoin (Paramètres / Comptabilité)
    cr_dst.execute("update res_company set vat_check_vies=false")
    cnx_dst.commit()

    # Mise en page des documents : web.external_layout_standard comme en v12 (bandeau DGET et pied de page du module) ;
    # format A4 avec les marges de la v12 (haut 30, bas 25, gauche et droite 10, en-tête 25 mm). Format en noupdate : non
    # écrasé par un -u base
    cr_dst.execute("select res_id from ir_model_data where module='web' and name='external_layout_standard'")
    layout_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("select res_id from ir_model_data where module='base' and name='paperformat_euro'")
    paperformat_id = cr_dst.fetchone()['res_id']
    cr_dst.execute("update res_company set external_report_layout_id=%s, paperformat_id=%s where id=1",[layout_id,paperformat_id])
    cr_src.execute("""
        select p.margin_top,p.margin_bottom,p.margin_left,p.margin_right,p.header_spacing
        from res_company c join report_paperformat p on p.id=c.paperformat_id where c.id=1
    """)
    format_src = cr_src.fetchone()
    cr_dst.execute("update report_paperformat set margin_top=%s, margin_bottom=%s, margin_left=%s, margin_right=%s, header_spacing=%s where id=%s",
        [format_src['margin_top'],format_src['margin_bottom'],format_src['margin_left'],format_src['margin_right'],format_src['header_spacing'],paperformat_id])
    cnx_dst.commit()

    # URL utilisée par wkhtmltopdf pour charger les CSS et images des rapports : web.base.url n'est pas joignable depuis
    # le serveur => PDF sans mise en page ; non écrasée si déjà présente (port ou hébergement différent)
    cr_dst.execute("insert into ir_config_parameter (key,value) values ('report.url','http://localhost:8069') on conflict (key) do nothing")
    cnx_dst.commit()

    # Digest périodique (mail récapitulatif d'Odoo, hebdomadaire par défaut en v20) : désactivé
    cr_dst.execute("update digest_digest set state='deactivated'")
    cnx_dst.commit()

    # Inscription libre au portail fermée : sur invitation seulement
    InscriptionSurInvitation(db_dst)

    # Couleur de l'entreprise (is_theme_entreprise) : aucune en v12, à choisir avec Tony

    # Comptes bancaires : IBAN écrit en dur sur la facture v12
    #******************************************************************************


    # ** Unités de mesure *********************************************************
    # Copiées avec les ids de la v12 (19 unités) ; voir MigrationUnites
    MigrationUnites(db_src,db_dst)
    #******************************************************************************


    # ** Articles *****************************************************************
    # 3 articles, mêmes ids qu'en v12 : ils sont écrits en dur dans la génération des factures (1 « Service » : lignes du
    # contrat, 2 « Facture » : factures précédentes) et « Révisions » est reconnu par son nom
    # Catégories (3) : nom texte en v12, traduisible en v20
    MigrationTableJsonb(db_src,db_dst,'product_category')
    parent_store_compute(cr_dst,cnx_dst,'product_category','parent_id')

    # Modèles d'articles : noms et descriptions traduisibles en v20 (traductions de ir_translation)
    # expense_policy => reinvoice_policy ; nouvelles colonnes obligatoires en v20 : service_tracking, base_unit_count
    MigrationTableJsonb(db_src,db_dst,'product_template',rename={'expense_policy':'reinvoice_policy'},
        default={'service_tracking':'no','base_unit_count':0})
    cnx_dst.commit()

    # Variantes (une par modèle) ; prix de vente des variantes (lst_price) : calculé et stocké en v20 (prix du modèle)
    MigrationTable(db_src,db_dst,'product_product',default={'base_unit_count':0})
    cr_dst.execute("update product_product p set lst_price=t.list_price from product_template t where t.id=p.product_tmpl_id")
    cnx_dst.commit()

    # Coût des variantes : propriété en v12, champ jsonb par société en v20
    MigrationIrPropertyJsonb(db_src,db_dst,'product.product','standard_price')

    # Identifiants externes : catégories renommées en v20 (product_category_all => product_category_goods...)
    cr_src.execute("select name,res_id from ir_model_data where model='product.category'")
    categories = {row['name']:row['res_id'] for row in cr_src.fetchall()}
    MigrationIrModelData(db_src,db_dst,['product.category'],correspondances={
        'product.category': {
            'product_category_goods'   : categories.get('product_category_all'),
            'product_category_expenses': categories.get('cat_expense'),
            'product_category_services': categories.get('product_category_1'),
        },
    })
    # Taxes et comptes des articles : repris avec la comptabilité
    #******************************************************************************


    # ** Conditions de paiement ***************************************************
    # 5 conditions copiées avec les ids de la v12 ; nom et note : texte en v12, traduisibles en v20
    # Échéances v12 : toutes « solde » à N jours après la date de facture (day_after_invoice_date) => days_after, N jours,
    # 100 % (value « balance » supprimé en v20)
    MigrationTableJsonb(db_src,db_dst,'account_payment_term')
    cr_src.execute("select * from account_payment_term_line order by payment_id, sequence, id")
    lignes = cr_src.fetchall()
    autres = [l for l in lignes if l['value']!='balance' or l['option']!='day_after_invoice_date']
    if autres:
        print("Échéances non prévues par le script (à convertir) : %s"%[(l['payment_id'],l['value'],l['option']) for l in autres])
    cr_dst.execute("alter table account_payment_term_line disable trigger all; delete from account_payment_term_line;")
    for l in lignes:
        SQL="""
            insert into account_payment_term_line (id,payment_id,value,value_amount,delay_type,nb_days,days_next_month,create_uid,create_date,write_uid,write_date)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cr_dst.execute(SQL,[l['id'],l['payment_id'],'percent',100,'days_after',l['days'] or 0,'10',l['create_uid'],l['create_date'],l['write_uid'],l['write_date']])
    cr_dst.execute("alter table account_payment_term_line enable trigger all")
    cnx_dst.commit()
    SetSequence(cr_dst,cnx_dst,'account_payment_term_line')
    MigrationIrModelData(db_src,db_dst,['account.payment.term'])

    # Conditions des clients (7 743 propriétés) : propriétés en v12, champs jsonb par société en v20
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_payment_term_id')
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_supplier_payment_term_id')
    #******************************************************************************


    # ** Tables du module (sans lien avec la comptabilité) ************************
    # Mêmes colonnes qu'en v12, copiées avec leurs ids dans l'ordre des dépendances. TVA DGET (is_tva : taxe et compte),
    # contrats, lignes de contrats et heures : étape 3, après la comptabilité
    for table in [
        'is_classement',                    # contacts
        'is_specialite',
        'is_classement_fournisseur',
        'res_partner_is_specialite_rel',
        'is_dossier_reference',             # tables des dossiers
        'is_dossier_contrat_traitance',
        'is_dossier_contrat_phase',
        'is_dossier_code_assurance',
        'is_dossier',                       # dossiers (2 427), références, notes, adjudicataires
        'is_dossier_is_reference_rel',
        'is_dossier_note',
        'is_dossier_adjudicataire',
        'is_concours',                      # concours (2 738)
        'is_concours_qui',
        'is_declaration_maf',               # déclarations MAF (7)
    ]:
        MigrationTable(db_src,db_dst,table)
    #******************************************************************************


# ** Étape 2 : sautée si départ à l'étape 3 ou plus ***************************
if depart<=2:


    # ** Paramètres comptables ****************************************************
    # Plan comptable (716 comptes), groupes de taxes (12), taxes (45), positions fiscales (3) et journaux (7) de la v12
    # copiés avec leurs ids à la place de ceux du plan fr_comp de la v20 (chargé dans dget20-vierge ; plan général
    # l10n_fr_pcg_chart_template en v12) ; colonnes ajoutées par la v20 (codes Factur-X des taxes...) reprises de
    # l'enregistrement v20 équivalent (même identifiant externe) ; références de la v20 recalées. Les ids de la v12 sont
    # écrits en dur dans le module (compte 622 = 701100, position fiscale 1) et dans is_tva
    # Voir Documentation/migration-odoo/migration-vers-odoo20.md § 3.7 et § 5.4
    cr_dst.execute("select count(*) as nb from account_account")
    if not cr_dst.fetchone()['nb']:
        print("Aucun compte dans %s : charger le plan comptable fr_comp (Comptabilité / Configuration / Paramètres) avant l'étape 2"%db_dst)
        sys.exit()

    # Lignes v20 et correspondance par identifiant externe, avant la copie
    # Taxes TTC de la v12 (16, jamais utilisées), absentes de la v20 : codes Factur-X de la taxe HT correspondante
    avant, corr = {}, {}
    for table,suffixes in [('account_account',[]),('account_tax_group',[]),('account_tax',['_TTC','_ttc']),('account_fiscal_position',[])]:
        avant[table], corr[table] = LireAvantCopie(db_src,db_dst,table,suffixes)
    # Taxes de vente à 0 % renommées en v20 (séparées en biens et services, codes Factur-X différents) => taxes « biens »
    taxes_renommees = {
        '1_tva_0'        : '1_tva_sale_good_0',         # TVA 0% autres opérations non imposables (vente) => E
        '1_tva_export_0' : '1_tva_sale_good_export_0',  # TVA 0% export (vente) => G
        '1_tva_intra_0'  : '1_tva_sale_good_intra_0',   # TVA 0% livraisons intracommunautaires (vente) => K
    }
    cr_src.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees)])
    taxes_src = {row['name']:row['res_id'] for row in cr_src.fetchall()}
    cr_dst.execute("select name,res_id from ir_model_data where model='account.tax' and name = any(%s)",[list(taxes_renommees.values())])
    taxes_dst = {row['name']:row['res_id'] for row in cr_dst.fetchall()}
    for nom_src,nom_dst in taxes_renommees.items():
        if nom_src in taxes_src and nom_dst in taxes_dst:
            corr['account_tax'][taxes_src[nom_src]] = taxes_dst[nom_dst]
        else:
            print("Taxe %s => %s : identifiant absent"%(nom_src,nom_dst))
    avant['account_journal'], _ = LireAvantCopie(db_src,db_dst,'account_journal')
    # Journaux : pas d'identifiant externe en v12 => correspondance par code (FAC, OD, EXCH, CABA, BNK1...), sinon par type
    # s'il n'y en a qu'un
    cr_src.execute("select id,code,type from account_journal")
    journaux_src = cr_src.fetchall()
    corr['account_journal'] = {}
    for j20 in avant['account_journal'].values():
        j12 = [j for j in journaux_src if j['code']==j20['code']] or [j for j in journaux_src if j['type']==j20['type']]
        if len(j12)==1 and j12[0]['id'] not in corr['account_journal']:
            corr['account_journal'][j12[0]['id']] = j20['id']
    print("Journaux (id v12 : id v20) : %s"%corr['account_journal'])
    inverse = {t:{id20:id_src for id_src,id20 in sorted(c.items(),reverse=True)} for t,c in corr.items()} # id v20 => id v12

    # Lignes de répartition des taxes de la v20 et leurs étiquettes (cases de la déclaration de TVA), avant la copie :
    # reprises pour la taxe v12 équivalente (voir plus bas)
    cr_dst.execute("""
        select r.tax_id, r.document_type, r.repartition_type, array_remove(array_agg(x.account_account_tag_id),null) as tags, count(distinct r.id) as nb
        from account_tax_repartition_line r left join account_account_tag_account_tax_repartition_line_rel x on x.account_tax_repartition_line_id=r.id
        group by 1,2,3
    """)
    etiquettes_v20 = {(row['tax_id'],row['document_type'],row['repartition_type']):row for row in cr_dst.fetchall()}

    # Tables de la v20 liées aux anciens comptes et taxes, sans équivalent repris
    for table in [
        'account_tax_filiation_rel',                                # taxes groupées (aucune en v12)
        'account_fiscal_position_account',                          # correspondances de comptes (aucune en v12)
        'account_fiscal_position_account_tax_rel',                  # recréées plus bas à partir de la v12
        'account_tax_alternatives',                                 # recréées plus bas à partir de la v12
        'account_account_tag_account_tax_repartition_line_rel',     # recréées avec les lignes de répartition
        'account_tax_repartition_line',
        'account_reconcile_model_line',                             # modèles de rapprochement : aucun en v12
        'account_reconcile_model',
    ]:
        cr_dst.execute("delete from "+table)
    cnx_dst.commit()

    # Comptes : nom traduisible, code => code_store (par société), deprecated => active, société => account_account_res_company_rel
    # Type : user_type_id (account.account.type, supprimé en v16) => account_type, d'après l'identifiant externe du type
    MigrationTableJsonb(db_src,db_dst,'account_account',default={'account_type':'income'})
    # Colonnes ajoutées par la v20 d'abord : code_store, active et account_type sont posés juste après
    CompleterColonnesV20(db_src,db_dst,'account_account',avant['account_account'],corr['account_account'],inverse)
    types_comptes = {
        'data_account_type_receivable'             : 'asset_receivable',
        'data_account_type_payable'                : 'liability_payable',
        'data_account_type_liquidity'              : 'asset_cash',
        'data_account_type_credit_card'            : 'liability_credit_card',
        'data_account_type_current_assets'         : 'asset_current',
        'data_account_type_non_current_assets'     : 'asset_non_current',
        'data_account_type_prepayments'            : 'asset_prepayments',
        'data_account_type_fixed_assets'           : 'asset_fixed',
        'data_account_type_current_liabilities'    : 'liability_current',
        'data_account_type_non_current_liabilities': 'liability_non_current',
        'data_account_type_equity'                 : 'equity',
        'data_unaffected_earnings'                 : 'equity_unaffected',
        'data_account_type_revenue'                : 'income',
        'data_account_type_other_income'           : 'income_other',
        'data_account_type_expenses'               : 'expense',
        'data_account_type_depreciation'           : 'expense_depreciation',
        'data_account_type_direct_costs'           : 'expense_direct_cost',
        'data_account_off_sheet'                   : 'off_balance',
    }
    cr_src.execute("""
        select a.id,a.code,a.deprecated,a.company_id,d.name as type
        from account_account a left join ir_model_data d on d.model='account.account.type' and d.res_id=a.user_type_id
    """)
    comptes = cr_src.fetchall()
    sans_type = [row['code'] for row in comptes if row['type'] not in types_comptes]
    if sans_type:
        print("Comptes sans type connu (laissés en produit) : %s"%sans_type)
    cr_dst.execute("delete from account_account_res_company_rel")
    execute_values(cr_dst,"""
        update account_account a set code_store=jsonb_build_object('1',s.code), active=not s.deprecated, account_type=s.account_type
        from (values %s) as s(id,code,deprecated,account_type) where s.id=a.id
    """,[(row['id'],row['code'],bool(row['deprecated']),types_comptes.get(row['type'],'income')) for row in comptes],page_size=5000)
    execute_values(cr_dst,"insert into account_account_res_company_rel (account_account_id,res_company_id) values %s",
        [(row['id'],row['company_id'] or 1) for row in comptes])
    cnx_dst.commit()
    parent_store_compute(cr_dst,cnx_dst,'account_account','parent_id')

    # Groupes de taxes (société obligatoire en v20) et taxes : price_include => price_include_override (vide = réglage de la société)
    # country_id : nouvelle colonne obligatoire en v20 => France (pays de la société)
    cr_dst.execute("select id from res_country where code='FR'")
    pays_fr = cr_dst.fetchone()['id']
    MigrationTableJsonb(db_src,db_dst,'account_tax_group',default={'company_id':1})
    CompleterColonnesV20(db_src,db_dst,'account_tax_group',avant['account_tax_group'],corr['account_tax_group'],inverse)
    MigrationTableJsonb(db_src,db_dst,'account_tax',default={'country_id':pays_fr})
    CompleterColonnesV20(db_src,db_dst,'account_tax',avant['account_tax'],corr['account_tax'],inverse)
    cr_src.execute("select id from account_tax where price_include")
    cr_dst.execute("update account_tax set price_include_override=case when id = any(%s) then 'tax_included' end",[[row['id'] for row in cr_src.fetchall()]])
    cnx_dst.commit()

    # Lignes de répartition (créées en v13) : en v12, la taxe porte ses comptes (account_id pour les factures,
    # refund_account_id pour les avoirs) => 4 lignes par taxe : base et taxe (100 %, compte de la v12), factures et avoirs.
    # Étiquettes (cases de la déclaration de TVA) : celles de la taxe v20 équivalente quand elle a une seule ligne du même
    # type (les taxes d'autoliquidation intracommunautaire de la v20 ont deux lignes de taxe : sans étiquette)
    cr_src.execute("select id,account_id,refund_account_id from account_tax order by id")
    nb_etiquettes = 0
    for t in cr_src.fetchall():
        id20 = corr['account_tax'].get(t['id'])
        for sequence,(document_type,repartition_type,compte) in enumerate([
            ('invoice','base',None), ('invoice','tax',t['account_id']),
            ('refund' ,'base',None), ('refund' ,'tax',t['refund_account_id']),
        ]):
            cr_dst.execute("""
                insert into account_tax_repartition_line (tax_id,document_type,repartition_type,factor_percent,account_id,sequence,company_id,use_in_tax_closing,create_uid,create_date,write_uid,write_date)
                values (%s,%s,%s,100,%s,%s,1,%s,1,now(),1,now()) returning id
            """,[t['id'],document_type,repartition_type,compte,sequence+1,repartition_type=='tax'])
            ligne_id = cr_dst.fetchone()['id']
            v20 = etiquettes_v20.get((id20,document_type,repartition_type))
            if v20 and v20['nb']==1:
                for tag in v20['tags']:
                    cr_dst.execute("insert into account_account_tag_account_tax_repartition_line_rel (account_tax_repartition_line_id,account_account_tag_id) values (%s,%s) on conflict do nothing",[ligne_id,tag])
                    nb_etiquettes+=1
    cnx_dst.commit()
    print("Lignes de répartition des taxes : 4 par taxe, %s étiquettes reprises de la v20"%nb_etiquettes)
    MigrationTable(db_src,db_dst,'account_account_tax_default_rel')

    # Positions fiscales (3) ; correspondances de taxes (50) : en v20, portées par la taxe de remplacement
    # Codes postaux : entier en v12 (0 = aucun), texte en v20
    MigrationTableJsonb(db_src,db_dst,'account_fiscal_position')
    cr_dst.execute("update account_fiscal_position set zip_from=null where zip_from='0'")
    cr_dst.execute("update account_fiscal_position set zip_to=null where zip_to='0'")
    # Validé avant CompleterColonnesV20 (autre connexion) : sinon elle attend la fin de cette transaction (blocage)
    cnx_dst.commit()
    CompleterColonnesV20(db_src,db_dst,'account_fiscal_position',avant['account_fiscal_position'],corr['account_fiscal_position'],inverse)
    cr_src.execute("select position_id,tax_src_id,tax_dest_id from account_fiscal_position_tax where tax_dest_id is not null")
    for row in cr_src.fetchall():
        cr_dst.execute("insert into account_fiscal_position_account_tax_rel (account_tax_id,account_fiscal_position_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['position_id']])
        cr_dst.execute("insert into account_tax_alternatives (dest_tax_id,src_tax_id) values (%s,%s) on conflict do nothing",[row['tax_dest_id'],row['tax_src_id']])
    cr_dst.execute("update account_tax t set is_domestic = not exists (select 1 from account_fiscal_position_account_tax_rel r where r.account_tax_id=t.id)")
    cr_dst.execute("update account_fiscal_position set is_domestic=false")
    cnx_dst.commit()

    # Journaux (7) : alias de messagerie non repris ; séquences (sequence_id, refund_sequence_id) supprimées en v14 : le
    # n° des factures est posé par le module (nom de la pièce)
    # default_debit_account_id => default_account_id (compte par défaut du journal, ex : 707100 pour FAC)
    MigrationTableJsonb(db_src,db_dst,'account_journal',default={'invoice_reference_type':'invoice','invoice_reference_model':'odoo'})
    cr_dst.execute("update account_journal set alias_id=null")
    cnx_dst.commit()
    CompleterColonnesV20(db_src,db_dst,'account_journal',avant['account_journal'],corr['account_journal'],inverse)
    cr_src.execute("select id,default_debit_account_id from account_journal where default_debit_account_id is not null")
    for row in cr_src.fetchall():
        cr_dst.execute("update account_journal set default_account_id=%s where id=%s",[row['default_debit_account_id'],row['id']])
    cnx_dst.commit()
    # Modes de paiement des journaux : table account_payment_method_line créée en v15 => lignes créées par la v20 gardées,
    # journal recalé sur l'id v12 ; lignes d'un journal sans équivalent supprimées
    cr_dst.execute("select id,journal_id from account_payment_method_line")
    for row in cr_dst.fetchall():
        id12 = inverse['account_journal'].get(row['journal_id'])
        if id12:
            cr_dst.execute("update account_payment_method_line set journal_id=%s where id=%s",[id12,row['id']])
        else:
            cr_dst.execute("delete from account_payment_method_line where id=%s",[row['id']])
    cnx_dst.commit()

    # Étiquettes des comptes : aucune en v12 => celles de la v20 (sur les comptes v20 remplacés) supprimées
    MigrationEtiquettesTaxes(db_src,db_dst,[('account_account_account_tag','account_account_id')])

    # Devises (EUR = 1 en v12, 126 en v20)
    MigrationDevisesParCode(db_src,db_dst,['account_account','account_journal'])

    # Champs comptables de la société et valeurs par défaut (comptes clients / fournisseurs, comptes des catégories...) :
    # valeur de la v12 (colonne de la société, propriété sans res_id), sinon valeur de la v20 convertie par la
    # correspondance (champs ajoutés en v20), sinon vidée
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
            where f.model=%s and f.name=%s and p.res_id is null and p.value_reference is not null
        """,[row['model'],row['name']])
        prop = cr_src.fetchone()
        valeur = int(prop['value_reference'].split(',')[1]) if prop else inverse.get(row['relation'].replace('.','_'),{}).get(json.loads(row['json_value']))
        if valeur:
            cr_dst.execute("update ir_default set json_value=%s where id=%s",[json.dumps(valeur),row['id']])
        else:
            cr_dst.execute("delete from ir_default where id=%s",[row['id']])
    cnx_dst.commit()

    # Propriétés par enregistrement (ir_property en v12 => colonnes jsonb par société en v20) : aucune en v12 (seulement
    # les valeurs par défaut, reprises ci-dessus) ; appelées pour le contrôle
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_receivable_id')
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_payable_id')
    MigrationIrPropertyJsonb(db_src,db_dst,'res.partner','property_account_position_id')
    MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_income_id')
    MigrationIrPropertyJsonb(db_src,db_dst,'product.template','property_account_expense_id')

    # Taxes des articles (3, ids des taxes de la v12)
    for table in ['product_taxes_rel','product_supplier_taxes_rel']:
        MigrationTable(db_src,db_dst,table)

    # Identifiants externes des modèles repris (journaux : par la correspondance par code, sans identifiant en v12)
    # Taxes à 0 % : identifiants « biens » de la v20 gardés sur les taxes v12 correspondantes (voir taxes_renommees)
    MigrationIrModelData(db_src,db_dst,['account.account','account.tax.group','account.tax','account.fiscal.position'],correspondances={
        'account.tax': {nom_dst:taxes_src[nom_src] for nom_src,nom_dst in taxes_renommees.items() if nom_src in taxes_src},
    })
    cr_dst.execute("select id,res_id from ir_model_data where model='account.journal'")
    for row in cr_dst.fetchall():
        id12 = inverse['account_journal'].get(row['res_id'])
        if id12:
            cr_dst.execute("update ir_model_data set res_id=%s where id=%s",[id12,row['id']])
        else:
            cr_dst.execute("delete from ir_model_data where id=%s",[row['id']])
    cr_dst.execute("delete from ir_model_data where model in ('account.reconcile.model','account.reconcile.model.line')")
    cnx_dst.commit()
    #******************************************************************************


# ** Étape 3 : tables du module liées à la comptabilité ***********************
if depart<=3:
    # TVA DGET (3 : taxe et compte de vente des factures du contrat), contrats (2 041), lignes de contrats (9 937 ;
    # colonne facture, calculée non stockée en v20, non reprise), heures des salariés (43 119)
    # Factures des contrats (invoice_ids) et liens des lignes de factures : avec les factures
    for table in [
        'is_tva',
        'is_dossier_contrat',
        'is_dossier_contrat_detail',
        'is_salarie_heure',
    ]:
        MigrationTable(db_src,db_dst,table)
    #******************************************************************************


# ** Étape 4 : factures, paiements, rapprochements ****************************
if depart<=4:
    # Factures v12 (account_invoice : 5 921, dont 156 avoirs et 27 annulées sans pièce comptable) => account_move avec
    # l'id de la facture (et non celui de sa pièce v12) : liens du module (is_invoice_id des lignes) et res_id des pièces
    # jointes et messages gardés tels quels. Pièces des paiements (3, sans facture) : ids à la suite des factures
    # Lignes : celles de la facture v12 (account_invoice_line : articles et notes, y compris les quantités 0, sans écriture
    # en v12), id = id v12 + plus grand id des écritures v12 ; lignes de taxes, lignes clients et lignes des paiements :
    # écritures v12 avec leurs ids (rapprochements). Montant des lignes des factures = écritures v12 (même total par
    # facture, contrôlé sur la v12)
    cr_dst.execute("select id from res_currency where name='EUR'")
    eur = cr_dst.fetchone()['id']

    # Tables vidées dans l'ordre des dépendances (relance avec --depart 4)
    for table in [
        'account_account_tag_account_move_line_rel',
        'account_move_line_account_tax_rel',
        'account_move__account_payment',
        'account_partial_reconcile',
        'account_move_line',
    ]:
        cr_dst.execute("delete from "+table)
    cr_dst.execute("update account_payment set move_id=null")
    cr_dst.execute("delete from account_move")
    cr_dst.execute("delete from account_payment")
    cr_dst.execute("delete from account_full_reconcile")
    cnx_dst.commit()

    # Insertion de lignes (dictionnaires avec les mêmes clés)
    def Inserer(table,lignes):
        if lignes:
            colonnes = list(lignes[0])
            execute_values(cr_dst,"insert into "+table+" ("+",".join(colonnes)+") values %s",
                [[ligne[c] for c in colonnes] for ligne in lignes],page_size=5000)
            cnx_dst.commit()
            SetSequence(cr_dst,cnx_dst,table)

    # N° de pièce => sequence_prefix et sequence_number (même découpage que _compute_split_sequence d'Odoo 20 :
    # 37FC183 => 37FC, 183)
    def DecouperNumero(name):
        prefixe,numero = re.match(r'^(.*?)(\d{0,9})(\D*?)$',name or '').groups()[:2]
        return prefixe,int(numero or 0)

    # Pièces v12 => id v20
    cr_src.execute("select max(id) as id from account_invoice")
    max_facture = cr_src.fetchone()['id']
    cr_src.execute("select max(id) as id from account_move_line")
    decalage = cr_src.fetchone()['id']
    cr_src.execute("select id,move_id from account_invoice where move_id is not null")
    pieces = {row['move_id']:row['id'] for row in cr_src.fetchall()}
    pieces_factures = set(pieces)
    cr_src.execute("select id from account_move m where not exists (select 1 from account_invoice i where i.move_id=m.id) order by id")
    for i,row in enumerate(cr_src.fetchall()):
        pieces[row['id']] = max_facture+i+1
    cr_dst.execute("select id,complete_name,commercial_partner_id from res_partner")
    partenaires = {row['id']:row for row in cr_dst.fetchall()}

    # Paiements (4, dont 1 brouillon) : insérés avant les pièces (origin_payment_id), pièce posée ensuite
    # Comptes : ceux des écritures v12 du paiement (512001 et 411100) ; état posted => paid (compte de banque non
    # rapproché avec un relevé)
    cr_src.execute("""
        select l.payment_id, l.move_id, l.account_id, a.internal_type, l.reconciled
        from account_move_line l join account_account a on a.id=l.account_id where l.payment_id is not null
    """)
    lignes_paiements = cr_src.fetchall()
    cr_dst.execute("""
        select l.id, l.journal_id, m.id as payment_method_id, m.payment_type
        from account_payment_method_line l join account_payment_method m on m.id=l.payment_method_id where m.code='manual'
    """)
    modes = {(row['journal_id'],row['payment_type']):row for row in cr_dst.fetchall()}
    etats_paiements = {'draft':'draft','cancelled':'canceled'}
    cr_src.execute("select * from account_payment order by id")
    paiements = []
    for p in cr_src.fetchall():
        lignes_p = [l for l in lignes_paiements if l['payment_id']==p['id']]
        mode = modes.get((p['journal_id'],p['payment_type']),{})
        paiements.append({
            'id'                            : p['id'],
            'name'                          : p['name'],
            'state'                         : etats_paiements.get(p['state'],'paid'),
            'payment_type'                  : p['payment_type'],
            'partner_type'                  : p['partner_type'],
            'partner_id'                    : p['partner_id'],
            'commercial_partner_id'         : partenaires[p['partner_id']]['commercial_partner_id'] if p['partner_id'] else None,
            'amount'                        : p['amount'],
            'amount_company_currency_signed': p['amount'] if p['payment_type']=='inbound' else -p['amount'],
            'currency_id'                   : eur,
            'date'                          : p['payment_date'],
            'memo'                          : p['communication'],
            'payment_reference'             : p['payment_reference'],
            'journal_id'                    : p['journal_id'],
            'company_id'                    : 1,
            'payment_method_line_id'        : mode.get('id'),
            'payment_method_id'             : mode.get('payment_method_id'),
            'outstanding_account_id'        : next((l['account_id'] for l in lignes_p if l['internal_type']=='liquidity'),None),
            'destination_account_id'        : next((l['account_id'] for l in lignes_p if l['internal_type'] in ('receivable','payable')),None),
            'is_reconciled'                 : any(l['reconciled'] for l in lignes_p),
            'is_matched'                    : False,
            'is_sent'                       : False,
            'create_uid'                    : p['create_uid'],
            'create_date'                   : p['create_date'],
            'write_uid'                     : p['write_uid'],
            'write_date'                    : p['write_date'],
        })
    Inserer('account_payment',paiements)
    paiement_piece = {pieces[l['move_id']]:l['payment_id'] for l in lignes_paiements}

    # Valeurs communes des pièces
    defaut_piece = {
        'move_type':'entry', 'company_id':1, 'currency_id':eur, 'invoice_currency_rate':1, 'auto_post':'no',
        'review_state':'no_review', 'always_tax_exigible':False, 'made_sequence_gap':False, 'is_manually_modified':False,
        'quick_edit_total_amount':0, 'is_move_sent':False, 'is_facture_payee':'non', 'payment_state':'not_paid',
    }
    for colonne in [
        'id','name','ref','payment_reference','narration','date','invoice_date','invoice_date_due','invoice_origin','state',
        'posted_before','journal_id','partner_id','commercial_partner_id','partner_shipping_id','fiscal_position_id',
        'invoice_payment_term_id','invoice_user_id','team_id','invoice_partner_display_name','invoice_source_email',
        'access_token','origin_payment_id','sequence_prefix','sequence_number','document_tax_mode',
        'amount_untaxed','amount_tax','amount_total','amount_residual','amount_untaxed_signed','amount_tax_signed',
        'amount_total_signed','amount_residual_signed','amount_untaxed_in_currency_signed','amount_total_in_currency_signed',
        'is_contrat_id','is_dossier_id','is_tva_id','is_date_update_facture','is_montant_revision',
        'is_montant_hors_revision','is_montant_hors_revision_signe',
        'create_uid','create_date','write_uid','write_date',
    ]:
        defaut_piece.setdefault(colonne,None)

    # Factures : open et paid => posted (payment_state not_paid ou paid, comme en v12 ; « Payée » du module reprise)
    # N° : number (move_name pour les annulées) ; ref : référence de la pièce v12 (37FC183/86), aussi référence de paiement
    # Montants signés : négatifs pour les avoirs
    # document_tax_mode (HT / TTC, obligatoire sur les factures en v20) : réglage de la société, comme _compute_document_tax_mode
    cr_dst.execute("select account_price_include from res_company where id=1")
    mode_taxes = cr_dst.fetchone()['account_price_include']
    cr_src.execute("""
        select i.*, m.ref as move_ref, m.narration
        from account_invoice i left join account_move m on m.id=i.move_id
        order by i.id
    """)
    factures, pieces_v20 = {}, []
    for f in cr_src.fetchall():
        name = f['number'] or f['move_name'] or '/'
        prefixe,numero = DecouperNumero(name)
        state = {'draft':'draft','cancel':'cancel'}.get(f['state'],'posted')
        signe = -1 if f['type'] in ('out_refund','in_invoice') else 1
        date = f['date'] or f['date_invoice'] or f['create_date'].date()
        factures[f['id']] = {'move_type':f['type'],'state':state,'date':date,'invoice_date':f['date_invoice'],
            'journal_id':f['journal_id'],'partner_id':f['commercial_partner_id'],'signe':signe}
        pieces_v20.append(dict(defaut_piece,
            id=f['id'], name=name, ref=f['move_ref'] or f['reference'], payment_reference=f['reference'],
            narration=f['narration'] or f['comment'], date=date, invoice_date=f['date_invoice'],
            invoice_date_due=f['date_due'], invoice_origin=f['origin'], state=state, posted_before=state=='posted',
            move_type=f['type'], document_tax_mode=mode_taxes, journal_id=f['journal_id'], partner_id=f['partner_id'],
            commercial_partner_id=f['commercial_partner_id'], partner_shipping_id=f['partner_shipping_id'],
            fiscal_position_id=f['fiscal_position_id'], invoice_payment_term_id=f['payment_term_id'],
            invoice_user_id=f['user_id'], team_id=f['team_id'],
            invoice_partner_display_name=partenaires[f['partner_id']]['complete_name'] if f['partner_id'] else None,
            invoice_source_email=f['source_email'], access_token=f['access_token'], is_move_sent=bool(f['sent']),
            payment_state='paid' if f['state']=='paid' else 'not_paid', sequence_prefix=prefixe, sequence_number=numero,
            amount_untaxed=f['amount_untaxed'], amount_tax=f['amount_tax'], amount_total=f['amount_total'],
            amount_residual=f['residual'], amount_untaxed_signed=signe*f['amount_untaxed'],
            amount_tax_signed=signe*f['amount_tax'], amount_total_signed=signe*f['amount_total'],
            amount_residual_signed=signe*f['residual'], amount_untaxed_in_currency_signed=signe*f['amount_untaxed'],
            amount_total_in_currency_signed=signe*f['amount_total'],
            is_contrat_id=f['is_contrat_id'], is_dossier_id=f['is_dossier_id'], is_tva_id=f['is_tva_id'],
            is_date_update_facture=f['is_date_update_facture'], is_facture_payee=f['is_facture_payee'] or 'non',
            is_montant_revision=f['is_montant_revision'], is_montant_hors_revision=f['is_montant_hors_revision'],
            is_montant_hors_revision_signe=f['is_montant_hors_revision_signe'],
            create_uid=f['create_uid'], create_date=f['create_date'], write_uid=f['write_uid'], write_date=f['write_date'],
        ))

    # Pièces des paiements : écritures diverses (entry) liées à leur paiement
    cr_src.execute("select * from account_move m where not exists (select 1 from account_invoice i where i.move_id=m.id) order by id")
    for m in cr_src.fetchall():
        prefixe,numero = DecouperNumero(m['name'])
        pieces_v20.append(dict(defaut_piece,
            id=pieces[m['id']], name=m['name'], ref=m['ref'], narration=m['narration'], date=m['date'],
            state=m['state'], posted_before=m['state']=='posted', journal_id=m['journal_id'], partner_id=m['partner_id'],
            commercial_partner_id=partenaires[m['partner_id']]['commercial_partner_id'] if m['partner_id'] else None,
            origin_payment_id=paiement_piece.get(pieces[m['id']]), sequence_prefix=prefixe, sequence_number=numero,
            amount_total=m['amount'], amount_total_signed=m['amount'], amount_total_in_currency_signed=m['amount'],
            amount_residual=0, amount_residual_signed=0,
            create_uid=m['create_uid'], create_date=m['create_date'], write_uid=m['write_uid'], write_date=m['write_date'],
        ))
    Inserer('account_move',pieces_v20)

    # Lettrages complets (3) : avant les lignes (full_reconcile_id)
    MigrationTable(db_src,db_dst,'account_full_reconcile')

    # Valeurs communes des lignes
    defaut_ligne = {'company_id':1, 'currency_id':eur, 'company_currency_id':eur, 'discount':0, 'reconciled':False,
        'amount_residual':0, 'amount_residual_currency':0}
    for colonne in [
        'id','move_id','move_name','display_type','sequence','name','ref','product_id','product_uom_id','quantity',
        'price_unit','price_subtotal','price_total','account_id','partner_id','journal_id','date','invoice_date',
        'date_maturity','parent_state','debit','credit','balance','amount_currency','tax_line_id','tax_base_amount',
        'full_reconcile_id','matching_number','payment_id','is_contrat_detail_id','is_invoice_id','is_deja_facture',
        'is_reellement_facture','is_montant_reellement_facture','create_uid','create_date','write_uid','write_date',
    ]:
        defaut_ligne.setdefault(colonne,None)
    noms_pieces = {p['id']:p['name'] for p in pieces_v20}

    # Lignes des factures (articles et notes) : montant signé (crédit pour les factures, débit pour les avoirs)
    cr_src.execute("select * from account_invoice_line order by id")
    lignes = []
    for l in cr_src.fetchall():
        f = factures[l['invoice_id']]
        note = l['display_type']=='line_note'
        balance = 0 if note else -f['signe']*(l['price_subtotal'] or 0)
        lignes.append(dict(defaut_ligne,
            id=decalage+l['id'], move_id=l['invoice_id'], move_name=noms_pieces[l['invoice_id']],
            display_type='line_note' if note else 'product', sequence=l['sequence'], name=l['name'],
            product_id=l['product_id'], product_uom_id=l['uom_id'], quantity=l['quantity'], price_unit=l['price_unit'],
            discount=l['discount'] or 0, price_subtotal=l['price_subtotal'], price_total=l['price_total'],
            account_id=l['account_id'], partner_id=f['partner_id'], journal_id=f['journal_id'], date=f['date'],
            invoice_date=f['invoice_date'], parent_state=f['state'], debit=max(balance,0), credit=max(-balance,0),
            balance=balance, amount_currency=balance, is_contrat_detail_id=l['is_contrat_detail_id'],
            is_invoice_id=l['is_invoice_id'], is_deja_facture=l['is_deja_facture'],
            is_reellement_facture=l['is_reellement_facture'], is_montant_reellement_facture=l['is_montant_reellement_facture'],
            create_uid=l['create_uid'], create_date=l['create_date'], write_uid=l['write_uid'], write_date=l['write_date'],
        ))

    # Écritures v12 gardées : taxes et lignes clients des factures, toutes les lignes des paiements
    cr_src.execute("""
        select l.*, a.internal_type
        from account_move_line l join account_account a on a.id=l.account_id
        where l.tax_line_id is not null or a.internal_type in ('receivable','payable')
           or not exists (select 1 from account_invoice i where i.move_id=l.move_id)
        order by l.id
    """)
    for l in cr_src.fetchall():
        facture = l['move_id'] in pieces_factures
        f = factures.get(pieces[l['move_id']],{})
        balance = l['debit']-l['credit']
        lignes.append(dict(defaut_ligne,
            id=l['id'], move_id=pieces[l['move_id']], move_name=noms_pieces[pieces[l['move_id']]],
            display_type=('tax' if l['tax_line_id'] else 'payment_term') if facture else 'product',
            name=l['name'], ref=l['ref'], product_id=l['product_id'], product_uom_id=l['product_uom_id'],
            quantity=l['quantity'], account_id=l['account_id'], partner_id=l['partner_id'], journal_id=l['journal_id'],
            date=l['date'], invoice_date=f.get('invoice_date'), date_maturity=l['date_maturity'], parent_state='posted',
            debit=l['debit'], credit=l['credit'], balance=balance, amount_currency=balance,
            amount_residual=l['amount_residual'], amount_residual_currency=l['amount_residual'], reconciled=l['reconciled'],
            tax_line_id=l['tax_line_id'], tax_base_amount=l['tax_base_amount'], full_reconcile_id=l['full_reconcile_id'],
            matching_number=str(l['full_reconcile_id']) if l['full_reconcile_id'] else None, payment_id=l['payment_id'],
            create_uid=l['create_uid'], create_date=l['create_date'], write_uid=l['write_uid'], write_date=l['write_date'],
        ))
    Inserer('account_move_line',lignes)

    # Taxes des lignes des factures (account_invoice_line_tax)
    cr_src.execute("select invoice_line_id,tax_id from account_invoice_line_tax")
    execute_values(cr_dst,"insert into account_move_line_account_tax_rel (account_move_line_id,account_tax_id) values %s",
        [(decalage+row['invoice_line_id'],row['tax_id']) for row in cr_src.fetchall()],page_size=5000)
    cnx_dst.commit()

    # Lignes de taxes : groupe et ligne de répartition (créées à l'étape 2, facture ou avoir) ; étiquettes (cases de la
    # déclaration de TVA) des lignes d'articles (ligne de répartition « base » de leur taxe) et des lignes de taxes
    SQL="""
        update account_move_line l set tax_group_id=t.tax_group_id from account_tax t where t.id=l.tax_line_id;
        update account_move_line l set tax_repartition_line_id=r.id
        from account_move m, account_tax_repartition_line r
        where m.id=l.move_id and r.tax_id=l.tax_line_id and r.repartition_type='tax'
          and r.document_type=case when m.move_type in ('out_refund','in_refund') then 'refund' else 'invoice' end;
        insert into account_account_tag_account_move_line_rel (account_move_line_id,account_account_tag_id)
        select l.id, x.account_account_tag_id
        from account_move_line l join account_move m on m.id=l.move_id
        join account_move_line_account_tax_rel t on t.account_move_line_id=l.id
        join account_tax_repartition_line r on r.tax_id=t.account_tax_id and r.repartition_type='base'
            and r.document_type=case when m.move_type in ('out_refund','in_refund') then 'refund' else 'invoice' end
        join account_account_tag_account_tax_repartition_line_rel x on x.account_tax_repartition_line_id=r.id
        where l.display_type='product'
        union
        select l.id, x.account_account_tag_id
        from account_move_line l join account_account_tag_account_tax_repartition_line_rel x on x.account_tax_repartition_line_id=l.tax_repartition_line_id;
    """
    cr_dst.execute(SQL)
    cnx_dst.commit()

    # Lettrages partiels (3) : montants en devise (EUR) ajoutés en v13
    MigrationTable(db_src,db_dst,'account_partial_reconcile')
    cr_dst.execute("""
        update account_partial_reconcile set debit_currency_id=%s, credit_currency_id=%s,
            debit_amount_currency=amount, credit_amount_currency=amount
    """,[eur,eur])
    cnx_dst.commit()

    # Pièce des paiements ; factures liées aux paiements (account_invoice_payment_rel, 5)
    for piece,paiement in paiement_piece.items():
        cr_dst.execute("update account_payment set move_id=%s where id=%s",[piece,paiement])
    cr_src.execute("select invoice_id,payment_id from account_invoice_payment_rel")
    execute_values(cr_dst,"insert into account_move__account_payment (invoice_id,payment_id) values %s",
        [(row['invoice_id'],row['payment_id']) for row in cr_src.fetchall()])
    cnx_dst.commit()

    # Contrôle : nombre de pièces et de lignes, total débit = total crédit par pièce
    cr_dst.execute("select move_type, count(*) as nb from account_move group by 1 order by 1")
    print("Pièces : %s"%{row['move_type']:row['nb'] for row in cr_dst.fetchall()})
    cr_dst.execute("select display_type, count(*) as nb from account_move_line group by 1 order by 1")
    print("Lignes : %s"%{row['display_type']:row['nb'] for row in cr_dst.fetchall()})
    cr_dst.execute("select move_id from account_move_line group by move_id having sum(debit)<>sum(credit)")
    desequilibres = [row['move_id'] for row in cr_dst.fetchall()]
    if desequilibres:
        print("Pièces déséquilibrées : %s"%desequilibres)
    #******************************************************************************


# ** Contrôle (lecture seule) **************************************************
# Clés étrangères qui ne pointent sur rien (tables copiées sans contrôle des clés)
ControleOrphelins(db_dst)
#******************************************************************************
