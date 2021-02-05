


SELECT
    invoice.id invoice_id,
    invoice.name,
    invoice.move_type,
    invoice.amount_total,
    line.id line_id,
    line.debit,
    line.credit
FROM account_move invoice join account_move_line line on invoice.id=line.move_id
                          join account_partial_reconcile part on (line.id=part.debit_move_id or line.id=part.credit_move_id)
WHERE invoice.id=7168;


SELECT
    payment.id,
    payment.move_id,
    payment.payment_type,
    payment.amount,
    line.id line_id,
    line.debit,
    line.credit,
    account.code,
    account.internal_type,
    line.name
FROM account_payment payment join account_move_line line on payment.move_id=line.move_id
                             join account_account account on line.account_id=account.id and account.internal_type IN ('receivable', 'payable')
WHERE payment.id=5373;


SELECT
    move.id move_id,
    move.name,
    move.move_type,
    move.amount_total,
    line.id line_id,
    line.debit,
    line.credit
FROM account_move move join account_move_line line on move.id=line.move_id
                       join account_partial_reconcile part on (line.id=part.debit_move_id or line.id=part.credit_move_id)
WHERE move.id=7282;


SELECT
    id,
    debit_move_id,
    credit_move_id,
    amount
FROM account_partial_reconcile part 
WHERE id=5444;

--SELECT
--    payment.id,
--    ARRAY_AGG(DISTINCT invoice.id) AS invoice_ids,
--    invoice.move_type
--FROM account_payment payment
--JOIN account_move move ON move.id = payment.move_id
--JOIN account_move_line line ON line.move_id = move.id
--JOIN account_partial_reconcile part ON
--    part.debit_move_id = line.id
--    OR
--    part.credit_move_id = line.id
--JOIN account_move_line counterpart_line ON
--    part.debit_move_id = counterpart_line.id
--    OR
--    part.credit_move_id = counterpart_line.id
--JOIN account_move invoice ON invoice.id = counterpart_line.move_id
--JOIN account_account account ON account.id = line.account_id
--WHERE account.internal_type IN ('receivable', 'payable')
--    AND payment.id in (5300,5373)
--    AND line.id != counterpart_line.id
--    AND invoice.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
--GROUP BY payment.id, invoice.move_type


--SELECT
--    payment.id,
--    line.id,
--    line.name,
--    line.debit,
--    line.credit,
--    part.id part_id
--FROM account_payment payment
--JOIN account_move move ON move.id = payment.move_id
--JOIN account_move_line line ON line.move_id = move.id


--JOIN account_partial_reconcile part ON
--    part.debit_move_id = line.id
--    OR
--    part.credit_move_id = line.id


----JOIN account_move_line counterpart_line ON
----    part.debit_move_id = counterpart_line.id
----    OR
----    part.credit_move_id = counterpart_line.id
----JOIN account_move invoice ON invoice.id = counterpart_line.move_id
----JOIN account_account account ON account.id = line.account_id
--WHERE
--    payment.id in (5300,5373) 
----    line.id != counterpart_line.id 


