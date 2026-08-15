# Operational & Maintenance Scripts

This directory contains standalone maintenance, migration, and diagnostic scripts for the PostgreSQL database and backend service.

## Scripts Overview

| Script | Purpose |
| :--- | :--- |
| cleanup_db.py | Cleans up test customer records, tickets, orders, and refund entries. |
| complete_refunds.py | Processes pending refund records to completed status. |
| ix_db.py | Applies database schema fixes and consistency migrations. |
| update_order.py | Helper script to update order delivery and tracking statuses. |

## Usage
Run any script from the project root:
`ash
python scripts/cleanup_db.py
`
