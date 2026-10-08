# Warrant ledger integration: architecture specification

Version 0.2 · 2026-10-08 · Draft. Status: phases 0 and 1 are implemented and
tested. [implementation.md](implementation.md) gives the build details;
[tasks.md](tasks.md) tracks the work.

Decisions of 2026-10-08:

- The target is production, not a hackathon demo. Real buyers supply real
  purchase orders.
- Phase 1 builds the beancount export.
- The first ERP is self-hosted Odoo 18 Community. A paid Odoo plan is future work.
- PDF invoices are future work. The checker reads UBL XML only.
- Invoices in EUR and AMD are supported through
  [the multi-currency change](../multi-currency/spec.md).

This document specifies how the Warrant invoice path connects to the books of the
buyer. The first targets are beancount, ERPNext and Odoo 18 Community. The
research that led to this design is in
`tameion/docs/research/agents-and-ledgers.md`.

Abbreviations: API — application programming interface; AP — accounts payable;
ERP — enterprise resource planning; JSON — JavaScript Object Notation; PO —
purchase order; REST — representational state transfer; RPC — remote procedure
call; UBL — Universal Business Language; USDC — USD Coin.

## 1. Problem

Warrant authorizes and settles an invoice payment. It does not post an entry to a
ledger. After a `Paid` event, nobody books the payment against the vendor bill.
Three ledger errors therefore come back at that step:

- **Omission.** An invoice arrives and nobody pays it. Nothing lists it.
- **Fictitious entry.** A payment exists with no bill behind it.
- **Booking error.** A person books the payment to the wrong bill or the wrong
  amount.

An ERP also holds the purchase orders and the vendor master data that Warrant
needs as signed input. Today a person types these facts by hand.

## 2. Goals and non-goals

Goals:

1. Book each `Paid` event against the matching vendor bill, exactly once.
2. Report each payment with no bill, and each bill with no payment.
3. Prepare unsigned drafts of the Warrant purchase order and vendor credential
   from ERP records, for the buyer to review and sign.
4. Keep the design independent of one ERP. One core, one adapter per ledger.

Non-goals:

- The connector never causes a payment. Only the escrow pays.
- The connector never signs. It holds no Warrant key.
- No agent write path into the ledger through MCP (Model Context Protocol).
- No change to the guest program, the image ID, the journal, the Verus proof or
  the contracts.

## 3. Trust boundary

The connector is outside the trust path of the payment. A fault in the connector
can cause a wrong or missing ledger entry. It cannot move money.

| Component | Trusted for | Not trusted for |
|---|---|---|
| `InvoiceEscrow` | Money movement, one payment per obligation | — |
| Warrant checker and proof | The decision `Allow`, `Deny` or `Ask` | — |
| Buyer key | Signatures on the PO, the vendor credential, `settleApproved` | — |
| Connector | Nothing that moves money | Correct bookings: it must check its own work (section 9) |
| ERP | Draft data for the PO and the vendor | Any field that selects: recipient, category, ceiling |

These invariants from the Warrant design stay in force:

- **Fields that select must never come from the ERP without a buyer signature.**
  The connector proposes. The buyer signs. The signed credential is the authority.
- **The key that executes must never be the key that can change the policy.** The
  connector holds an ERP API key. That key has no Warrant authority.
- **A chain is not an independent witness.** A booking that agrees with the chain
  proves consistency only. The design makes no reconciliation claim beyond that.

## 4. Architecture

```text
                 ┌──────────────── upstream (phase 3) ─────────────────┐
  ERP PO, ──read──▶ draft builder ──▶ draft JSON ──▶ buyer reviews ──▶ warrant-evidence
  supplier                                                            sign-po / sign-invoice-vendor
                                                                      (buyer key, offline)

                 ┌──────────────── downstream (phases 1–2) ────────────┐
  Arc chain ──logs──▶ indexer ──▶ event store ──▶ matcher ──▶ ledger adapter ──▶ beancount
  (InvoiceEscrow)       │          (SQLite)         │                         ──▶ ERPNext REST
                        │                           │                         ──▶ Odoo JSON-RPC
                        └── warrant-ids (hashes, invoice facts)
                                                    └──▶ exceptions report
```

