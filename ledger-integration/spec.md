# Warrant ledger integration: architecture specification

Version 0.1 · 2026-10-08 · Draft. Status: design only. No code exists. Section 13
lists the tasks; [tasks.md](tasks.md) tracks them.

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
                        └── warrant-host invoice-ids (hashes)                  
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
5. **Identifier tool.** A new `warrant-host invoice-ids` subcommand computes the
   Warrant hashes. The connector does not reimplement the bincode encoding.
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

The obligation identifier is
`obligation_id(seller tax ID, invoice number)` (`core/src/evidence.rs:341-346`).
The connector computes it for each candidate bill:

1. Take the order from the `Paid` event and its `poId` from `Offered`.
2. List the bills linked to the PO whose `reference_hash(PO number)` equals
   `poId`.
3. For each bill, compute `obligation_id` from the seller tax ID and the invoice
   number. Use `warrant-host invoice-ids`.
4. Exactly one match: book it. No match: report "payment without a bill". More
   than one match: report "ambiguous", book nothing.

Field sources per ledger:

| Value | ERPNext | Odoo 18 | beancount |
|---|---|---|---|
| Invoice number | Purchase Invoice `bill_no` | `account.move.ref` (filled from `cbc:ID`) | Not applicable: the exporter writes entries from events only |
| Seller tax ID | The UBL document. `Purchase Invoice.tax_id` is a copy of `Supplier.tax_id` (`fetch_from`), not the invoice value | The UBL document, or `partner_id.vat` | — |
| PO number | `items.purchase_order` | `invoice_origin` (from `OrderReference/ID`) | — |

The seller tax ID must come from the invoice document when the document is
available. A supplier record can carry an old or a wrong tax ID. If the document
value and the master value differ, the connector reports the bill and books
nothing.

After a match, the adapter stores the obligation ID on the bill. Later lookups use
the stored value.

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
| `Offered` | `Assets:Escrow:Warrant` debit, `Assets:Buyer:Wallet` credit, link `^order-<orderId>` |
| `Paid` | `Liabilities:Payable:<vendor>` debit, `Assets:Escrow:Warrant` credit, links to order and document hash, metadata `txid`, `obligation`, `evidence`, `authenticator` |
| `Closed` | `Assets:Buyer:Wallet` debit, `Assets:Escrow:Warrant` credit |
| After `Closed` | `balance Assets:Escrow:Warrant 0.000000 ~ 0.000001 USDC`, dated the next day |

A small plugin checks that each `Paid` entry has the metadata fields above. The
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
| `warrant-host invoice-ids` subcommand: prints `tax_id_hash`, `reference_hash`, `obligation_id` and `orderId` for given inputs | `host/src/main.rs` | None. Host only. |
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
| 0 | `invoice-ids` subcommand and cross-language test vectors | 1 day |
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

Decision: build phase 1 now. Choose between 2a and 2b when a pilot buyer is known.

## 15. Open questions

1. How many confirmations does Arc need for the connector to treat a log as final?
2. Does the buyer want the escrow funding (`Offered`) in the ERP, or only the
   payments?
3. Who owns the ERP API key: the buyer's accountant or the operator of the
   connector?
4. Does `edocument` read `PayableAmount` and `InvoiceTypeCode`? Not checked.
5. `docstatus: 1` on `POST /api/resource` should submit in one call. This review
   inferred it from the code only. The design uses `frappe.client.submit`.

## 16. Sources

Read on 2026-10-08 from shallow clones:

- `frappe/erpnext` and `frappe/frappe`, branch `version-15`.
- `prilk-consulting/edocument`, branch `develop`.
- `frappe/mcp`, default branch (MIT). Not used: plain REST is simpler.
- `odoo/odoo` 18.0 at `c04c3e0` (addons `account`, `account_edi_ubl_cii`,
  `purchase`).
- `OCA/edi` 18.0 at `ac78346`.
- `erpipe-org/mcp-odoo` 1.3.2 (MIT). Not used: the connector does not need MCP.
- `beancount/beancount` 3.2.3 at `9747213`.
