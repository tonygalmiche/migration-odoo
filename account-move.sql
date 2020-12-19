

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



select 
 aml.id,
 am.partner_id,
 aml.move_id,
 am.state,
 aml.debit,
 aml.credit,
 ai.number
from 
    account_move_line aml left outer join account_move am on aml.move_id=am.id 
                          left outer join account_invoice ai on am.id=ai.move_id
where aml.id>0
order by aml.id;
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

select * from account_move_reconcile;
