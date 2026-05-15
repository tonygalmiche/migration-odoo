#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from migration_fonction import *
import os
import json


#** Paramètres ****************************************************************
db_src = "odoo-agenda14"
db_dst = "odoo-agenda19"
#******************************************************************************


# #** Permet de repartir sur une base vierge si la migration échoue *************
# db_vierge = db_dst+'-vierge'
# SQL='DROP DATABASE \"'+db_dst+'\";CREATE DATABASE \"'+db_dst+'\" WITH TEMPLATE \"'+db_vierge+'\"'
# cde="""echo '"""+SQL+"""' | psql postgres"""
# lines=os.popen(cde).readlines() #Permet de repartir sur une base vierge si la migration échoue
# # rsync -rva --delete /media/sf_dev_odoo/home/odoo/filestore/infosaone19-vierge/ /media/sf_dev_odoo/home/odoo/filestore/infosaone19
# #******************************************************************************


cnx_src,cr_src=GetCR(db_src)
cnx_dst,cr_dst=GetCR(db_dst)





# ** Tables diverses **********************************************************
tables=[
    "res_partner",
    "res_users",
    "calendar_recurrence",
    "calendar_event_res_partner_rel",
    "calendar_event_res_partner_refusee",
    "calendar_event_res_partner_acceptee",
    "calendar_event",
    "calendar_attendee",
    "calendar_alarm_calendar_event_rel",
]
for table in tables:
    MigrationTable(db_src,db_dst,table)


# ** Conversion du champ weekday de calendar_recurrence ************************
# Odoo 14 utilise 2 lettres (MO, TU, WE, TH, FR, SA, SU)
# Odoo 19 utilise 3 lettres (MON, TUE, WED, THU, FRI, SAT, SUN)
weekday_mapping = {
    'MO': 'MON',
    'TU': 'TUE',
    'WE': 'WED',
    'TH': 'THU',
    'FR': 'FRI',
    'SA': 'SAT',
    'SU': 'SUN',
}
for old_val, new_val in weekday_mapping.items():
    cr_dst.execute(
        "UPDATE calendar_recurrence SET weekday = %s WHERE weekday = %s",
        (new_val, old_val)
    )
cr_dst.connection.commit()
#******************************************************************************


# ** Migration des couleurs du calendrier vers res_partner *********************
# Dans Odoo 14, la couleur était déterminée par une fonction getColor custom
# dans calendar_renderer.js qui mappait les user_id (pas partner_id!) vers des
# index couleurs 1-29. Le calendrier v14 utilisait color="user_id".
# Logique : roulement cyclique ((user_id-1) % 29) + 1, avec exception user_id 26 → 4 (Céline).
# Dans Odoo 19, on stocke la couleur dans is_calendar_color de res_partner (56 couleurs).

def get_v14_color(user_id):
    """Reproduit la logique exacte du getColor custom d'Odoo 14.
    La clé est le user_id. Roulement cyclique sur 1-29, sauf user_id 26 → 4 (Céline)."""
    if not user_id or user_id <= 0:
        return 1
    if user_id == 26:  # Céline FRANZINI (user_id=26, partner_id=27)
        return 4
    return ((user_id - 1) % 29) + 1

# Mapping v14_color_index → v19_color_index (couleur la plus proche visuellement)
V14_TO_V19_COLOR = {
    1: 1,    # #F06050 (rouge/corail)    → #ee2d2d (rouge)
    2: 6,    # #F4A460 (brun sable)      → #db8865 (brun/orange)
    3: 15,   # #F7CD1F (jaune)           → #F7CD1F (exact)
    4: 4,    # #6CC1ED (bleu clair)      → #5794dd (bleu)
    5: 5,    # #814968 (mauve foncé)     → #9f628f (mauve)
    6: 27,   # #EB7E7F (rose clair)      → #b56969 (rose)
    7: 7,    # #2C8397 (sarcelle)        → #41a9a2 (sarcelle)
    8: 8,    # #475577 (bleu acier)      → #304be0 (bleu)
    9: 18,   # #D6145F (rose foncé)      → #D6145F (exact)
    10: 13,  # #30C381 (vert)            → #30C381 (exact)
    11: 11,  # #9365B8 (violet)          → #9872e6 (violet)
    12: 12, 13: 13, 14: 14, 15: 15, 16: 16, 17: 17, 18: 18, 19: 19,
    20: 20, 21: 21, 22: 22, 23: 23, 24: 24, 25: 25, 26: 26, 27: 27,
    28: 28, 29: 29,
}

# Récupérer tous les participants du calendrier avec leur user_id
cr_dst.execute("""
    SELECT DISTINCT rp.id as partner_id, ru.id as user_id
    FROM res_partner rp
    JOIN calendar_event_res_partner_rel rel ON rel.res_partner_id = rp.id
    LEFT JOIN res_users ru ON ru.partner_id = rp.id
""")
rows = cr_dst.fetchall()