Components:

1. **Indexer.** It reads `Offered`, `Accepted`, `Paid`, `SignerRevoked` and
   `Closed` logs with `eth_getLogs`. It waits for a configured number of
   confirmations. It stores each log once, keyed by chain ID, transaction hash and
   log index.
2. **Event store.** A SQLite file. It holds raw logs, decoded events, the order
   join and the booking state of each event.
3. **Matcher.** It finds the ledger bill for each `Paid` event (section 7).
4. **Ledger adapter.** One per ledger. It implements the interface in section 6.
5. **Identifier tool.** A new binary `warrant-ids` computes the Warrant hashes and
   reads the facts of an invoice document. It lives in a new crate with no zkVM
   dependency, so a buyer can run the connector without the RISC Zero toolchain.
   The connector does not reimplement the bincode encoding.
6. **Exceptions report.** It lists every event or bill that the connector could
   not book (section 10).
7. **Draft builder** (phase 3). It reads ERP records and writes unsigned JSON.

Location: a Python package at `policy-execution/connectors/ledger/`. It follows
the `showcases/ionet_arc/` layout: a package, a pinned `requirements.txt` and
tests. It calls `warrant-host` as a subprocess, like the existing scripts.

## 5. Data from the chain

`InvoiceEscrow` emits these events (`contracts/src/InvoiceEscrow.sol:100-111`):

| Event | Indexed | Data |
|---|---|---|
| `Offered` | `orderId`, `customer` | `Terms`: `policyHash`, `policyVersion`, `poId`, `recipient`, `maxTotal`, `signer`, `signerAllowance`, `proofThreshold`, `acceptBy`, `settleBy` |
| `Accepted` | `orderId` | — |
| `Paid` | `orderId`, `taskId` | `amount`, `authenticator`, `deliverableHash`, `evidenceHash` |
| `SignerRevoked` | `orderId` | — |
| `Closed` | `orderId` | `refunded` |

Rules for the connector:

1. `Paid` has no customer and no `poId`. The connector joins `Paid` to `Offered` on
   `orderId`. If the `Offered` log is not in the store, the connector calls
   `order(bytes32)` and records the event as incomplete until the join succeeds.
2. `taskId` is the obligation identifier. `deliverableHash` is the SHA-256 hash of
   the invoice bytes.
3. `authenticator` is `Proof`, `Signature` or `BuyerApproval`. For
   `BuyerApproval`, `evidenceHash` is zero and the checker did not run on chain.
   The connector books the payment and marks it "approved by buyer, not checked".
4. Amounts are `uint64` base units of USDC, with 6 decimals.
5. The idempotency key of an event is `chainId:transactionHash:logIndex`.

## 6. Ledger adapter interface

Each adapter implements these operations. All are idempotent.

| Operation | Input | Result |
|---|---|---|
| `find_bills(po_number_hash)` | `poId` | Open vendor bills linked to that PO, with supplier tax ID, invoice number, total, currency |
| `bill_for(obligation_id)` | obligation ID | One bill, none, or several (an error) |
| `book_payment(event, bill)` | decoded `Paid`, bill | Ledger reference of the payment, or a refusal with a reason |
| `book_refund(event)` | decoded `Closed` | Ledger reference, or "not supported" |
| `find_booking(event_key)` | idempotency key | The existing ledger reference, or none |
| `open_bills(since)` | date | Bills with an unpaid balance, for the omission report |

`book_payment` must call `find_booking` first. A second run of the connector must
never create a second entry.

## 7. Matching a payment to a bill

