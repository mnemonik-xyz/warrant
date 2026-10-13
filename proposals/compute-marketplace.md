# Proposal: a compute marketplace in front of Warrant

Status: **proposal, 2026-10-13. Nothing in this document is implemented.**
The starting point is the io.net showcase in
[policy-execution/showcases/ionet_arc](../policy-execution/showcases/ionet_arc/README.md).
The earlier marketplace concept in the parent repository
(`policy-market/marketplace.md`) is a different stack. This document keeps only its idea.

Abbreviations: MCP — Model Context Protocol; GPU — Graphics Processing Unit;
RFB — Request for Builders.

## 1. Question and short answer

Question: can a marketplace serve as the meeting point for buyers and sellers of
compute, with Warrant as the payment rail, and sign nothing?

Answer: yes.

- The marketplace is a discovery service. It lists sellers and relays quotes.
- The marketplace holds no key that any policy pins. It is not in the money path.
- The buyer keeps the registry key and the acceptance key, as the showcase does today.
- The seller keeps the quote key and the payout address.
- The escrow on Arc stays unchanged.

The cost of this answer is one gap. Nobody can accept a delivery for an absent buyer.
Section 6 states what happens then.

## 2. Decisions from the design interview

The interview on 2026-10-13 fixed these points:

| Decision | Choice |
|---|---|
| Sellers on day one | io.net GPU classes, through the existing adapter. One real provider, labelled as one. |
| Unit of sale | A lease: an authenticated GPU endpoint for a fixed number of hours. |
| Settlement | The simplest path, with a real proof. The proof work belongs to `policy-execution`, not to this document. |
| Marketplace signatures | None. The marketplace must not sign anything. |
| Reputation | None for now. |
| Scope | As simple as possible. |

## 3. Starting point: the showcase as implemented

One buyer agent talks to one seller MCP server. The flow has these steps:

1. The buyer agent calls `list_suitable_hardware` and `propose_deployment` on the seller server.
2. The buyer guardrail checks the budget and the duration, derives the policy hash, and calls `offer` on `TaskEscrow`.
3. The seller server reads the task, calls `accept`, and provisions a worker container.
4. The buyer agent probes `/health` with the worker token.
5. The buyer guardrail signs an acceptance with the buyer acceptance key.
6. The seller server evaluates the policy natively and calls `settle`.

Two keys authorize facts in this flow. `init.py` generates both on the buyer side:

- `registry.key` signs the vendor credential: recipient, category, scope and validity.
- `buyer_acceptance.key` signs the acceptance: task, deliverable hash, recipient and amount.

The buyer is therefore already its own registry. The marketplace does not change this.

## 4. What the marketplace is

The marketplace is one MCP server that stands in front of many seller MCP servers.
On day one it stands in front of one. It exposes two tools:

- `list_offers(category, constraints)` returns listings that match.
- `get_quote(listing_id, duration_hours)` forwards the request to the seller server and returns the quote.

The marketplace stores listings, serves them, and forwards quote requests. It does nothing else.

### 4.1 Who signs what

| Object | Signer | Reader |
|---|---|---|
| Listing | The seller, with the seller key | The marketplace, the buyer guardrail |
| Quote | The seller, with the seller key | The buyer guardrail |
| Vendor credential | The buyer, with the buyer registry key | The checker |
| Acceptance | The buyer, with the buyer acceptance key | The checker |
| Authorization journal | The checker, through a proof or a named signer | The escrow |
| Nothing | The marketplace | — |

### 4.2 The listing

A listing is a signed record with these fields:

- seller payout address, which must equal the recipient in every quote;
- category, from the policy taxonomy, such as 42 for GPU transcription;
- hardware class and hourly price;
- maximum lease duration;
- seller MCP server URL;
- validity window;
- the seller signature over all fields above.

A quote is the existing `propose_deployment` response, signed by the seller key.
Its `recipient` must equal the listing's payout address. The buyer guardrail rejects a quote that differs.

## 5. The flow with the marketplace

1. The buyer agent calls `list_offers` on the marketplace and selects a listing.
2. The buyer agent calls `get_quote`. The marketplace forwards it and returns the seller-signed quote.
3. The buyer guardrail checks the listing signature, the quote signature and the recipient match.
4. If the seller is new to this buyer, the guardrail issues a vendor credential with the buyer registry key. The policy can require a human click for this step, or allow it under a per-seller budget.
5. The guardrail runs `warrant_evaluate_and_offer` as today. The escrow reserves the funds.
6. The seller server accepts and provisions, as today.
7. The guardrail probes `/health` and signs the acceptance as a background task. It does not wait for the agent.
8. The seller server settles, as today.

Steps 5 to 8 are unchanged. The marketplace appears only in steps 1 and 2.

## 6. The absent buyer

The guardrail is a daemon. Step 7 runs without the agent. The buyer is absent only when the guardrail is offline.

In that case the acceptance never arrives. After `settleBy` anyone can call `refund`. The buyer recovers the funds. The seller bears the provisioning cost.

This is the fail-closed rule from the project research: a timeout must fail closed. The marketplace must not fill this gap with its own signature, because the interview excluded marketplace signatures. A later release can let the buyer name an independent prober as reviewer. That prober is not the marketplace.

## 7. What the marketplace cannot do

- It cannot redirect money. The recipient is fixed at `offer`, and the credential that names it is signed by the buyer.
- It cannot raise the price. The quote is signed by the seller, and the amount sits inside the buyer's budget cap.
- It cannot change a policy. It never sees a policy key.
- It cannot hold funds. The escrow has no administrator and no fee split.

It can omit a seller or serve a stale listing. That is a liveness fault, not a safety fault.

## 8. What stays out

- Reputation. The escrow events on Arc are public, and a score can be computed later from them. RFB-003 in the parent repository describes a suitable formula. It is not part of this release.
- Open seller registration. Day one has one seller.
- Disputes. Warrant has no dispute path. A refused acceptance ends in a refund.
- Fees. Any marketplace fee is a separate agreement outside the contract.
- Seller attestation of the allocated hardware. The showcase states that no such attestation exists.
- Real proof settlement in place of the digest verifier. This is `policy-execution` work.

## 9. Effort

| Component | Work | Estimate |
|---|---|---|
| Listing and quote formats | Two signed records, unknown fields rejected | 1 day |
| Marketplace MCP server | `list_offers`, `get_quote`, a listing store, forwarding to seller servers | 2 days |
| Seller server | Sign listings and quotes with the seller key | 1 day |
| Buyer guardrail | Check both signatures, issue a credential for a new seller, probe and sign in the background | 2 days |
| Demo | Extend the showcase flow with the marketplace in front | 1 day |

About one engineer-week. No contract, guest or proof changes.

## 10. Open questions

- Should credential issuance for a new seller require a human click, or a per-seller budget in the policy?
- Should the marketplace also publish listings to the Circle Discovery API, so agents find them through the existing channel?
- How long must `settleBy` be, so that provisioning on io.net finishes before the refund window opens?