for row in rows:
    partner_id = row['partner_id']
    user_id = row['user_id']
    if user_id:
        v14_color = get_v14_color(user_id)
        v19_color = V14_TO_V19_COLOR.get(v14_color, v14_color)
    else:
        # Partenaire sans user (contact externe) : couleur auto
        v19_color = 0
    cr_dst.execute(
        "UPDATE res_partner SET is_calendar_color = %s WHERE id = %s",
        (v19_color, partner_id)
    )
cr_dst.connection.commit()


# ** calendar_contacts => calendar_filters ************************************
rename={
}
default={
}
MigrationTable(db_src,db_dst,'calendar_contacts', table_dst='calendar_filters', rename=rename,default=default)
#******************************************************************************


# ** calendar_alarm => JSON ************************************
MigrationTable(db_src,db_dst,'calendar_alarm',text2jsonb=True)
#******************************************************************************

#** res_company ***************************************************************
MigrationDonneesTable(db_src,db_dst,'res_company')
#******************************************************************************



#** res_groups ****************************************************************
MigrationTable(db_src,db_dst,'res_company_users_rel')
MigrationResGroups(db_src,db_dst)
#****************************************************************************


#** mail ****************************************************************
tables = [
    # "message_attachment_rel",   # => La clé (attachment_id)=(6804) n'est pas présente dans la table « ir_attachment 
    "mail_tracking_value",
    "mail_message_res_partner_rel",
    "mail_message",
    "mail_mail_res_partner_rel",
    "mail_mail",
    "mail_followers_mail_message_subtype_rel",
    "mail_alias",
]

for table in tables:
    print(table)
    MigrationTable(db_src,db_dst,table)
#****************************************************************************


# # ** mail_template ************************************************************

# ERREUR:  une instruction insert ou update sur la table « mail_template » viole la contrainte de clé
# étrangère « mail_template_model_id_fkey »
# DÉTAIL : La clé (model_id)=(302) n'est pas présente dans la table « ir_model ».

# MigrationTable(db_src,db_dst,'mail_template',text2jsonb=True)
# #******************************************************************************



# # ** Conversion syntaxe ${...} => {{ ... }} dans mail_template ****************
# # Odoo 14 utilise la syntaxe Mako ${...}, Odoo 19 utilise inline_template {{ ... }}
# cr_dst.execute("""
#     UPDATE mail_template 
#     SET lang = REGEXP_REPLACE(lang, '\\$\\{([^}]+)\\}', '{{ \\1 }}', 'g')
#     WHERE lang LIKE '%${%}'
# """)
# cr_dst.connection.commit()
# #******************************************************************************







# ** mail_message_subtype *****************************************************
MigrationTable(db_src,db_dst,'mail_message_subtype',text2jsonb=True)
#******************************************************************************



# ** mail_message_res_partner_needaction_rel => mail_notification *************
rename={
}
default={
}
MigrationTable(db_src,db_dst,'mail_message_res_partner_needaction_rel', table_dst='mail_notification', rename=rename,default=default)
#******************************************************************************



# ** calendar_contacts => calendar_filters ************************************
default={
    'partner_id': 2,
}
MigrationTable(db_src,db_dst,'mail_followers',default=default)
#******************************************************************************


# ** mail_channel_res_groups_rel => discuss_channel_res_groups_rel ************************************
rename={
    'mail_channel_id': 'discuss_channel_id',
}
default={
}
MigrationTable(db_src,db_dst,'mail_channel_res_groups_rel', table_dst='discuss_channel_res_groups_rel', rename=rename,default=default)
#******************************************************************************



# ** mail_channel_partner => discuss_channel_member ************************************
rename={
}
default={
    'new_message_separator': 0,
}
MigrationTable(db_src,db_dst,'mail_channel_partner', table_dst='discuss_channel_member', rename=rename,default=default)
#******************************************************************************


# La table mail_message_mail_channel_rel n'existe plus dans Odoo 19
# Explication
# Dans Odoo 14, la table mail_message_mail_channel_rel était une table de relation Many2Many qui liait les messages (mail.message) aux canaux (mail.channel).

# Dans Odoo 19, cette approche a été complètement restructurée :

# Le modèle mail.channel a été renommé en discuss.channel
# La relation M2M a été supprimée - les messages sont maintenant liés aux canaux via les champs standards model et res_id de mail.message
# Un champ calculé channel_id a été ajouté sur mail.message :


# ** mail_channel => discuss_channel ******************************************
# Note: group_public_id doit être NULL sauf pour channel_type='channel' (contrainte Odoo 19)
# On désactive temporairement la contrainte, on migre, puis on corrige et réactive