A `Paid` event carries two keys: `taskId`, the obligation identifier, and
`deliverableHash`, the SHA-256 hash of the invoice bytes. The connector matches on
the document hash first, and on the obligation identifier second.

### 7.1 Where the connector finds the bill

| Ledger | Bill source | Document hash | Obligation identifier |
|---|---|---|---|
| beancount | Intake records: the connector runs `warrant-ids facts` on each UBL document that the buyer's agent submits, and stores the result in the event store | From the document bytes | From the document bytes |
| Odoo 18 | `account.move` with `move_type = "in_invoice"`, linked to the PO through `invoice_origin` or the purchase lines | From the UBL attachment of the bill, read through the API and hashed by `warrant-ids facts` | From the same attachment. Fallback: `partner_id.vat` and `ref` |
| ERPNext 15 | Purchase Invoice linked to the PO through `items.purchase_order` | From the UBL attachment, if the `edocument` app keeps it | From the attachment. Fallback: the UBL tax ID and `bill_no` |

### 7.2 Procedure

1. Take the order from the `Paid` event and its `poId` from `Offered`.
2. Look up a bill whose document hash equals `deliverableHash`. One match: book
   it.
3. Otherwise list the bills for the PO, where `reference_hash(PO number)` equals
   `poId`. For each bill, compute `obligation_id` with `warrant-ids`. Exactly one
   match with `taskId`: book it, and report "matched without the document".
4. No match: report "payment without a bill". More than one: report "ambiguous"
   and book nothing.

The seller tax ID must come from the invoice document when it is available. A
supplier record can carry an old or a wrong tax ID. In ERPNext,
`Purchase Invoice.tax_id` is a copy of `Supplier.tax_id` (`fetch_from`), not the
invoice value. If the document value and the master value differ, the connector
reports the bill and books nothing.

After a match, the adapter stores the document hash and the obligation ID on the
bill. Later lookups use the stored values.

## 8. Booking rules

### 8.1 Common rules

1. **The amount is the on-chain amount.** The connector never books a different
   amount. If the bill total differs from the paid amount, it books the payment
   and reports the difference. A partial payment stays visible as an open
   balance.
2. **Refuse, do not repair.** If the ledger currency precision cannot hold the
   amount exactly, the adapter refuses and reports. It never books a rounding
   difference to another account. Example: a ledger in USD with 2 decimals
   refuses `10.004500 USDC`.
3. **Every entry links to the evidence.** Each payment carries the transaction
   hash, the obligation ID, the document hash, the evidence hash and the
   authenticator.
4. **Confirmations.** The connector books an event only after the configured
   number of confirmations.

### 8.2 beancount

Facts from `beancount` 3.2.3 (GPL-2.0-only):

- `USDC` is a valid commodity. A 0x-prefixed hex hash is a valid link
  (`lexer.l:292`).
- An explicit tolerance is `balance Account 0.000000 ~ 0.000001 USDC`.
- The `noduplicates` plugin ignores metadata. The exporter must deduplicate by the
  event key itself.

Mapping:

| Event | Entry |
|---|---|
| Intake record | `custom "warrant-invoice"` directive with the document hash, obligation ID, invoice number, currency and payable amount. No postings |
| `Offered` | `Assets:Escrow:Warrant` debit, `Assets:Buyer:Wallet` credit, link `^order-<orderId>` |
| `Paid` | `Expenses:Warrant:<vendor>` debit (cash basis: intake records carry no postings), `Assets:Escrow:Warrant` credit, links to order and document hash, metadata `txid`, `obligation`, `evidence`, `authenticator` |
| `Closed` | `Assets:Buyer:Wallet` debit, `Assets:Escrow:Warrant` credit |
| After `Closed` | `balance Assets:Escrow:Warrant 0.000000 ~ 0.000001 USDC`, dated the next day |

A small plugin, `warrant_ledger.beancount_plugin`, runs inside `bean-check`. It
reports:

