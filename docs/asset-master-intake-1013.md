# Automatic Item Master asset registration

An active BUY item classified FIXED_ASSET automatically receives a linked
Fixed Asset record in the same transaction. The item requires an active posting
DEBIT ASSET account under 100-600 or 100-900. The master registration is unique
per item while pending and uses `FA-ITEM-<product id>` as its stable register number.

Master-only intake is PENDING_REGISTRATION: acquisition date, acquisition cost
and book value remain unknown. The catalogue can establish the business unit
when a unique active Hotel/Project Catering unit exists; it does not establish
an acquisition location or department. No item reference price is treated as
owned asset value. No quantity, acquisition movement, journal or depreciation
is generated from the Item Master list.

Complete Registration supplies actual acquisition date/cost, organization,
category and depreciation configuration. The same record becomes DRAFT;
capitalization and depreciation use the existing explicit finance workflow.
An invoice linked to the item completes its pending record using its actual
source data instead of adding a duplicate. Later separate acquisitions retain
the existing per-invoice-line registration behavior.

Hotel linen, chinaware, silverware and glassware map respectively to the four
100-900-100..103 operating-equipment COAs. Master taxonomy uses the existing
ASSET/FURNITURE family (FF&E); no new Item Master subgroup is introduced.
The XLS reader maps identifiable source linen/tableware, deferring uncertain
material and duplicate/unit cases. Those new Hotel asset items also register
pending automatically. The previously seeded stock items remain untouched.

Migration `20261013_asset_master_intake` permits missing details only for pending
registrations, guarded by a check constraint and a pending-product unique index.
It does not insert or adjust any balance. Apply the migration on EC2 before
merging the backend branch that triggers Lambda deployment.

After deployment, complete category configuration (useful life, residual and
posting accounts) explicitly; the source list supplies no depreciation policy.
