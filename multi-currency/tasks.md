# Multi-currency invoices: tasks

Status of the work in [spec.md](spec.md). C1 to C6 are done (2026-10-08). C7 and C8 need the RISC Zero toolchain and a deployment.

| ID | Task | Depends on | Status |
|---|---|---|---|
| C1 | Currency table (USD, EUR, AMD with ISO 4217 minor units) and `parse_amount` per currency | — | Done |
| C2 | `PurchaseOrder.currency`, `rate_num`, `rate_den`; `InvoicePolicy.currencies`; policy tag `v3` | — | Done |
| C3 | `authorize_invoice`: currency checks, exact conversion in `u128`, round down; new `AskReason` values | C1, C2 | Done |
| C4 | `CHECKER_VERSION = 3`; regenerate fixtures, `terms.json` and cross-language vectors | C3 | Done |
| C5 | Tests from spec section 7, including the updated E11 | C3 | Done |
| C6 | Update `evidence-checker.md`, `invoice-escrow.md`, `validation-results.md`, the README and the whitepaper journal text | C3 | Done |
| C7 | Rebuild the invoice guest with `RISC0_USE_DOCKER=1`, record the new image ID, prove in a new receipt directory | C4 | Planned: blocked in the cloud session, where `rzup` cannot download the toolchain |
| C8 | New `InvoiceEscrow` deployment with the new image ID | C7 | Planned |