- a `Paid` entry without the metadata fields above;
- a `Paid` entry with no intake record of the same document hash (payment without
  a bill);
- an intake record older than a configured number of days with no `Paid` entry
  (bill without a payment).
 The
exporter rewrites the file from the event store. It never edits by hand.

### 8.3 ERPNext (version 15)

Facts from `frappe/erpnext` and `frappe/frappe` at `version-15`:

- `get_payment_entry(dt, dn, ...)` is whitelisted and returns an unsaved Payment
  Entry (`payment_entry.py:2900-3073`).
- `reference_no` and `reference_date` are mandatory for a bank account
  (`payment_entry.py:1239-1245`). `reference_no` is a 140-character Data field.
- Nothing prevents two Payment Entries for one invoice.
- A Custom Field with `unique: 1` becomes a database UNIQUE column.
- `check_supplier_invoice_uniqueness` defaults to 0 and checks one fiscal year
  only.
- Currency precision is one site-wide setting (`currency_precision`, 0 to 9).

Procedure for one `Paid` event:

1. Call `get_payment_entry("Purchase Invoice", <name>, party_amount=<amount>, bank_account=<escrow account>)`.
2. Set `reference_no` to the transaction hash and `reference_date` to the block
   date.
3. Set the custom fields `warrant_event_key` (unique), `warrant_obligation_id`,
   `warrant_document_hash`, `warrant_evidence_hash` and `warrant_authenticator`.
4. Insert it, then submit it with `frappe.client.submit`.
5. A UNIQUE violation on `warrant_event_key` means "already booked". Read the
   existing entry and continue.

Site setup, done once by an administrator:

- Turn on `check_supplier_invoice_uniqueness`.
- Turn on `po_required`. Turn on `pr_required` when receipts are in use.
- Create a bank account "Warrant escrow" and the custom fields.
- Choose the currency mode (section 8.5).
- Optional: install `prilk-consulting/edocument` (GPL-3.0). It creates draft
  Purchase Invoices from UBL. It matches the supplier by tax ID and the PO by
  `OrderReference`.

Optional chain statement: the connector can create Bank Transactions with
`reference_number` equal to the transaction hash. ERPNext ranks a match on
`reference_no == reference_number` (`bank_reconciliation_tool.py:862`). This
proves agreement with the chain only. It is not an independent witness.

### 8.4 Odoo 18 Community

Facts from `odoo/odoo` at 18.0 and `OCA/edi` at 18.0:

- `account_edi_ubl_cii` (LGPL-3, auto-installed with `account`) imports UBL vendor
  bills. It fills `ref` from `cbc:ID`, `invoice_origin` from `OrderReference/ID`,
  the dates and the currency.
- The import **does not read `PayableAmount`**. Odoo recomputes the totals and can
  add a rounding line.
- The import **does not read `InvoiceTypeCode`**. An `Invoice` root with code 381
  becomes a normal vendor bill.
- The import **creates a vendor bank account from `PayeeFinancialAccount`**, with
  `allow_out_payment=False`.
- If the bill matches a PO, the purchase module can replace the UBL lines with the
  PO lines.
- The duplicate vendor reference check is a warning only.
- `res.currency.name` has 3 characters. `USDC` is cut to `USD` and collides with
  the existing currency.
- The bank reconciliation widget is in the enterprise module `account_accountant`.
  The models for statement lines and reconciliation are in Community.
- The external API is `/jsonrpc` with API keys. There is no JSON-2 API in 18.0.

Consequences for the design:

1. The Odoo bill is not evidence. The connector reads only `ref`, `invoice_origin`
   and `amount_total` from it. The Warrant checker reads the original UBL bytes.
2. The connector compares `amount_total` with the paid amount and reports a
   difference (rule 8.1.1).
3. The bank account that Odoo creates from the invoice IBAN is never used. Warrant
   pays the recipient in the signed vendor credential. Odoo never makes the
   payment.

Procedure for one `Paid` event:

