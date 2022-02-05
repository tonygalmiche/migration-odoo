
            SELECT
                line.id,
--                line.move_id,
--                line.product_id,
--                line.account_id,
--                line.analytic_account_id,
--                line.journal_id,
--                line.company_id,
--                line.company_currency_id,
--                line.partner_id AS commercial_partner_id,
--                move.state,
--                move.move_type,
--                move.partner_id,
--                move.invoice_user_id,
--                move.fiscal_position_id,
--                move.payment_state,
--                move.invoice_date,
--                move.invoice_date_due,
--                uom_template.id                                             AS product_uom_id,
--                template.categ_id                                           AS product_categ_id,

--                line.quantity,

                uom_line.factor,
                uom_template.factor,
                move.move_type,
                line.balance,


                line.quantity / NULLIF(COALESCE(uom_line.factor, 1) / COALESCE(uom_template.factor, 1), 0.0) * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS quantity,
                -line.balance                          AS price_subtotal,
                -COALESCE(
                   -- Average line price
                   (line.balance / NULLIF(line.quantity, 0.0))
                   -- convert to template uom
                   * (NULLIF(COALESCE(uom_line.factor, 1), 0.0) / NULLIF(COALESCE(uom_template.factor, 1), 0.0)),
                   0.0)                                AS price_average,
                COALESCE(partner.country_id, commercial_partner.country_id) AS country_id





            FROM account_move_line line
                LEFT JOIN res_partner partner ON partner.id = line.partner_id
                LEFT JOIN product_product product ON product.id = line.product_id
                LEFT JOIN account_account account ON account.id = line.account_id
                LEFT JOIN account_account_type user_type ON user_type.id = account.user_type_id
                LEFT JOIN product_template template ON template.id = product.product_tmpl_id
                LEFT JOIN uom_uom uom_line ON uom_line.id = line.product_uom_id
                LEFT JOIN uom_uom uom_template ON uom_template.id = template.uom_id
                INNER JOIN account_move move ON move.id = line.move_id
                LEFT JOIN res_partner commercial_partner ON commercial_partner.id = move.commercial_partner_id
--                JOIN {currency_table} ON currency_table.company_id = line.company_id

--            currency_table=self.env['res.currency']._get_query_currency_table({'multi_company': True, 'date': {'date_to': fields.Date.today()}}),



            WHERE move.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
                AND line.account_id IS NOT NULL
                AND NOT line.exclude_from_invoice_tab

 and line.move_id in (1486,1518)

