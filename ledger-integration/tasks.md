# Ledger integration: tasks

Status of the work in [spec.md](spec.md) and [implementation.md](implementation.md).

| ID | Task | Phase | Depends on | Status |
|---|---|---|---|---|
| L0.1 | `warrant-ids` crate: `facts`, `obligation`, `reference`, `tax-id`, `order-id` | 0 | — | Done |
| L0.2 | Test vectors shared by Rust and the Python connector | 0 | L0.1 | Done |
| L1.1 | Indexer: `eth_getLogs` for the five `InvoiceEscrow` events, confirmations, decode | 1 | — | Done |
| L1.2 | Event store (SQLite), keyed by `chainId:txHash:logIndex`; `Paid`–`Offered` join | 1 | L1.1 | Done |
| L1.3 | Intake records, matcher and adapter interface (spec sections 6, 7) | 1 | L0.1, L1.2 | Done |
| L1.4 | beancount writer and plugin | 1 | L1.3 | Done |
| L1.5 | Exceptions report (spec section 10) | 1 | L1.3 | Done |
| L1.6 | Demo: `scripts/invoice-demo.py --signed-only` on `anvil`, then export and `bean-check` | 1 | L1.4, L1.5 | Done |
| L2b.1 | Odoo test site (Docker), `warrant_ledger` module with fields and unique constraint | 2b | — | Planned |
| L2b.2 | Odoo adapter: `account.payment.register`, `action_create_payments`, search by event key | 2b | L1.3, L2b.1 | Planned |
| L2b.3 | Confirm that the Odoo UBL import keeps the XML attachment; else use the fallback match | 2b | L2b.1 | Planned |
| L2a.1 | ERPNext test site and adapter (for a buyer who runs ERPNext) | 2a | L1.3 | Planned |
| L3.1 | `warrant-evidence sign-po` and `sign-invoice-vendor` with the buyer key | 3 | — | Planned |
| L3.2 | Draft builder: ERP PO and supplier to unsigned JSON | 3 | L3.1, L2b.1 | Planned |
| L4.1 | Self-checks (spec section 9) | 4 | L1.3 | Partly done: order totals; read-back checks need an ERP adapter |
| L4.2 | ERPNext chain statement as Bank Transactions | 4 | L2a.1 | Planned |

Prerequisites outside this work: [multi-currency invoices](../multi-currency/tasks.md)
and `settleApproved` through the checker. See spec section 12.
