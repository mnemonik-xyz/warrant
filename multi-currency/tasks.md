# Multi-currency invoices: tasks

Status of the work in [spec.md](spec.md). All tasks are planned. None has started.

| ID | Task | Depends on | Status |
|---|---|---|---|
| C1 | Currency table (USD, EUR, AMD with ISO 4217 minor units) and `parse_amount` per currency | — | Planned |
| C2 | `PurchaseOrder.currency`, `rate_num`, `rate_den`; `InvoicePolicy.currencies`; policy tag `v3` | — | Planned |
| C3 | `authorize_invoice`: currency checks, exact conversion in `u128`, round down; new `AskReason` values | C1, C2 | Planned |
| C4 | `CHECKER_VERSION = 3`; regenerate fixtures, `terms.json` and cross-language vectors | C3 | Planned |
| C5 | Tests from spec section 7, including the updated E11 | C3 | Planned |
| C6 | Update `evidence-checker.md`, `invoice-escrow.md`, `validation-results.md`, the README and the whitepaper journal text | C3 | Planned |
| C7 | Rebuild the invoice guest with `RISC0_USE_DOCKER=1`, record the new image ID, prove in a new receipt directory | C4 | Planned |
| C8 | New `InvoiceEscrow` deployment with the new image ID | C7 | Planned |
