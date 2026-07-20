# Identity Context Update

This snapshot adds the ERP identity context used by the audit trail.

## Audit identity snapshot

Every new audit event stores the context that existed when the event was created:

- actor name
- user id
- department id and name
- location id and name
- role names

The values are snapshots. If a user later moves department, location, or role, old audit events keep the original context.

## New master data

- Locations
- Users with department, location, and initial role assignment
- Roles with edit support

## Migration

```bash
alembic upgrade head
```

New revision:

`20260720_identity_context`
