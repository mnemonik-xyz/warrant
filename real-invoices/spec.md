# Real invoices for the Warrant showcase: specification and collection guide

Status: 2026-09-24, revised the same day: invoices are collected as received, never converted or exported. English version; the Russian version is
[`spec.ru.md`](spec.ru.md). Target countries: Armenia and Latvia.

Abbreviations: PO — purchase order; USDC — USD Coin; UBL — Universal Business
Language (OASIS XML standard for business documents); VAT — value-added tax;
TIN — tax identification number; SRC — State Revenue Committee of Armenia;
VID — Valsts ieņēmumu dienests, the Latvian State Revenue Service; PVN —
pievienotās vērtības nodoklis, Latvian VAT; Peppol BIS — Pan-European Public
Procurement On-Line Business Interoperability Specification; EN 16931 — the
European e-invoice semantic standard.

## 1. Why real invoices, and what "real" means here

The hackathon disqualifies synthetic data. Every invoice shown in the demo must
be a document that a real vendor issued to a real buyer for a real delivery.
Amounts, dates, names, tax identifiers and line texts stay as issued. The only
permitted edits are the redactions in §6. An invoice that was "adjusted to fit
the demo" is synthetic and must not be used.

What we do with each invoice: the buyer's agent reads it, the checker verifies
it against a signed vendor credential and a signed purchase order, and the
escrow on Arc pays the vendor in USDC. The vendor credential and the purchase
order are created for the demo by us, from facts the buyer and vendor confirm
(§5); the invoice is not.

## 2. What to collect: the invoice exactly as it arrived

The agent's job is to read what a business actually receives. So collect the
invoice **as received**, and nothing else:

- The email, saved as `.eml` with its attachments, when the invoice came by
  email. This is the normal case in both countries.
- The PDF alone, when it was downloaded from a vendor portal or handed over.
- The XML, when the vendor's system happened to send one (Peppol BIS Billing 3.0
  or another UBL profile). Keep it next to the PDF if both came.
- A scan or a photo, when that is all there is.

Do not convert, re-type, export from a tax portal, or ask the vendor for a
different format. A document produced for the demo is synthetic; a document
that arrived in the ordinary course of business is real. Exporting from the
Armenian SRC system or a Peppol access point is something an accountant might
do; it is not what the agent does, and an invoice obtained that way is not the
input the demo is about.

## 3. What the demo needs to find in the document

The agent extracts these fields; the checker re-verifies each one against the
document and the signed facts. An invoice can lack some of them and still be
useful, as a case that ends in escalation to the buyer.

| Field | Why it matters | If absent or different |
|---|---|---|
| Invoice number | With the seller's tax ID it forms the obligation ID; one payment per obligation | Cannot be paid |
| Seller's tax ID (Armenia: 8-digit TIN; Latvia: `LV` + 11 digits) | Matched against the buyer's signed vendor registry entry | Vendor mismatch; not paid |
| Order or contract reference | Matched against the buyer's signed purchase order | Cannot be matched to an order; not paid |
| Currency | USDC settlement; USD today, AMD and EUR support planned | Escalated to the buyer |
| Amount payable, and totals that add up | The amount that is paid | Escalated to the buyer |
| Lines: description, item code if any, amount | Each line is matched to an order line or to the buyer's word list | Unmatched lines escalate |
| Bank details | Ignored on purpose; payment goes to the registry address | None; a demo point |

