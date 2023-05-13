do $$
  declare r record;
BEGIN
FOR r IN  (
  SELECT FORMAT(
    'UPDATE pg_constraint SET convalidated=false WHERE conname = ''%I''; ALTER TABLE %I VALIDATE CONSTRAINT %I;',
    tc.constraint_name,
    tc.table_name,
    tc.constraint_name
  ) AS x
  FROM information_schema.table_constraints AS tc
  JOIN information_schema.tables t ON t.table_name = tc.table_name and t.table_type = 'BASE TABLE'
  JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
  -- JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name => Cette table allonge enormement le temps de traitement sans rien changer au résultat
  WHERE  
    constraint_type = 'FOREIGN KEY' AND
    tc.constraint_schema = 'public' AND
    tc.constraint_name not in ('stock_rule_route_id_fkey',' is_mode_operatoire_menu_menu_id_fkey') AND
    tc.table_name not in ('is_mode_operatoire_menu')
)
  LOOP
    EXECUTE (r.x);
  END LOOP;
END;
$$;


--  SELECT 
--    tc.constraint_name,
--    tc.table_name,
--    tc.constraint_name
--  FROM information_schema.table_constraints AS tc
--  JOIN information_schema.tables t ON t.table_name = tc.table_name and t.table_type = 'BASE TABLE'
--  JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
--  JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
--  WHERE  constraint_type = 'FOREIGN KEY'
--    AND tc.constraint_schema = 'public'



-- update pg_constraint set convalidated = false where conname = 'stock_rule_route_id_fkey' and conrelid = 'stock_rule'::regclass;
-- alter table stock_rule validate constraint stock_rule_route_id_fkey;



-- SELECT tc.constraint_name, tc.table_name
-- FROM information_schema.table_constraints AS tc JOIN information_schema.tables t ON t.table_name = tc.table_name and t.table_type = 'BASE TABLE'
--                                                 JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
--                                                 -- JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name TODO : Très long en ajoutant cette table
-- WHERE  constraint_type = 'FOREIGN KEY' AND tc.constraint_schema = 'public'
-- 3212 lignes dans pg-odoo16-0 => Même résultat avec le JOIN constraint_column_usage => Donc pas necessaire
