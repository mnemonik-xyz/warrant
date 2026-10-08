# Ledger integration: tasks

Status of the work in [spec.md](spec.md). All tasks are planned. None has started.

| ID | Task | Phase | Depends on | Status |
|---|---|---|---|---|
| L0.1 | `warrant-host invoice-ids`: print `tax_id_hash`, `reference_hash`, `obligation_id`, `orderId` as hex | 0 | — | Planned |
| L0.2 | Test vectors shared by Rust and the Python connector | 0 | L0.1 | Planned |
| L1.1 | Indexer: `eth_getLogs` for the five `InvoiceEscrow` events, confirmations, decode | 1 | — | Planned |
| L1.2 | Event store (SQLite), keyed by `chainId:txHash:logIndex`; `Paid`–`Offered` join | 1 | L1.1 | Planned |
| L1.3 | Matcher and adapter interface (spec section 6, 7) | 1 | L0.1, L1.2 | Planned |
| L1.4 | beancount adapter, plugin for required metadata, balance assertion | 1 | L1.3 | Planned |
| L1.5 | Exceptions report (spec section 10) | 1 | L1.3 | Planned |
| L1.6 | Demo: `scripts/invoice-demo.py` on `anvil`, then export and `bean-check` | 1 | L1.4, L1.5 | Planned |
| L2a.1 | ERPNext test site (Docker), setup script: settings, escrow account, custom fields | 2a | — | Planned |
| L2a.2 | ERPNext adapter: `get_payment_entry`, insert, `frappe.client.submit`, unique event key | 2a | L1.3, L2a.1 | Planned |
| L2b.1 | Odoo test site (Docker), `warrant_ledger` module with fields and unique constraint | 2b | — | Planned |
| L2b.2 | Odoo adapter: `account.payment.register`, `action_create_payments`, search by event key | 2b | L1.3, L2b.1 | Planned |
| L3.1 | `warrant-evidence sign-po` and `sign-invoice-vendor` with the buyer key | 3 | — | Planned |
| L3.2 | Draft builder: ERP PO and supplier to unsigned JSON | 3 | L3.1, L2a.1 or L2b.1 | Planned |
| L4.1 | Self-checks (spec section 9) | 4 | L1.3 | Planned |
| L4.2 | ERPNext chain statement as Bank Transactions | 4 | L2a.2 | Planned |

Prerequisites outside this work: non-USD invoices (currency support) and
`settleApproved` through the checker. See spec section 12.
