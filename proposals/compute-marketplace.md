# Proposal: a compute marketplace in front of Warrant

Status: **proposal, 2026-10-13. Nothing in this document is implemented.**
The starting point is the io.net showcase in
[policy-execution/showcases/ionet_arc](../policy-execution/showcases/ionet_arc/README.md).
The earlier marketplace concept in the parent repository
(`policy-market/marketplace.md`) is a different stack. This document keeps only its idea.

Abbreviations: MCP — Model Context Protocol; GPU — Graphics Processing Unit;
RFB — Request for Builders; TLS — Transport Layer Security; API — Application
Programming Interface.

## 1. Question and short answer

Question: can a marketplace serve as the meeting point for buyers and sellers of
compute, with Warrant as the payment rail, and sign nothing?

Answer: yes, and we do not need to build the marketplace. Circle's Discovery API
can be the listing board. Warrant settles the deal.

- The listing board is a discovery service. It holds no key that any policy pins.
- The buyer keeps the registry key and the acceptance key, as the showcase does today.
- The seller keeps the quote key and the payout address.
- The escrow on Arc stays unchanged.

The cost of this answer is one gap. Nobody can accept a delivery for an absent buyer.
Section 7 states what happens then.

## 2. Decisions from the design interview

The interview on 2026-10-13 fixed these points:

| Decision | Choice |
|---|---|
| Sellers on day one | io.net GPU classes, through the existing adapter. One real provider, labelled as one. |
| Unit of sale | A lease: an authenticated GPU endpoint for a fixed number of hours. |
| Settlement | The simplest path, with a real proof. The proof work belongs to `policy-execution`, not to this document. |
| Marketplace signatures | None. The listing board must not sign anything. |
| Reputation | None for now. |
| Listing board | Circle Discovery API first. Our own board only if Circle declines the listing. |
| Lease structure | One lease is a sequence of short interval tasks. Service for an interval is released only after that interval's acceptance. See section 6.1. |
| `settleBy` | Per interval task: the interval length plus a margin. The first task also covers the provisioning time, which is still to be measured. |
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

The buyer is therefore already its own registry. The listing board does not change this.

## 4. Why credential issuance needs a decision

The vendor credential is the only source of two fields that select: the recipient
address and the category. The checker's `vendor_category_in` and `recipient_equals`
atoms pass when the credential says so. The project invariant states that fields that
select must never come from the text or the model.

If the guardrail signs a credential for any seller the agent picks from a listing,
the agent picks the recipient. The registry key becomes a stamp. The invariant is broken.
The issuance step is therefore the point where a party other than the model decides
that this address is a seller of this category.

### 4.1 The issuance flow

1. The guardrail receives a seller-signed quote. The quote names a recipient.
2. The guardrail looks up the recipient in the buyer's seller list.
3. If the recipient is present and the credential is valid, the flow continues.
4. If the recipient is absent, the guardrail applies the issuance rule from the policy.
5. The rule returns one of three results: issue, ask, or refuse.
6. On issue, the guardrail signs a credential with the buyer registry key. The credential names the recipient, the category, the scope and a validity window.
7. On ask, the guardrail returns a pending state. A human approves or rejects in the guardrail, not in the agent.
8. On refuse, the quote is rejected.

### 4.2 Three issuance rules and their trust assumptions

| Rule | Who decides | Trust assumption | Loss bound if the assumption fails |
|---|---|---|---|
| Human click | A human, once per seller, for the credential validity window | The human reads the listing and the payout address before the click | One seller's leases up to the policy budget |
| Per-seller budget | A rule in the policy | The model can select any listed address. Loss per unvetted seller is bounded. | The per-seller budget, times the number of unvetted sellers, capped by a total budget for unvetted sellers |
| Circle listing match | Circle's review, read by the guardrail over TLS | Circle screened the payout wallet and reviewed the listing. The Discovery response is honest. TLS to `api.circle.com` is intact. | One seller's leases up to the policy budget, for a seller Circle listed |