1. Search `account.payment` for `payment_reference` equal to the event key. If
   found, stop.
2. Create `account.payment.register` with context `active_model="account.move"`
   and `active_ids=[bill]`. Values: `journal_id` (the escrow journal),
   `payment_date` (block date), `amount`, `communication` (transaction hash).
3. Call `action_create_payments`. This creates, posts and reconciles the payment.
4. Write `payment_reference` (event key) and the custom `x_warrant_*` fields on the
   new payment.

Site setup, done once:

- A small Odoo module `warrant_ledger` adds the `x_warrant_*` fields and a unique
  SQL constraint on the event key. A module is preferred to fields created over
  RPC.
- A bank journal "Warrant escrow" in the chosen currency (section 8.5).
- An API key for a dedicated user with accounting rights only.

### 8.5 Currency mode

USDC has 6 decimals. Invoices in USD have 2. Two modes:

| Mode | Ledger currency of the escrow account | Rule |
|---|---|---|
| A, default | USD, ledger precision 2 | Book `amount / 10^6` as USD. Refuse if the amount is not a multiple of `10^4` base units (rule 8.1.2). |
| B | A separate currency for USDC, precision 6 | ERPNext: `currency_precision=6` for the whole site. Odoo: a 3-letter code such as `XUS` with `rounding=0.000001`. Needs exchange rates against the company currency. |

Mode A is the default. Mode B changes site-wide behaviour and needs an accountant
to approve it.

## 9. Self-checks of the connector

The connector is not trusted for correct bookings. It checks its own output:

1. After each booking, read the entry back and compare amount, bill and event key.
2. Daily: the sum of booked payments per order equals the sum of `Paid` amounts in
   the event store.
3. Daily: for each closed order, `maxTotal = spent + refunded`.
4. Each failed check goes to the exceptions report. The connector does not repair
   it.

## 10. Exceptions report

The report lists:

| Exception | Meaning |
|---|---|
| Payment without a bill | A `Paid` event with no matching bill. A possible fictitious entry, or a bill not yet imported. |
| Bill without a payment | An open bill linked to a Warrant PO, past its due date or past `settleBy`. A possible omission. |
| Amount difference | Bill total and paid amount differ. |
| Tax ID difference | Document tax ID and supplier master tax ID differ. |
| Ambiguous match | More than one bill has the same obligation ID. |
| Refused precision | The ledger cannot hold the amount exactly. |
| Buyer approval | Paid through `settleApproved`; the checker did not run on chain. |
| Order expiring | An accepted order within N days of `settleBy` with open bills. |

The report is a JSON file and a plain-text summary. The planned Operations view
(`docs/product/frontend.md:20`) can read the JSON later.

## 11. Upstream: drafts from ERP records (phase 3)

Today `core/examples/invoice_fixture.rs` signs the PO and the vendor credential
with fixed test keys. No tool signs them for a real buyer.

Flow:

1. The draft builder reads a confirmed PO and its supplier from the ERP.
2. It writes `po.draft.json` and `vendor.draft.json`. The PO draft holds the order
   number, the vendor tax ID, `max_total` and the lines (`item_id`, `category`).
3. The buyer reviews the drafts. The buyer adds the fields that select and that the
   ERP must not supply: the recipient address and the category of the vendor.
4. The buyer signs with the new `warrant-evidence sign-po` and
   `warrant-evidence sign-invoice-vendor` commands, offline, with the buyer key.
5. The buyer calls `offer` with the signed PO.

Field rules:

| Warrant field | Source | Why |
|---|---|---|
| `po_id` | `reference_hash(ERP PO number)` | The invoice cites this number |
| `vendor_tax_id` | ERP supplier tax ID, confirmed by the buyer | Selects the vendor |
| `max_total` | ERP PO total, converted to base units, confirmed by the buyer | Selects the ceiling |
| `lines[].item_id` | `reference_hash(supplier item code)` | The invoice line cites it |
| `lines[].category` | The buyer | Selects the limits |
| `recipient` | The buyer, never the ERP | The ERP bank data can come from an invoice IBAN |

