# Ledger integration: implementation plan

Companion to [spec.md](spec.md) version 0.2. Status 2026-10-08: phases 0 and 1
are implemented in `policy-execution` (`ids/`, `connectors/ledger/`), with 4 Rust
tests, 12 Python tests and an end-to-end run on Anvil
(`scripts/invoice-demo.py --signed-only --ledger`, `bean-check` passes). This document gives the build
details for phase 0 (`warrant-ids`), phase 1 (connector core and beancount) and
phase 2b (Odoo 18 Community). All paths are in `policy-execution` unless stated.

## 1. Phase 0: the `warrant-ids` crate

A new workspace member `ids/`, package `warrant-ids`, one binary `warrant-ids`.

Dependencies: `warrant-policy` (path `../core`), `serde_json`, `hex`, `sha3`. All
are already in `Cargo.lock`. The guests have their own lock files and do not link
this crate, so the image IDs do not change. Add the crate to
`[workspace] members`, not to `default-members`.

Commands. Every hash is printed as `0x` followed by 64 lowercase hex digits.

| Command | Output |
|---|---|
| `warrant-ids facts <document.xml>` | JSON object, see below |
| `warrant-ids obligation <seller-tax-id> <invoice-number>` | `obligation_id` |
| `warrant-ids reference <text>` | `reference_hash` |
| `warrant-ids tax-id <text>` | `tax_id_hash` |
| `warrant-ids order-id <chain-id> <escrow> <customer> <policy-hash> <po-id>` | `keccak256(abi.encode(...))`, as `InvoiceEscrow.orderIdFor` |

`facts` output:

```json
{
  "documentHash": "0x…",
  "invoiceNumber": "INV-1",
  "sellerTaxId": "LV40003000000",
  "taxIdHash": "0x…",
  "poRef": "PO-7",
  "poId": "0x…",
  "obligationId": "0x…",
  "currency": "EUR",
  "currencyConsistent": true,
  "precise": true,
  "payableMinor": 123456,
  "totalsConsistent": true
}
```

`payableMinor` is in minor units of `currency`, as `InvoiceFacts.payable_minor`,
or `null`. The USDC amount depends on the order's signed rate
([multi-currency](../multi-currency/spec.md)), so `facts` does not give it. The
connector compares the paid amount with the invoice for USD only. `poRef`
and `poId` are `null` if the document cites no order. A document that
`parse_invoice` denies gives exit code 2 and a message on standard error.

Tests:

1. Rust unit tests compare each command with the library functions on the
   `invoice_fixture` documents.
2. `order-id` matches `host/src/signer.rs:85-102` for the fixture terms.
3. A test vector file `ids/tests/vectors.json` is written by a Rust test and read
   by the Python tests (section 2.8).

## 2. Phase 1: connector core and beancount

### 2.1 Layout

```text
connectors/ledger/
├── README.md
├── pyproject.toml            # package warrant-ledger, Python ≥ 3.11
├── requirements-test.txt     # beancount==3.2.3 (tests and bean-check only)
├── warrant_ledger/
│   ├── __init__.py
│   ├── __main__.py           # CLI
│   ├── config.py             # TOML configuration (tomllib)
│   ├── chain.py              # JSON-RPC, eth_getLogs paging, event decoding
│   ├── store.py              # SQLite schema and queries
│   ├── ids.py                # subprocess calls to warrant-ids
│   ├── intake.py             # intake records from UBL documents
│   ├── match.py              # spec section 7
│   ├── sync.py               # confirmed-log sync and manual rescan
│   ├── report.py             # exceptions report (spec section 10) and self-checks (section 9)
│   ├── adapters/
│   │   ├── base.py           # interface, spec section 6
│   │   └── beancount.py      # text writer
│   └── beancount_plugin.py   # runs inside bean-check
└── tests/
```

The runtime uses the Python standard library only: `urllib`, `json`, `sqlite3`,
`tomllib`, `subprocess`. This follows `scripts/`. `beancount` is needed only to
validate the output.

### 2.2 Configuration

```toml
[chain]
rpc_url = "https://…"          # public Arc RPC
chain_id = 5042002
escrow = "0x…"
from_block = 123456            # deployment block
confirmations = 12
max_range = 2000               # blocks per eth_getLogs call

[tools]
warrant_ids = "/usr/local/bin/warrant-ids"

[store]
path = "/var/lib/warrant-ledger/events.sqlite"

[beancount]
path = "/srv/books/warrant.beancount"
escrow_account = "Assets:Escrow:Warrant"
wallet_account = "Assets:Buyer:Wallet"
expense_prefix = "Expenses:Warrant"
unpaid_after_days = 30

[vendors]                       # recipient address → account suffix
"0xabc…" = "AcmeLV"
```