The simplest release uses the human click. The per-seller budget is the first automation.
The Circle match is a stronger automation and adds one named dependency.

None of the three rules checks delivery quality. They decide only that an address is a
seller. The acceptance signature after the probe decides that a lease was delivered.

## 5. Circle Discovery as the listing board

Measured on 2026-10-13 against `https://api.circle.com/v2/x402/discovery/resources`:

| Fact | Value |
|---|---|
| Resources | 2,854 from 42 providers |
| Categories | 7: SOCIAL_INTELLIGENCE, WEB_SEARCH_RESEARCH, FINANCIAL_ANALYSIS, INFRASTRUCTURE, DATA_ENRICHMENT, PREDICTION_MARKETS, CREATIVE |
| Filters | `category`, `network`, `type` (http or mcp), `maxUsdPrice`, `limit`, `offset` |
| Arc mainnet (`eip155:5042`) | Accepted by 2,195 resources, with USDC at `0x3600…0000` and EIP-3009 transfers |
| Arc testnet (`eip155:5042002`) | Not present in the catalogue |
| Payment schemes | `exact` on 18,070 entries, `upto` on 25, `batch-settlement` on 10 |
| MCP-type resources | 0 |
| GPU leases | None. The closest entry is per-call audio transcription at 10 USDC per call. |
| Authentication | None. No API key. |
| Response | JSON over TLS. Not signed. Cached for one hour. |