# Désactiver la contrainte
cr_dst.execute("ALTER TABLE discuss_channel DROP CONSTRAINT IF EXISTS discuss_channel_group_public_id_check")
cr_dst.connection.commit()

# Migration
MigrationTable(db_src, db_dst, 'mail_channel', table_dst='discuss_channel')

# Correction : mettre group_public_id à NULL pour les canaux qui ne sont pas de type 'channel'
cr_dst.execute("UPDATE discuss_channel SET group_public_id = NULL WHERE channel_type != 'channel'")
cr_dst.connection.commit()

# Réactiver la contrainte
cr_dst.execute("ALTER TABLE discuss_channel ADD CONSTRAINT discuss_channel_group_public_id_check CHECK (channel_type = 'channel' OR group_public_id IS NULL)")
cr_dst.connection.commit()
#******************************************************************************


# ** mail_activity_type (champs traduisibles en JSONB) ************************
# chaining_type est nouveau et obligatoire en v19 (valeurs: 'suggest' ou 'trigger')
MigrationTable(db_src, db_dst, 'mail_activity_type', text2jsonb=True, 
               default={'chaining_type': 'suggest'})
#******************************************************************************






# ** web_m2x_options : paramètres système *************************************
web_m2x_params = [
    ('web_m2x_options.create',      'False'),
    ('web_m2x_options.create_edit', 'False'),
    ('web_m2x_options.limit',       '10'),
]
for key, value in web_m2x_params:
    cr_dst.execute("""
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, %s, 1, 1, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING
    """, (key, value))
cr_dst.connection.commit()
#******************************************************************************



# ** Désactivation des contacts sans utilisateur associé **********************
cr_dst.execute("""
    UPDATE res_partner
    SET active = FALSE
    WHERE id NOT IN (SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL)
    AND active = TRUE
""")
cr_dst.connection.commit()
#******************************************************************************


# ** Recalcul de complete_name sur res_partner *********************************
# Logique identique à _get_complete_name() d'Odoo 19 :
#   - Société ou contact sans parent ni company_name : complete_name = name
#   - Contact avec parent : complete_name = "Nom société parente, nom"
#   - Contact avec company_name sans parent : complete_name = "company_name, nom"
cr_dst.execute("""
    UPDATE res_partner p
    SET complete_name = CASE
        WHEN p.is_company OR (p.parent_id IS NULL AND COALESCE(p.company_name, '') = '')
            THEN COALESCE(TRIM(p.name), '')
        WHEN p.parent_id IS NOT NULL
            THEN TRIM(
                COALESCE(
                    (SELECT name FROM res_partner WHERE id = p.parent_id),
                    p.company_name,
                    ''
                ) || ', ' || COALESCE(p.name, '')
            )
        ELSE TRIM(p.company_name || ', ' || COALESCE(p.name, ''))
    END
""")
cr_dst.connection.commit()
#******************************************************************************




# Correction manuelle : Pour me mettre en vert (couleur 47)
cr_dst.execute("""
    UPDATE res_partner SET is_calendar_color = 47 WHERE id=7
""")
cr_dst.connection.commit()
#******************************************************************************


# ** Suppression des orphelins dans message_attachment_rel ********************
# Supprime les lignes dont le message_id n'existe plus dans mail_message
cr_dst.execute("""
    DELETE FROM message_attachment_rel
    WHERE NOT EXISTS (
        SELECT 1 FROM mail_message WHERE id = message_attachment_rel.message_id
    )
""")
cr_dst.connection.commit()
#******************************************************************************


# =============================================================================
# PROBLÈME RENCONTRÉ APRÈS COPIE SUR SERVEUR DE PROD (25/04/2026)
# =============================================================================
# Symptôme : page de login inaccessible, écran blanc sans formulaire.
# Erreur dans les logs Odoo :
#   FileNotFoundError: [Errno 2] Aucun fichier ou dossier de ce nom:
#   '/home/odoo/.local/share/Odoo/filestore/odoo19-agenda/3b/3bfec11ea...'
#
# Cause :
#   1. Le filestore n'a pas été copié sur le serveur de prod.
#   2. Les assets web (JS/CSS) sont stockés comme ir.attachment avec un fichier
#      physique dans le filestore. Sans ce fichier, le chargement de la page
#      de login plante (asset web.assets_frontend_lazy.min.js introuvable).
#
# Solution en 2 étapes :
#
#   Étape 1 - Débloquer la connexion (supprimer les assets en cache) :
#     DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
#     Puis redémarrer Odoo → les assets sont regénérés automatiquement.
#
#   Étape 2 - Copier le filestore complet depuis la machine locale :
#     rsync -rva /home/odoo/.local/share/Odoo/filestore/odoo19-agenda/ \
#         user@prod:/home/odoo/.local/share/Odoo/filestore/odoo19-agenda/
# =============================================================================