An unknown recipient gets the suffix `V` followed by the first 8 hex digits of the
address. Secrets never go in this file. Phase 2b reads the Odoo API key from the
environment variable `WARRANT_ODOO_API_KEY`.

### 2.3 Chain reading

Event topics are constants in `chain.py`. A test recomputes them with
`cast sig-event` when `cast` is present.

| Event | Signature for the topic |
|---|---|
| `Offered` | `Offered(bytes32,address,(bytes32,uint64,bytes32,address,uint64,address,uint64,uint64,uint64,uint64))` |
| `Accepted` | `Accepted(bytes32)` |
| `Paid` | `Paid(bytes32,bytes32,uint64,uint8,bytes32,bytes32)` |
| `SignerRevoked` | `SignerRevoked(bytes32)` |
| `Closed` | `Closed(bytes32,uint64)` |

All data fields are static ABI types. Decoding is a split into 32-byte words:
`Offered` has 10 data words, `Paid` 4, `Closed` 1.

Procedure of `sync`:

1. Read `eth_blockNumber`. The safe head is `head - confirmations`.
2. Call `eth_getLogs` for the escrow address from the stored cursor to the safe
   head, in ranges of `max_range` blocks.
3. For each log, read the block hash and the timestamp (`eth_getBlockByNumber`,
   cached per block). Store the log.
4. Before the next run, re-read the hash of the last stored block. If it changed,
   delete the logs from that block onwards and scan again. Bookings exist only for
   confirmed logs, so a reorganization deeper than `confirmations` stops the
   connector with an error. It does not repair.

### 2.4 Event store

```sql
CREATE TABLE logs (
  chain_id INTEGER, tx_hash TEXT, log_index INTEGER,
  block_number INTEGER, block_hash TEXT, block_time INTEGER,
  event TEXT, order_id TEXT, data TEXT,          -- data: decoded JSON
  PRIMARY KEY (chain_id, tx_hash, log_index));
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY, customer TEXT, policy_hash TEXT, po_id TEXT,
  recipient TEXT, max_total INTEGER, settle_by INTEGER, state TEXT);
CREATE TABLE invoices (
  document_hash TEXT PRIMARY KEY, obligation_id TEXT, invoice_number TEXT,
  seller_tax_id TEXT, po_id TEXT, currency TEXT, payable INTEGER,
  source TEXT, recorded_at INTEGER);
CREATE TABLE bookings (
  event_key TEXT, adapter TEXT, ledger_ref TEXT, status TEXT, reason TEXT,
  booked_at INTEGER, PRIMARY KEY (event_key, adapter));
CREATE TABLE cursor (chain_id INTEGER, escrow TEXT, next_block INTEGER,
  PRIMARY KEY (chain_id, escrow));
```

`event_key` is `chainId:txHash:logIndex`. `status` is `booked`, `refused` or
`pending`.

### 2.5 Intake

`python -m warrant_ledger intake <document.xml>…` runs `warrant-ids facts` on
each file and inserts a row in `invoices`. A file that is already recorded is a
no-op. The buyer's agent, or the signing service wrapper, calls `intake` for every
document it submits. An intake record means "Warrant saw this invoice". It is not
a decision.

### 2.6 beancount writer

`python -m warrant_ledger export-beancount` rewrites the whole file from the event
store, in a stable order: by block number, then log index. It writes to a
temporary file and renames it. It never edits the file in place. Bookings are
recorded per event key, so a second export gives the same bytes.

Layout of the generated file:

```beancount
; Generated by warrant-ledger. Do not edit. Source: chain 5042002, escrow 0x…
option "operating_currency" "USDC"
plugin "warrant_ledger.beancount_plugin" "unpaid_after_days=30"

2026-01-01 commodity USDC
2026-01-01 open Assets:Buyer:Wallet USDC
2026-01-01 open Assets:Escrow:Warrant USDC
2026-01-01 open Expenses:Warrant:AcmeLV USDC

2026-10-01 custom "warrant-invoice" "0x<documentHash>"
  obligation: "0x…"
  invoice: "INV-1"
  currency: "USD"
  payable: "1234.560000"

2026-10-01 * "Warrant" "Offered order 0x1a2b…" ^order-0x<orderId>
  txid: "0x…:3"
  po: "0x<poId>"
  Assets:Escrow:Warrant   5000.000000 USDC
  Assets:Buyer:Wallet    -5000.000000 USDC

2026-10-02 * "AcmeLV" "Paid INV-1" ^order-0x<orderId> ^0x<documentHash>
  txid: "0x…:1"
  obligation: "0x…"
  evidence: "0x…"
  authenticator: "Signature"
  Expenses:Warrant:AcmeLV   1234.560000 USDC
  Assets:Escrow:Warrant    -1234.560000 USDC
```