How a seller gets listed, per Circle's
[get-listed page](https://developers.circle.com/agent-stack/agent-marketplace/get-listed.md),
read on 2026-10-13:

- The endpoint must return `402 Payment Required` when unpaid and serve the resource when paid.
- The seller publishes an OpenAPI specification for the endpoint.
- The seller submits a form with the endpoint URL, the payout wallet address and a description.
- Circle reviews listings manually. A self-serve flow is announced, not available.
- Circle sanctions-screens the payout wallet and health-checks the endpoint continuously.

### 5.1 How Warrant sellers fit

Every listed resource is a pay-per-call endpoint. A Warrant lease is not. The seller
therefore lists its **quote endpoint**, not the lease:

- The quote endpoint returns 402 when unpaid. It charges a nominal quote fee over x402 on Arc.
- A paid call returns the seller-signed quote: escrow address, policy template, recipient, hardware class, price and maximum duration.
- The resource's `payTo` must equal the recipient in every quote. The guardrail rejects a quote that differs.
- The lease itself settles through `TaskEscrow`, as today.

Two things are not established. Circle has not confirmed that it accepts an endpoint
whose product settles outside x402. The catalogue carries no testnet network, so a
listing names a mainnet payout address and follows the mainnet canary plan.

## 6. The flow with Circle Discovery

1. The buyer agent asks the guardrail for offers. The guardrail queries Circle Discovery with `category`, `network=eip155:5042` and a provider tag.
2. The buyer agent selects a resource and pays the quote fee over x402. The seller returns the signed quote.
3. The guardrail checks the quote signature and the recipient match against the listed `payTo`.
4. The guardrail applies the issuance rule from section 4 for a new seller.
5. The guardrail runs `warrant_evaluate_and_offer` as today. The escrow reserves the funds.
6. The seller server accepts and provisions, as today.
7. The guardrail probes `/health`, signs the acceptance for the current interval, and funds the next interval task. It runs as a background task and does not wait for the agent.
8. The seller server settles the interval and releases the token for the next one.

Steps 5 and 6 are unchanged. Steps 7 and 8 repeat once per interval. Circle appears
only in step 1. If Circle declines the listing, a small board of our own serves step 1
with the same record format.

### 6.1 Interval tasks: bounded exposure for both sides

The showcase signs one acceptance after the first probe, with the buyer's own key.
A fact that one party controls protects that party only. Signed at provisioning, the
seller can take the money and stop the endpoint. Signed at the end, the buyer can use
the hour and never sign. No timing rule fixes this. The exposure must be bounded instead.

The rule in this proposal:

- One lease of N intervals is N escrow tasks, for example four tasks of 15 minutes for one hour. Each task has its own `taskId`, amount, `acceptBy` and `settleBy`.
- The container is provisioned once, at the first task, and keeps running. Each task delivers a fresh worker token for its interval. The `deliverableHash` of the task is the hash of that token.
- The seller releases the token for interval k only after the buyer signed the acceptance for interval k and the seller settled it. No signature, no token.
- The buyer funds task k+1 before interval k ends. A buyer that stops funding gets no further intervals. A seller that stops serving gets no further acceptances.
- The buyer can cancel any task the seller has not accepted. The seller accepts each task at the start of its interval.

Exposure per side is one interval. The seller's residue is the provisioning time of a
buyer that never signs the first interval. That is a no-show, bounded, and paid once
per buyer.

What stays unchanged: the contracts, the guest image, the policy template, and the
amount per task as a policy parameter. The policy validity of 900 seconds in the
showcase already matches a 15-minute interval.

The cost: three transactions per interval, `offer`, `accept` and `settle`, at about
0.01 USDC each on Arc. For a one-hour lease at 0.35 USDC that is about 0.12 USDC of
fees, which is high. Longer intervals lower the fee share and raise the exposure.
The interval length is a policy parameter, not a fixed rule.

The buyer reaches the worker through the seller's `transcribe_audio` tool, which the
showcase already provides. The seller server therefore enforces the interval token
itself, and the worker image needs no change for token rotation. Direct access to the
worker, as the showcase README also describes, would need a token rotation endpoint
in the worker and a new image. That is a later option.

## 7. The absent buyer

The guardrail is a daemon. Step 7 runs without the agent. The buyer is absent only
when the guardrail is offline.

In that case the acceptance never arrives. After `settleBy` anyone can call `refund`.
The buyer recovers the funds. The seller bears the provisioning cost.

This is the fail-closed rule from the project research: a timeout must fail closed.
The listing board must not fill this gap with its own signature. A later release can
let the buyer name an independent prober as reviewer. That prober is not the board.

## 8. What the listing board cannot do

- It cannot redirect money. The recipient is fixed at `offer`, and the credential that names it is signed by the buyer.
- It cannot raise the price. The quote is signed by the seller, and the amount sits inside the buyer's budget cap.
- It cannot change a policy. It never sees a policy key.
- It cannot hold funds. The escrow has no administrator and no fee split.

It can omit a seller, delist one, or serve a stale listing. That is a liveness fault, not a safety fault.

## 9. What stays out

- Reputation. The escrow events on Arc are public, and a score can be computed later from them. RFB-003 in the parent repository describes a suitable formula. It is not part of this release.
- Open seller registration. Day one has one seller.
- Disputes. Warrant has no dispute path. A refused acceptance ends in a refund.
- Fees. Any fee is a separate agreement outside the contract.
- Seller attestation of the allocated hardware. The showcase states that no such attestation exists.
- Real proof settlement in place of the digest verifier. This is `policy-execution` work.

## 10. Effort

| Component | Work | Estimate |
|---|---|---|
| Seller quote endpoint | Return 402, charge a quote fee over x402 on Arc, return the signed quote, publish an OpenAPI specification | 2 days |
| Circle submission | Form, then manual review | Unknown lead time |
| Buyer guardrail | Query Discovery, check the quote signature and the `payTo` match, apply the issuance rule, probe and sign in the background | 2 days |
| Demo | Extend the showcase flow with discovery in front | 1 day |
| Fallback board | Only if Circle declines: a store and one `list_offers` tool | 2 days |

About one engineer-week plus the review wait. No contract, guest or proof changes.

## 11. Open questions

- Does Circle accept a quote endpoint whose product settles outside x402? Ask before the seller work starts.
- How long is the provisioning time on io.net? The first task's `settleBy` depends on it.
- What interval length balances fees against exposure for a 0.35 USDC per hour GPU?
- When does the per-seller budget rule replace the human click?
