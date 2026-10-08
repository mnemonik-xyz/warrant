# Warrant multi-currency invoices: specification

Version 0.1 · 2026-10-08 · Draft. Status: design only. No code exists.
[tasks.md](tasks.md) tracks the work.

This document specifies a small change to the invoice checker. It lets Warrant
pay invoices in EUR and AMD in USDC, and it closes the precision gap for USD.

Abbreviations: AMD — Armenian dram; EUR — euro; FX — foreign exchange; ISO
4217 — the international standard for currency codes; PO — purchase order;
UBL — Universal Business Language; USD — United States dollar; USDC — USD Coin.

## 1. Problem

The checker pays only USD invoices (`core/src/evidence.rs:464-470`). Any other
currency gives `Ask(NotUsd)` (`evidence.rs:730-731`). The first real vendors are
in Armenia and Latvia. They invoice in AMD and EUR. Today every such invoice goes
to `settleApproved`, which does not check the document.

A second problem is precision. `parse_amount` accepts 6 decimals for any
currency (`evidence.rs:387-413`). USD has 2. The checker therefore accepts
`1.005 USD`, and no test covers it.

## 2. Goals and non-goals

Goals:

1. Pay invoices in USD, EUR and AMD in USDC, with the same checks as USD today.
2. Refuse an amount with more decimals than the currency allows.
3. Keep the conversion exact and deterministic: integer arithmetic only.
4. Keep the journal, the contracts and the Verus proof unchanged.

Non-goals:

- A live FX feed. Version 1 uses a rate that the buyer signs (section 4).
  A signed rate source is planned (section 9).
- PDF invoices. They stay future work.
- Settlement in a token other than USDC.

## 3. Currency table

The checker holds a fixed table of supported currencies and their minor units
from ISO 4217:

| Code | Minor units | Status |
|---|---|---|
| `USD` | 2 | Supported now (with 6 decimals; this change restricts it to 2) |
| `EUR` | 2 | Planned by this change |
| `AMD` | 2 | Planned by this change |

ISO 4217 gives AMD 2 minor units. Armenian invoices often show whole drams. A
whole-dram amount is valid under 2 minor units.

To add a currency later is a change to this table. It changes the checker
version and the image ID.

## 4. Conversion rate

The buyer fixes the rate in the signed purchase order. This is the contract rate
between buyer and vendor.

New fields:

| Struct | Field | Type | Meaning |
|---|---|---|---|
| `PurchaseOrder` | `currency` | `String`, ISO 4217 code | The invoice currency that this order accepts |
| `PurchaseOrder` | `rate_num` | `u64` | USDC base units ... |
| `PurchaseOrder` | `rate_den` | `u64` | ... per this number of invoice minor units |
| `InvoicePolicy` | `currencies` | `Vec<String>` | Currencies the owner allows a PO to name |

Conversion, with `payable_minor` the invoice payable amount in minor units:

```text
amount_usdc = floor(payable_minor × rate_num / rate_den)
```

Rules:

1. The calculation uses `u128`. An overflow, or a result above `u64::MAX`, gives
   `Ask(PayableUnknown)`.
2. The result is rounded down. The vendor never receives more than the signed rate
   gives. The difference is less than one USDC base unit (0.000001 USD).
3. `rate_num = 0` or `rate_den = 0` denies the PO (`InvalidEvidence`).
4. For a USD order the rate is `rate_num = 10000`, `rate_den = 1`: one cent is
   10,000 base units. The checker requires exactly this rate for `USD`. A USD
   order cannot carry a different rate.
5. `po.max_total` stays in USDC base units. It is the buyer's exposure in the
   settlement token.

Example: an EUR order at 1.0850 USD per euro has `rate_num = 1085000`,
`rate_den = 100`. An invoice of 1,234.56 EUR is 123456 minor units. The amount is
`floor(123456 × 1085000 / 100) = 1339497600` base units, which is 1,339.4976 USDC.

## 5. Checker changes

In `parse_invoice` (`evidence.rs:432`):

1. Read `DocumentCurrencyCode`. Every amount must carry the same `currencyID`, as
   today.