The current `PoLine` has no quantity and no unit price. The draft builder can read
both from the ERP, but Warrant cannot check them yet. A later revision of
`PurchaseOrder` can add them. That is an interpreter change and needs a new image
ID.

## 12. Changes to Warrant

| Change | Where | Effect on approvals |
|---|---|---|
| `warrant-ids` binary: `facts`, `obligation`, `reference`, `tax-id`, `order-id` | `ids/` (new crate) | None. The guests do not link it. |
| `warrant-evidence sign-po` and `sign-invoice-vendor` | `host/src/bin/warrant-evidence.rs` | None. Signing tools only. |
| Hex output option for JSON hashes | host | None |
| Connector package | `connectors/ledger/` (new) | None |

The guest, the image ID, the journal, the Verus proof and the contracts do not
change.

Prerequisites outside this specification. A real use case needs both:

1. **Currency.** The checker asks on any non-USD invoice (`AskReason::NotUsd`).
   The target countries invoice in AMD and EUR.
2. **`settleApproved` through the checker.** Today it accepts any obligation ID.
   Without this change, the ledger books buyer-approved payments that no check
   covers. The connector marks them (section 10), but cannot prevent them.

## 13. Phases

| Phase | Content | Estimate |
|---|---|---|
| 0 | `warrant-ids` crate and cross-language test vectors | 1 day |
| 1 | Indexer, event store, matcher core, beancount adapter, exceptions report; demo on `anvil` with `scripts/invoice-demo.py` | 3 days |
| 2a | ERPNext adapter, site setup script, Docker test site | 4 days |
| 2b | Odoo adapter, `warrant_ledger` module, Docker test site | 4 days |
| 3 | Signing commands and draft builder for one ERP | 3 days |
| 4 | Self-checks, confirmations, chain statement (ERPNext) | 2 days |

The estimates are for one engineer and exclude the prerequisites in section 12.
Build 2a or 2b first, not both: choose the ERP that the pilot buyer runs.

## 14. Choice of ERP

| Criterion | ERPNext 15 | Odoo 18 Community |
|---|---|---|
| Licence | GPL-3.0 (ERPNext), MIT (Frappe) | LGPL-3 |
| UBL bill import | `edocument` app (GPL-3.0), draft Purchase Invoice | Built in (`account_edi_ubl_cii`) |
| Import reads the payable amount | Not checked in this review | No: totals recomputed |
| Bank account from invoice IBAN | Not observed in `edocument` | Yes, untrusted by default |
| Three-way match | Built in: `po_required`, `pr_required`, `received_qty` | `purchase_method="receive"`; full bill control is enterprise |
| Idempotency support | Custom Field with `unique: 1` | Module with SQL constraint |
| 6-decimal currency | Site-wide precision | 3-letter code limit; `rounding` supports 6 decimals |
| API | REST, token auth | JSON-RPC, API keys |
| Hosted option | Frappe Cloud, from about $5 to $20 per month (unverified) | Odoo Online needs the Custom plan for API access (unverified) |

Decision (2026-10-08): phase 1 (beancount) now, then phase 2b (Odoo 18
Community, self-hosted). Phase 2a (ERPNext) stays planned for a buyer who runs
ERPNext.

## 15. Deployment

The ERP is the buyer's book of account. The buyer runs it, or the buyer's
accountant or integrator runs it for the buyer. Protocol operators do not host
customer ERPs. Three reasons:

1. **Custody.** A ledger that an operator hosts is a custodial tier. The data
   belongs to the buyer and has legal retention rules.
2. **Trust.** The connector must not run with a key that the operator controls and
   the buyer cannot revoke.
3. **Choice.** Most buyers already run an ERP. The connector connects to it.

