# HMM Connect ERP

HMM Connect is an ERP prototype focused on controlled purchasing, document traceability, inventory, finance, and auditability.

This project is currently in **trial / pre-production mode**, but its deployment architecture is already split into production frontend, production backend, and an EC2 data-processing layer.

## Business flow

```text
User
  ↓
Purchase Requisition (PR)
  ↓
Configurable approval layers
  ↓
Approved PR
  ↓
Purchase Order (PO)
  ↓
Configurable approval layers
  ↓
Approved PO
  ↓
Goods Receipt
  ├── Inventory
  └── Direct Consumption
```

## Procurement flow

### 1. Purchase Requisition (PR)

A requester creates a PR with:

- Product
- Quantity
- Estimated price
- Notes

The estimated price is an **estimate only**. It is not the final purchasing cost.

PR lifecycle:

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
APPROVED
```

A PR can also be rejected.

### 2. Layered PR approval

Approval is **not hardcoded as `Section → Manager` in application code**.

The workflow is configurable:

```text
PR_APPROVAL
  1. Section Approval
  2. Manager Approval
```

Each approval step can be configured by:

- Role
- Department (optional)
- Location (optional)

Example:

```text
Step 1
Role: SECTION_APPROVER
Department: Operations

Step 2
Role: MANAGER
```

A workflow can be changed without changing the PR business logic.

### 3. Purchase Order (PO)

A PO can combine **multiple approved PRs**.

```text
PR-000001 ─┐
            ├── PO-000001
PR-000002 ─┘
```

PO stores:

- Supplier
- PO items
- Final unit price
- Expected date
- Expiry date
- Receipt tolerance

The PO price is separate from the PR estimated price.

### 4. Layered PO approval

Default trial workflow:

```text
PO_APPROVAL
  1. Section Approval
  2. Manager Approval
  3. Finance Approval
```

The same configurable approval engine is used for PR and PO.

### 5. Goods Receipt

A PO is received only after approval.

```text
Approved PO
  ↓
Goods Receipt
```

The receiving user chooses the destination:

```text
Inventory
```

or

```text
Direct Consumption
```

Receipt cost is derived from the PO and is not manually changed during receiving.

The PO receipt tolerance controls how much quantity variance is allowed.

## Approval engine

The approval engine uses four concepts:

```text
Approval Workflow
        ↓
Workflow Steps
        ↓
Approval Request
        ↓
Approval Request Steps
```

### Workflow definition

Defines the business flow:

```text
PR_APPROVAL
PO_APPROVAL
```

### Workflow steps

Defines the ordered approval layers.

### Approval request

Created when a document is submitted.

The request stores the workflow used by the document.

### Approval request steps

The workflow configuration is copied into the document approval instance.

This is intentional.

If the company changes the workflow next month, an old PR must still show the approval chain that was required when it was submitted.

## Audit principle

Audit is a core ERP feature.

Every important action records:

```text
User
Department
Location
Roles
Action
Document
Timestamp
Details
```

Example:

```text
Advan
Purchasing
Jakarta Office
PURCHASING

SUBMITTED PR-000001
```

The user identity context is snapshotted in the audit log. If the user later changes department, location, or role, historical audit records remain correct.

## User / role / department / location

```text
User
  ↓
Roles
  ↓
Department
  ↓
Location
```

Location is part of the operational identity context used by audit and approval rules.

The default approval workflow also includes `SECTION_APPROVER` as a configurable role. The `section` trial user is included so the layered PR and PO approval flow can be tested immediately.

## Architecture

HMM Connect is deployed as separate frontend, backend, and data-processing layers.

```text
                              GitHub
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
               main                           backend
                 │                               │
                 ▼                               ▼
              Vercel                        AWS Lambda
             Frontend                         FastAPI
                 │                               │
                 └───────────────┬───────────────┘
                                 │
                                 ▼
                            PostgreSQL
                               EC2
                                 │
                                 └── Heavy processing
                                     XLS / XLSX imports
                                     database migrations
```

### Frontend

- Repository branch: `main`
- Deployment platform: **Vercel**
- The `main` branch is the production frontend source of truth.
- Commits pushed to `main` trigger the Vercel deployment workflow.

### Backend

- Repository branch: `backend`
- Runtime: **AWS Lambda**
- Application: **FastAPI**
- The `backend` branch is the production backend source of truth.
- Commits pushed to `backend` trigger the Lambda deployment workflow.
- Lambda is intentionally kept lightweight; heavy file processing does not belong in the Lambda runtime.

### Database and processing

- Database: **PostgreSQL**
- PostgreSQL runs on the **EC2** host.
- EC2 also provides the heavy-processing environment for operations such as XLS/XLSX imports.
- Database migrations are executed on EC2 using Alembic.

The production responsibilities are therefore separated:

```text
Vercel
  └── Frontend

AWS Lambda
  └── FastAPI backend / API

EC2
  ├── PostgreSQL
  ├── Alembic migrations
  └── Heavy processing / XLS-XLSX imports
```

## Deployment model

Production deployments are branch-driven:

```text
Frontend change
      ↓
   push main
      ↓
   Vercel
      ↓
Production frontend
```

```text
Backend change
      ↓
 push backend
      ↓
 AWS Lambda
      ↓
Production API
```

Database changes follow the migration workflow on EC2:

```text
Migration code
      ↓
     EC2
      ↓
 alembic upgrade head
      ↓
 PostgreSQL
```

Frontend and backend can therefore be deployed independently while sharing the same production database.

## Demo environment

The EC2 host may also contain a separate **demo** deployment used for testing and investigation. The demo environment is not the production backend.

```text
Production
  ├── Vercel
  └── AWS Lambda

Demo / processing environment
  └── EC2
      └── separate demo application
```

Do not treat the EC2 demo Uvicorn application as the production API. Production backend traffic is served through AWS Lambda.

## Database migration

Migrations are maintained with Alembic and executed from the backend environment on EC2.

```bash
alembic upgrade head
```

The migration workflow must be completed against the production PostgreSQL database before deploying backend code that depends on new database structures.

## Frontend development

```bash
npm install
npm run lint
npm run build
```

## Development principles

- Keep production frontend and backend deployment paths independent.
- Keep Lambda lightweight and suitable for API execution.
- Perform heavy XLS/XLSX processing on EC2 rather than inside Lambda.
- Run database migrations on EC2 against PostgreSQL.
- Treat auditability and document traceability as core ERP requirements.
- Keep the backend API and database model as the source of truth for frontend behavior.