2. Look up the minor units in the table. An unknown code gives
   `Ask(UnsupportedCurrency)`.
3. Parse each amount with at most that number of decimals. An amount with more
   gives `Ask(CurrencyPrecision)`. Amounts stay in minor units in `InvoiceFacts`.
4. Replace the field `usd: bool` with `currency: String` and
   `currency_consistent: bool`.

In `authorize_invoice` (`evidence.rs:653`):

1. The PO currency must be in `policy.currencies`. Otherwise `InvalidEvidence`.
2. The PO rate must follow section 4 rules 3 and 4.
3. If the document currency is not the PO currency: `Ask(CurrencyMismatch)`.
4. Convert the payable amount (section 4). The USDC amount goes into the
   `Request`, the evaluator facts and the journal, as today.

New `AskReason` values: `UnsupportedCurrency`, `CurrencyPrecision`,
`CurrencyMismatch`. `NotUsd` is removed.

## 6. What changes and what does not

| Item | Change |
|---|---|
| `CHECKER_VERSION` | 2 → 3 |
| `po_message` bytes | Change: the PO has three new fields |
| Invoice policy hash | Tag `warrant/invoice-policy/v2` → `v3`: the policy has a new field |
| `evidenceHash` | Covers the PO, so it covers the rate. No format change |
| Invoice guest and image ID | New image ID. New receipts in a new directory |
| Journal (15 words) | No change. `amount` is USDC base units, as today |
| `InvoiceEscrow` and other contracts | No change |
| Verus proof of the evaluator | No change: the evaluator sees a `u64` amount, as today |
| Signing service (`invoice-sign`) | No code change: it calls `authorize_invoice` |
| Fixtures and test vectors | Regenerate |

A deployed escrow pins the invoice image ID. The new image needs a new
`InvoiceEscrow` deployment. Old orders keep the old image.

## 7. Tests

Update E11 (EUR invoice) from `Ask` to `Allow` with a signed EUR order. Add:

| Case | Expected |
|---|---|
| EUR invoice, EUR order, rate 1085000/100 | `Allow`, amount as in section 4 |
| AMD invoice, AMD order | `Allow` |
| USD invoice, USD order, rate 10000/1 | `Allow`, amount unchanged from today |
| USD order with any other rate | `Deny(InvalidEvidence)` |
| `1.005 USD` | `Ask(CurrencyPrecision)` |
| `6.000000 USD` | `Ask(CurrencyPrecision)`: EN 16931 allows at most 2 decimals for an amount |
| `6.00 USD` | `Allow` |
| `GBP` invoice | `Ask(UnsupportedCurrency)` |
| EUR invoice, USD order | `Ask(CurrencyMismatch)` |
| PO currency not in `policy.currencies` | `Deny(InvalidEvidence)` |
| `rate_den = 0` | `Deny(InvalidEvidence)` |
| Overflow in conversion | `Ask(PayableUnknown)` |
| Rounding: a result with a fraction | Rounded down |
| One line `currencyID` differs from the document | Ask, as today |

The cross-language fixtures and the Solidity tests keep the 15-word journal. They
need new fixture values only.

## 8. Risk

- **FX risk stays with the buyer.** The rate is fixed for the PO validity window.
  A buyer who wants a short exposure signs a short PO window.
- **A wrong rate is a buyer error, bounded by the PO ceiling.** The owner bounds
  it with `max_po_total`, as today.
- **The agent cannot choose the rate.** It comes from the PO signature only.

## 9. Planned extension: signed rate source

A later version can accept a rate attestation signed by a rate key that the owner
approves in the policy. The attestation names the currency pair, the rate and a
short validity window. The PO then carries a bound, not a fixed rate. This needs
a new evidence type and a new image ID. It is not part of this change.

## 10. Related work

- `ledger-integration/spec.md`: the ledger connector books the USDC amount and
  can record the invoice currency, the invoice amount and the rate.
- `InvoiceTypeCode` is still not read: an `Invoice` with code 381 counts as
  payable. That is a separate small change.