| Component | Who runs it | Where |
|---|---|---|
| Odoo 18 Community | The buyer, or the buyer's integrator | The buyer's server, Docker image `odoo:18` with PostgreSQL |
| Connector | The buyer | Next to the ERP: a container or a systemd timer |
| beancount file | The buyer | A Git repository of the buyer |
| Test Odoo for continuous integration | The Warrant project | Docker in CI, data from test fixtures only |
| Chain | Public | Arc. The connector reads public RPC; it signs nothing |

A managed connector service is future work. It would need the buyer's ERP API key
and therefore a separate trust review.

## 16. Event source and storage

The chain is the source of truth. `InvoiceEscrow` writes the events as logs; every
Arc node keeps them. The connector does not need a separate indexer service.

- The connector polls `eth_getLogs` for the escrow address, from the deployment
  block, in bounded block ranges.
- It stores the logs in its own SQLite file. The file is a cache: the connector
  can rebuild it by a new scan from the deployment block.
- It stores the block hash of each log. Before it books, it waits for the
  configured confirmations and checks that the block hash is unchanged.
- The planned chain indexer of the product (`docs/product/architecture-api.md:13`)
  can replace the polling later. It uses the same identity: chain, transaction and
  log index.
- The Mnemonik discovery indexer is not used. It finds memory artifacts on
  Arweave; it does not read EVM logs. Mnemonik can later anchor a signed record
  of each export batch. That is planned, not part of phase 1.


## 17. Open questions

1. How many confirmations does Arc need for the connector to treat a log as final?
2. Does the buyer want the escrow funding (`Offered`) in the ERP, or only the
   payments?
3. Answered: the buyer owns the ERP API key (section 15).
4. Does `edocument` read `PayableAmount` and `InvoiceTypeCode`? Not checked.
5. `docstatus: 1` on `POST /api/resource` should submit in one call. This review
   inferred it from the code only. The design uses `frappe.client.submit`.

## 18. Sources

Read on 2026-10-08 from shallow clones:

- `frappe/erpnext` and `frappe/frappe`, branch `version-15`.
- `prilk-consulting/edocument`, branch `develop`.
- `frappe/mcp`, default branch (MIT). Not used: plain REST is simpler.
- `odoo/odoo` 18.0 at `c04c3e0` (addons `account`, `account_edi_ubl_cii`,
  `purchase`).
- `OCA/edi` 18.0 at `ac78346`.
- `erpipe-org/mcp-odoo` 1.3.2 (MIT). Not used: the connector does not need MCP.
- `beancount/beancount` 3.2.3 at `9747213`.

Links, checked on 2026-10-08. The web pages returned HTTP 200. Our proxy blocks
GitHub web pages, so the GitHub links were checked with `git ls-remote` and in
the clones:

- Frappe Cloud pricing: <https://frappe.io/cloud/pricing> ($5 per month shared,
  $25 per month dedicated) and <https://docs.frappe.io/cloud/pricing>. The older
  address `docs.frappe.io/customer-guide/pricing/frappe-cloud-pricing` returns 404.
  `frappecloud.com/pricing` redirects to the first address.
- Odoo pricing: <https://www.odoo.com/pricing-plan>. Standard is US$24.90 to
  US$31.10 per user per month. "External API" is listed for the Custom plan only.
- EDocument app for ERPNext: <https://cloud.frappe.io/marketplace/apps/edocument>;
  source <https://github.com/prilk-consulting/edocument>.
- OCA UBL import for Odoo 18: <https://apps.odoo.com/apps/modules/18.0/account_invoice_import_ubl>.
- Odoo UBL module source: <https://github.com/odoo/odoo/tree/18.0/addons/account_edi_ubl_cii>.
- ERPNext Payment Entry source: <https://github.com/frappe/erpnext/blob/version-15/erpnext/accounts/doctype/payment_entry/payment_entry.json>.
- beancount: <https://github.com/beancount/beancount>.
