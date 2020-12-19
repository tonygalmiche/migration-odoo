



-- update account_move_line set exclude_from_invoice_tab='t';
-- update account_move_line set exclude_from_invoice_tab='f' where product_id is not null;


select ai.number,ail.id,ail.name,ail.product_id,ail.quantity 
from account_invoice ai inner join account_invoice_line ail on ai.id=ail.invoice_id 
where ai.move_id=7150 order by ail.id;

--    number   |  id  |                                  name                                  | product_id | quantity 
-- ------------+------+------------------------------------------------------------------------+------------+----------
--  20-12-1251 | 7330 | BON COMMANDE N° 2020-00001525                                         +|          3 |    1.000
--             |      | N° ENGAGEMENT CHORUS PRO : C20201490                                  +|            | 
--             |      | Service : P03r-41-Formation                                           +|            | 
--             |      |                                                                        |            | 
--  20-12-1251 | 7331 | ACOMPTE 50 % à la signature du contrat de prestations n° AF0412       +|          3 |    0.500
--             |      | FACTURE 19-11-1045 du 27/11/19                                         |            | 




select ai.number,l.id,l.product_id,l.name,l.debit,l.credit,l.tax_amount,l.quantity 
from account_move_line l inner join account_invoice ai on l.move_id=ai.move_id 
where product_id is not null and l.move_id=7150;

--    number   |  id   | product_id |                              name                               |  debit  | credit  | tax_amount | quantity 
-- ------------+-------+------------+-----------------------------------------------------------------+---------+---------+------------+----------
--  20-12-1251 | 20417 |          3 | BON COMMANDE N° 2020-00001525                                   |    0.00 | 4800.00 |    4800.00 |     1.00
--  20-12-1251 | 20418 |          3 | ACOMPTE 50 % à la signature du contrat de prestations n° AF0412 | 2400.00 |    0.00 |   -2400.00 |     0.50



select count(*)
from account_move_line l inner join account_invoice ai on l.move_id=ai.move_id 
where product_id is not null;


select count(*)
from account_invoice ai inner join account_invoice_line ail on ai.id=ail.invoice_id where ai.state not in ('cancel');




select *
from account_invoice ai inner join account_invoice_line ail on ai.id=ail.invoice_id 
where ai.move_id=7150 order by ail.id;

select *
from account_move_line l inner join account_invoice ai on l.move_id=ai.move_id 
where product_id is not null and l.move_id=7150;




-- select 
--     ai.id,
--     ai.number,
--     ai.name,
--     ai.move_id 
-- from account_invoice ai inner join account_move am on ai.move_id=am.id 
-- where ai.id>0
-- order by ai.id;


-- select 
--     id,
--     product_id
-- from account_invoice_line 
-- where id>0
-- order by id;


-- select 
--     *
-- from account_move_line 
-- where id>0
-- order by id;



-- select 
--  aml.id,
--  am.partner_id,
--  aml.move_id,
--  am.state,
--  aml.debit,
--  aml.credit,
--  ai.number
-- from 
--     account_move_line aml left outer join account_move am on aml.move_id=am.id 
--                           left outer join account_invoice ai on am.id=ai.move_id
-- where aml.id>0
-- order by aml.id;
--limit 10

-- id | create_date | statement_id | company_id | currency_id | date_maturity | partner_id | reconcile_partial_id | blocked | 
-- analytic_account_id | create_uid | credit | centralisation | journal_id | reconcile_ref | tax_code_id | state | debit | ref | 
-- account_id | period_id | write_date | date_created | date | write_uid | move_id | name | reconcile_id | tax_amount | product_id | 
-- account_tax_id | product_uom_id | amount_currency | quantity | id | create_uid | partner_id | create_date | name | company_id | 
-- write_uid | journal_id | state | period_id | write_date | narration | date | balance | ref | to_check 


-- select * from account_invoice_line where id=0;
-- id | origin | uos_id | account_id | sequence | invoice_id | price_unit | price_subtotal | company_id | 
-- discount | product_id | account_analytic_id | partner_id | quantity | name | purchase_line_id | is_affaire_id 


--select * from account_move_line where id=0;
-- id | statement_id | company_id | currency_id | date_maturity | partner_id | reconcile_partial_id | blocked | 
-- analytic_account_id | credit | centralisation | journal_id | reconcile_ref | tax_code_id | state | debit | ref | 
-- account_id | period_id | date_created | date | move_id | name | reconcile_id | tax_amount | product_id | 
-- account_tax_id | product_uom_id | amount_currency | quantity 

-- select * from account_move_reconcile;