Country facts used above: Armenia's TIN is 8 digits issued by the State Revenue
Committee ([Lookup Tax, Armenia TIN guide](https://lookuptax.com/docs/tax-identification-number/armenia-tax-id-guide));
Latvia's VAT number is `LV` followed by 11 digits, issued by VID
([Avalara, Latvian VAT registration](https://www.avalara.com/us/en/vatlive/country-guides/europe/latvia/latvian-vat-registration.html)).
Latvia mandates Peppol BIS Billing 3.0 for invoices to budget institutions since
1 January 2025 ([EY](https://www.ey.com/en_gl/technical/tax-alerts/latvia-to-require-business-to-government-e-invoicing-as-of-1-january-2025)),
so a few Latvian vendors may already send XML; that is a bonus, not a
requirement.

## 4. Currency

Domestic invoices in Armenia are in AMD and in Latvia in EUR. Settlement is in
USDC. Invoices already denominated in USD, typical for export services, need no
conversion rule. Invoices in AMD or EUR are still wanted: they are the case where
the policy has to say how to convert, and until it does they escalate to the
buyer.

## 5. Facts to confirm with the buyer and the vendor

The checker trusts three signed statements that we create for the demo. They
must be based on confirmed facts, not guesses.

**Vendor registry entry** (one per vendor)

- Legal name and country.
- Tax identifier exactly as it appears on the invoices.
- Category of what they supply, in one or two words (for example "software
  services", "hosting", "office supplies").
- A USDC address on Arc testnet that the vendor controls, for receiving demo
  payments. If the vendor cannot provide one, we create a test wallet for them
  and say so in the demo.

**Purchase order** (one per buyer-vendor relationship, or per real order)

- The order or contract number the vendor cites on invoices. If invoices cite
  none, ask the buyer which internal reference they use and whether the vendor
  can add it to the next invoice. Without a reference the invoice cannot be
  matched to an order.
- The ceiling: the total the buyer agreed to pay under that order or contract.
- The order lines: the seller item codes and what each is (category).
- Validity period.

**Acceptance** (optional)

- Whether the buyer has a person who confirms delivery before payment, and
  whether they are willing to sign a short acceptance statement for the demo.

## 6. Consent and redaction

- Written consent from both the buyer and the vendor that the invoice may be
  shown publicly in a hackathon demo and stored in a public repository. One
  sentence in an email is enough; keep the email.
- Personal data of natural persons (names of employees, personal phone numbers,
  personal e-mails, personal ID numbers) may be replaced with "REDACTED". Company
  names, tax identifiers, amounts, dates, line texts and order references stay.
- Bank account details may stay or be redacted; the checker ignores them either
  way. Keeping them makes the "changed bank details are ignored" demo stronger.
- Do not change any amount, date, identifier or line text. If something must be
  hidden that the checker reads, the invoice is not usable for the demo.

## 7. What to collect, per invoice

Deliver one folder per invoice, named `<country>-<vendor-short>-<invoice-number>`:

```
lv-acme-2026-0113/
  received.eml           # the email as received, attachments inside (when by email)
  invoice.pdf            # the attachment or download, byte for byte
  invoice.xml            # only if the vendor's system sent one
  consent.txt            # who consented, when, and how (email subject and date)
  facts.yaml             # the confirmed facts below
```

`facts.yaml` template:

```yaml
country: LV                     # AM or LV
vendor:
  legal_name: "Acme SIA"
  tax_id: "LV40003000000"       # exactly as on the invoice
  category: "software services"
  usdc_address_arc_testnet: "0x..."
  contact: "name, email"        # for questions; not published
buyer:
  legal_name: "..."
  contact: "name, email"        # not published
invoice:
  number: "2026-0113"
  issue_date: "2026-03-04"
  currency: "USD"               # as on the document
  payable_amount: "1320.00"
  order_reference: "PO-77"      # as on the document, or "none"
  received_as: "email+pdf"      # email+pdf | pdf | email+xml | scan
  lines:
    - name: "Annual software license"
      seller_item_code: "SW-1"  # or "none"
      amount: "1000.00"
purchase_order:
  number: "PO-77"
  ceiling: "3000.00"
  currency: "USD"
  lines:
    - seller_item_code: "SW-1"
      category: "software services"
  valid_from: "2026-01-01"
  valid_until: "2026-12-31"
story:
  paid_in_reality: yes          # yes | no | partially
  anomaly: "none"               # none | duplicate | re-issued | changed bank details | over ceiling | unknown line | other
  notes: "..."
```

## 8. The set we want

Minimum eight invoices across the two countries, preferably several months of one
vendor relationship plus the anomalies that occurred in it. Each line below is one
demo moment.

| # | Case | Country | What makes it usable |
|---|---|---|---|
| 1 | Clean invoice, matches the order, USD | AM | Cites the order or contract reference; lines are recognisable against the order |
| 2 | Clean invoice, matches the order, USD | LV | Same |
| 3 | Invoice below the proof threshold | either | Small amount; settles on the signer's word live |
| 4 | Invoice above the proof threshold | either | Larger amount; settles on a pre-generated proof |
| 5 | A line nobody can label | either | A line that matches no order line and no word-list term; escalates, buyer approves |
| 6 | Re-issued or duplicate invoice | either | Two documents for the same delivery, same or new number |
| 7 | Bank details differ from the registry | either | Vendor changed accounts between invoices, or a corrected invoice with new IBAN |
| 8 | Over the order ceiling | either | Sum of invoices under one order exceeds what was agreed |
| 9 | Non-USD invoice | AM or LV | AMD or EUR; shows escalation for currency |

Known gaps to expect, and to note in `story.notes` rather than work around:
invoices in AMD or EUR; scans without a text layer; invoices with several tax
totals or line-level discounts.

## 9. Delivery

- Send folders through the agreed private channel, not through public chat.
- Only files with a `consent.txt` are used.
- The collector keeps the originals; the repository receives the copies after
  redaction and after the buyer and vendor have seen exactly what will be shown.
