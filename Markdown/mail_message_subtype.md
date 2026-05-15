# Bug : label "Contrat en attente" dans tous les chats — résidu de migration Odoo 8 → 16

## Symptôme

Toutes les entrées du chatter Odoo affichent un label parasite ("Contrat en attente" ou
"Contrat à renouveler") en titre ou en badge, sur **tous les modèles** de la base.

## Cause

Dans Odoo 16, la méthode `_message_log()` (utilisée pour tous les logs de tracking) écrit :

```python
'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
```

Après la migration depuis Odoo 8, l'entrée `ir_model_data` pour `mail.mt_note` pointe vers
le mauvais enregistrement :

| ir_model_data (module=mail, name=mt_note) | → | mail_message_subtype.id=2 |
|---|---|---|
| Devrait pointer vers | | `{"en_US": "Note", "fr_FR": "Note"}` (pas de res_model) |
| Pointe en réalité vers | | `{"en_US": "Contrat à renouveler"}` res_model=account.analytic.account |

## Diagnostic SQL

```sql
-- Vérifier le mauvais mapping
SELECT d.name, d.res_id, s.name as subtype_name, s.res_model
FROM ir_model_data d
JOIN mail_message_subtype s ON s.id = d.res_id
WHERE d.module='mail' AND d.name IN ('mt_note','mt_comment');
-- Résultat : mt_note → id=2 "Contrat à renouveler" (account.analytic.account)  ← FAUX
--            mt_comment → id=1 "Discussions"                                    ← OK
```

## Correction (à exécuter en psql sur pg-odoo16-1)

### Étape 1 — Créer le bon subtype mt_note

```sql
BEGIN;

INSERT INTO mail_message_subtype
    (name, internal, "default", hidden, sequence, create_uid, write_uid, create_date, write_date)
VALUES
    ('{"en_US": "Note", "fr_FR": "Note"}', true, false, false, 0, 1, 1, NOW(), NOW())
RETURNING id;
```

Noter l'id retourné (ex: **24**).

### Étape 2 — Corriger la référence et les messages existants

```sql
-- Corriger le pointeur mail.mt_note (remplacer 24 par l'id retourné)
UPDATE ir_model_data SET res_id = 24 WHERE module='mail' AND name='mt_note';

-- Optionnel : corriger les anciens messages qui ont le mauvais subtype
UPDATE mail_message SET subtype_id = 24 WHERE subtype_id = 2;

COMMIT;
```

### Étape 3 — Redémarrer Odoo

Nécessaire pour vider le cache ORM de `ir.model.data`.

## Résultat attendu

Les nouveaux logs de tracking n'afficheront plus aucun label parasite.
Le subtype "Note" (interne, caché) ne s'affiche pas dans le chatter, ce qui est le
comportement normal d'Odoo 16.
