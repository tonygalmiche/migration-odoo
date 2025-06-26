import psycopg2
import sys

# --- Paramètres à configurer ---
SOURCE_DB = "opta-s18"
DEST_DB = "sgp18"
TABLE_NAME = 'ir_attachment'

# 👇 Remplacez l'ID par une clause WHERE complète.
# Assurez-vous d'échapper correctement les apostrophes si nécessaire.
WHERE_CLAUSE = "name='res.company.scss'"


def copy_records_by_where_clause():
    """
    Copie plusieurs enregistrements d'une base à une autre
    en se basant sur une clause WHERE.
    """
    source_conn = None
    dest_conn = None
    try:
        # --- Connexion simplifiée aux bases de données ---
        source_conn = psycopg2.connect(dbname=SOURCE_DB)
        dest_conn = psycopg2.connect(dbname=DEST_DB)

        source_cur = source_conn.cursor()

        # 1. Récupérer dynamiquement la liste des colonnes (sauf 'id')
        source_cur.execute("""
            SELECT array_agg(column_name::text ORDER BY ordinal_position)
            FROM information_schema.columns
            WHERE table_name = %s AND column_name <> 'id';
        """, (TABLE_NAME,))
        
        result = source_cur.fetchone()
        if not result or not result[0]:
            print(f"❌ Erreur: Aucune colonne trouvée pour la table '{TABLE_NAME}'.")
            return
            
        columns_to_copy = result[0]
        columns_str = ", ".join(columns_to_copy)

        # 2. Récupérer TOUS les enregistrements correspondants avec fetchall()
        # La clause WHERE est injectée ici. Voir l'avertissement de sécurité plus bas.
        select_query = f"SELECT {columns_str} FROM {TABLE_NAME} WHERE {WHERE_CLAUSE}"
        source_cur.execute(select_query)
        
        # fetchall() récupère toutes les lignes correspondantes dans une liste de tuples
        source_data_list = source_cur.fetchall()
        
        if not source_data_list:
            print(f"ℹ️ Aucun enregistrement trouvé avec la clause : {WHERE_CLAUSE}")
            return
            
        print(f"✅ {len(source_data_list)} enregistrement(s) trouvé(s) et prêt(s) à être copiés.")
        source_cur.close()

        # 3. Insérer tous les enregistrements en une seule fois avec executemany()
        dest_cur = dest_conn.cursor()
        placeholders = ", ".join(['%s'] * len(columns_to_copy))
        insert_query = f"INSERT INTO {TABLE_NAME} ({columns_str}) VALUES ({placeholders})"
        
        # executemany est très performant pour l'insertion en masse
        dest_cur.executemany(insert_query, source_data_list)
        
        dest_conn.commit()
        print(f"🚀 {dest_cur.rowcount} enregistrement(s) copié(s) avec succès dans la base de destination.")
        dest_cur.close()

    except psycopg2.Error as e:
        print(f"❌ Erreur de base de données : {e}", file=sys.stderr)
        if dest_conn:
            dest_conn.rollback() # Annuler la transaction en cas d'erreur
    finally:
        if source_conn:
            source_conn.close()
        if dest_conn:
            dest_conn.close()

if __name__ == '__main__':
    copy_records_by_where_clause()