Rules:

1. Amounts always carry 6 decimals.
2. The date is the UTC date of the block.
3. After a `Closed` event, write the refund and a `balance` assertion for the
   escrow account on the next day with `~ 0.000001`. This assertion holds only if
   the file books every order on this escrow account.
4. A `Paid` event that the matcher cannot book still gets its transaction. The
   plugin reports it.

### 2.7 beancount plugin

`beancount_plugin.py` exposes `__plugins__ = ("check",)` and
`check(entries, options_map, config_str)`. It returns the entries unchanged and a
list of errors, as `beancount/plugins/noduplicates.py` does. Checks: spec section
8.2. It needs only the `beancount` package.

### 2.8 Tests

1. Unit tests: ABI decoding, the store, matching, the writer, the plugin.
2. Cross-language: read `ids/tests/vectors.json` and compare with `ids.py`.
3. Integration: a test chain on `anvil` with a deployed `InvoiceEscrow`. Reuse
   `scripts/invoice-demo.py --signed-only`. It funds an order and settles by
   signature and by buyer approval. Then run `intake`, `sync` and
   `export-beancount`, and run `bean-check` on the output. Expected: two `Paid`
   entries, one marked `BuyerApproval`, and no plugin error for the signed one.
4. Idempotency: run `sync` and `export-beancount` twice; the file bytes are equal.
5. Reorganization: `anvil` snapshot and revert; the connector drops unconfirmed
   logs.

### 2.9 Commands

```text
python -m warrant_ledger sync                 # read new confirmed logs
python -m warrant_ledger intake FILE…         # record UBL documents
python -m warrant_ledger export-beancount     # rewrite the ledger file
python -m warrant_ledger report [--json]      # exceptions report
python -m warrant_ledger check                # self-checks
```

## 3. Phase 2b: Odoo 18 Community adapter

### 3.1 Odoo module `warrant_ledger`

Location: `connectors/ledger/odoo/warrant_ledger/`. Licence LGPL-3, the same as
the Odoo modules it extends. `depends: ["account", "purchase"]`.

Fields on `account.payment`: `x_warrant_event_key` (Char, unique SQL constraint),
`x_warrant_obligation_id`, `x_warrant_document_hash`, `x_warrant_evidence_hash`,
`x_warrant_authenticator`, `x_warrant_order_id`. Fields on `account.move`:
`x_warrant_document_hash`, `x_warrant_obligation_id` (Char, indexed).

The module adds no write path and no payment logic.

### 3.2 Adapter calls (JSON-RPC, `/jsonrpc`)

| Operation | Odoo call |
|---|---|
| `find_booking` | `account.payment` `search_read` on `x_warrant_event_key` |
| `find_bills` | `account.move` `search_read`, domain `move_type = in_invoice`, `state = posted`, `invoice_origin` in the PO names |
| Document of a bill | `ir.attachment` `search_read` with `res_model = account.move`, `res_id`, `mimetype` XML; read `datas` (base64); hash with `warrant-ids facts` |
| `book_payment` | `account.payment.register` `create` with context `active_model = account.move`, `active_ids = [bill]`; then `action_create_payments`; then `write` the `x_warrant_*` fields on the new payment |
| `open_bills` | `account.move` `search_read`, `payment_state` not in `paid`, `in_payment` |

Whether the UBL import keeps the original XML as an attachment of the bill is not
confirmed. Task L2b.3 checks it on the test site. If it does not, the adapter
uses the fallback in spec section 7.1.

### 3.3 Test site

`connectors/ledger/odoo/docker-compose.yml` with images `odoo:18` and
`postgres:16`. A setup script installs `account`, `purchase`, `account_edi_ubl_cii`
and `warrant_ledger`, creates the escrow journal, a vendor, a PO and an API key
for a user with accounting rights only. CI runs the adapter tests against it.
The data are test fixtures. Production data never go into CI.

## 4. Order of work

1. L0.1 to L0.2: `warrant-ids`.
2. L1.1 to L1.6: connector core, beancount, demo.
3. L2b.1 to L2b.3: Odoo module, adapter, test site.
4. L4.1: self-checks.

Phase 3 (drafts and signing tools) follows after the pilot buyer is known.
