# POS revenue choice and Item Master sales context

The menu location and department controls only filter the catalog. Choosing another filter does not clear or retag the order. Selected menus carry their Item Master location, business unit, catalog and department; the API independently derives and validates these dimensions. Menus with incompatible locations, departments or catalogs require separate orders. Shared menus have a separate order location/department selector. Account login access still applies on both lookup and posting.

Choose the revenue account on the order. Only active credit-balance operating revenue posting accounts are available: Hotel uses 400-100 descendants, Catering uses 400-110 descendants. The legacy posting account 400, if it exists, remains compatible. Nonoperating revenue 760, expenses, headers and the other unit's revenue are excluded. A selected account is saved on the draft and used at posting; old drafts may choose an account in the Sales detail dialog. The existing global setting is a fallback for older clients, validated against the actual sale unit. PBJT remains a separate liability credit.

A saved draft is reused after a posting failure, including after browser refresh. Retrying invoice metadata retains the invoice number. Successful posting or explicit clearing removes the local recovery input. Clearing a saved order does not silently delete its server draft; it remains in Sales for review/void.

Apply 20261022_pos_revenue on EC2 and run scripts/check_pos_revenue_1022.py. The migration adds one nullable revenue-account FK; it does not change existing journals, mappings, balances or Item Master data.
