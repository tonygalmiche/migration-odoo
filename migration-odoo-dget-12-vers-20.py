#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Reprise des données de DGET : Odoo 12 (is_dget) => Odoo 20 (is_dget20)
# Documentation : Documentation/migration-odoo/migration-is_dget12-vers-is_dget20.md
# Étape 1 : contacts, utilisateurs, société, unités, articles, conditions de paiement, tables du module qui ne dépendent
# pas de la comptabilité
# Étape 2 : comptabilité (plan comptable, taxes, positions fiscales, journaux, propriétés)
# Étape 3 : tables du module liées à la comptabilité (TVA DGET, contrats, lignes de contrats, heures)
# A faire ensuite : factures (account_invoice v12 => account_move), paiements, pièces jointes, chatter, filtres
from migration_fonction import *
from psycopg2.extras import execute_values
import atexit


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


# ** Contrôle (lecture seule) **************************************************
# Clés étrangères qui ne pointent sur rien (tables copiées sans contrôle des clés)
ControleOrphelins(db_dst)
#******************************************************************************
