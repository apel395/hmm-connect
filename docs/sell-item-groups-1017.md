# Selling item groups and codes

Hotel Sell Items offers Food, Beverage, Room and Service. Catering Sell Items offers Food, Beverage and Service (Jasa). Both use a group only, with no selling subgroup.

New automatic codes use the selected group code, a hyphen and a six-digit sequence, for example `S-FOOD-000001`, `S-BEV-000001`, `S-ROOM-000001` and `S-SERVICE-000001`. Configured selling group codes take precedence over defaults. Sequences share the existing globally unique Item Master code namespace; previews do not reserve a number and saving allocates under the existing transaction lock.

The classification API accepts `item_type` and `catalog_type`. Code previews use the same catalog; the API rejects selling subgroups and Catering Room items. The SELL catalog omits subgroup options, including legacy configured subgroup options. Existing item codes are retained on edits; explicit Item Master edits clear legacy SELL subgroup metadata. No bulk rewriting of existing products is performed.

The Catering selling form retains service, business unit, location, editable price, PBJT/PPN alternatives, PPh 23 and service charge. This change does not set tax eligibility or tax rates automatically.

BUY groups, subgroups and classification-based numbering are unchanged. No database migration or EC2 correction is needed.
