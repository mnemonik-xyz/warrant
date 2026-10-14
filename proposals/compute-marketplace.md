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
| Lease structure, first release | One lease is a sequence of short interval tasks. Service for an interval is released only after that interval's acceptance. See section 6.1. |
| Lease structure, target | One escrow order for the whole lease, settled per interval against buyer-signed vouchers. Needs a lease guest. See section 6.2. |
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

Interval tasks are the first release, not the target. The lease exists only in the
seller's session and the guardrail's loop. The chain sees N unrelated tasks. Either
side can walk away at an interval boundary with no record, and the seller can reprice
each interval. Section 6.2 states the target that removes these limits.

### 6.2 Target: one escrow order per lease

`InvoiceEscrow` already holds the model the target needs. It checks only the fifteen
journal words against the order. It knows nothing about invoices. A lease is an order
with `poId` as the lease identifier and `poMaxTotal` as the ceiling.

The target design:

- The buyer funds one order for the whole lease: rate, interval length, maximum intervals and deadline in the policy hash, the ceiling reserved at `offer`.
- The seller accepts the whole lease once, at a fixed rate.
- After each interval the buyer signs a voucher: lease identifier, interval index, token hash.
- The seller settles interval k with that voucher. The obligation is `hash(lease, k)`, so each interval pays once. The amount is the rate. The escrow enforces the ceiling, the deadline and single payment per interval.
- The seller chooses when to settle. It can settle late and in batches. A missing voucher stops the next token, as in section 6.1.
- After `settleBy`, the unpaid remainder returns to the buyer.

What the target adds over interval tasks:

- The agreement is on chain. A seller that stops has unpaid intervals on an accepted order. A buyer that stops has reserved funds until `settleBy`. Neither can reprice.
- Transactions drop from 3N to N plus 2.
- The on-chain record shows one lease with k paid intervals.

What the target does not add: the chain still cannot see the GPU. The checker verifies
signatures and arithmetic. Delivery evidence stays a buyer-signed voucher, and the
seller's defence stays the interval token.

What the target costs, in `policy-execution`:

- A lease evidence module in `core`: verify the voucher against the acceptance key in the policy, compute the amount, derive the obligation. The signature code exists for the task path.
- A lease guest in `methods`, three host subcommands, fixtures shared with the Solidity tests, a catalogue template, a mock-verifier path for the showcase.
- A new deployment of `InvoiceEscrow` pinned to the lease image. No contract change.
- The lease checker is tested, not proved. The Verus proof covers the evaluator only.

About two engineer-weeks, plus the same orchestration as section 6.1. The orchestration
carries over: fund once instead of N times, settle against an order instead of a task.

One operational point: a real proof per interval is minutes on the recorded sample.
The signature path of `InvoiceEscrow` covers it. Below the threshold, the buyer's
guardrail acts as the named signer and countersigns the journal it already agreed to
when it signed the voucher. If the buyer withholds that countersignature, the seller
proves the same voucher and settles through the proof path.

### 6.3 The lease evidence module

The module follows the solver path: mandatory gates first, the rule tree last. It
reuses `Acceptance` as the voucher, `VendorCredential` as the seller credential, the
existing `verify`, and the fifteen-word journal layout of the invoice path. Nothing
changes in Solidity.

```rust
// core/src/lease.rs
pub const CHECKER_VERSION: u32 = 1;

pub struct LeasePolicy {
    pub version: u64,
    pub customer: Address,        // the funding buyer, bound into the journal
    pub scope: Scope,             // chain, escrow, token
    pub valid_after: u64,
    pub valid_until: u64,
    pub registry_key: Vec<u8>,    // vouches for the seller; the buyer's own key today
    pub acceptance_key: Vec<u8>,  // signs the interval vouchers
    pub checker_version: u32,
    pub lease_id: Hash,           // poId on chain
    pub rate: u64,                // USDC atomic units per interval
    pub max_intervals: u32,       // ceiling = rate * max_intervals = poMaxTotal
    pub rule: Rule,
}

pub struct LeaseInput {
    pub policy: LeasePolicy,
    pub request: Request,         // task_id = obligation, deliverable_hash = token hash
    pub interval: u32,
    pub vendor: VendorCredential,
    pub vendor_signature: Vec<u8>,
    pub acceptance: Acceptance,   // the voucher
    pub acceptance_signature: Vec<u8>,
}

pub struct LeaseAuthorization {
    pub authorization: Authorization,
    pub lease_id: Hash,
    pub ceiling: u64,
    pub customer: Address,
}
// journal(): the 12 base words, then lease_id, ceiling, customer,
// byte for byte the InvoiceAuthorization layout.

pub fn obligation_id(lease_id: &Hash, interval: u32) -> Hash {
    hash_tagged(b"warrant/lease-obligation/v1", &(lease_id, interval))
}

pub fn authorize_lease(input: &LeaseInput) -> Result<LeaseAuthorization, LeaseError>
```

`authorize_lease` checks, in this order:

1. Policy: version, scope, both keys, checker version, rate and maximum intervals nonzero, no overflow in the ceiling, rule valid with the invoice flag off.
2. Request: scope, amount equals the rate, recipient nonzero, `task_id` equals `obligation_id(lease_id, interval)`, interval below the maximum.
3. Credential: scope, recipient equals the request recipient, signature under the registry key.
4. Voucher: scope, `task_id`, `deliverable_hash`, recipient and amount equal the request, `accepted` true, signature under the acceptance key.
5. Validity window: the intersection of the policy, credential and voucher windows.
6. Facts: amount, category, accepted, deliverable, recipient. Then `evaluate`.
7. Evidence hash over the checker version, the credential and the voucher.

The module does not know the spent ceiling. The contract checks that. It does not
know whether interval k minus one was paid. Each interval is its own obligation. It
does not know whether the GPU ran. Nobody can check that.

The rest of the delta:

| Piece | Work |
|---|---|
| `methods/lease-guest` | Read `LeaseInput`, call `authorize_lease`, commit the journal. Add the name to `build.rs`. |
| Host | `lease-image-id`, `lease-evaluate`, `lease-execute`, `lease-prove`, copied from the solver ones. |
| Signer path | `signer_digest` and `sign_journal` from `evidence.rs` apply unchanged. |
| Fixtures | One lease journal for the Solidity test that mutates all fifteen words. |
| Template | `templates/lease-v1.json` with rate, interval and ceiling as parameters. |
| Deployment | `DeployInvoice.s.sol` with the lease image ID. |
| Tests | The positive path, every gate, removed-check mutations. |

About one engineer-week. The guardrail needs no new signing tool. `warrant_sign_acceptance`
with a derived `task_id` is the voucher. The Verus proof covers the evaluator only. The
lease checker is tested, not proved, like the other two checkers.

### 6.4 What the seller's proof says, and what a cheating buyer can do

The proof the seller presents at settlement is a RISC Zero receipt for the lease
image, or the buyer's countersignature on the same journal below the threshold. It
establishes one statement: under policy hash P, a voucher signed by the buyer's
acceptance key exists for lease L and interval k, with token hash T, recipient R and
amount equal to the rate, and the seller holds a valid credential. The contract then
checks the order, the ceiling, the deadline, and that interval k was not paid before.

The proof says nothing about the GPU. The evidence of service is the buyer's signature,
which the buyer gives after the interval was served. The seller's defence is the
interval token: no voucher, no next token.

What a buyer can try, and what happens:

| Attempt | Result |
|---|---|
| Use interval k, refuse to sign | No token for k plus one. The seller loses one interval. The buyer loses the rest of the lease and keeps the ceiling locked until `settleBy`. |
| Sign, then try to take the money back | Impossible. After `accept` the buyer cannot close before `settleBy`. A consumed obligation stays paid. |
| Sign a voucher with a wrong amount, recipient or token | The checker rejects it. Same as a refusal. |
| Sign a voucher with a window too short to settle | The seller checks the window before it releases the next token. A voucher the seller cannot settle counts as a refusal. |
| Revoke the signer mid-lease | `revokeSigner` only tightens. The seller settles the same voucher through the proof path. |
| Issue a seller credential that expires mid-lease | The seller checks at `accept` that the credential window covers the whole lease plus a settlement margin. |
| Pin a rule that no voucher can satisfy | The seller inspects the policy before `accept`, as the showcase already does when it verifies the policy hash. |
| Fund less than the ceiling | Impossible. `offer` reserves the whole ceiling. |
| Redirect the payment | Impossible. The recipient is fixed at `offer`. |
| Refuse to sign interval zero after provisioning | The seller loses the provisioning minutes. This is the no-show residue. |

The seller's rules before `accept` are therefore part of the design: the policy names
the agreed keys and rate, the rule passes for a sample voucher, and the credential and
policy windows cover the lease. The seller's rules during the lease are two: release a
token only against a settleable voucher, and settle each voucher inside its window.

The seller can cheat symmetrically in one way: take the token fee for interval k and
stop. The buyer then signs nothing more and loses nothing beyond interval k, because
it signs after service. A seller cannot settle without a voucher, and cannot settle
early, because the guardrail sets each voucher's `valid_after` to the end of its
interval and the contract enforces the window.

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
- The lease guest and the lease order of section 6.2. This is the target, after the first release.

## 10. Effort

| Component | Work | Estimate |
|---|---|---|
| Seller quote endpoint | Return 402, charge a quote fee over x402 on Arc, return the signed quote, publish an OpenAPI specification | 2 days |
| Circle submission | Form, then manual review | Unknown lead time |
| Buyer guardrail | Query Discovery, check the quote signature and the `payTo` match, apply the issuance rule, probe and sign in the background | 2 days |
| Interval tasks | Lease session on the seller, interval loop in the guardrail, tests | 3 to 4 days |
| Demo | Extend the showcase flow with discovery in front | 1 day |
| Fallback board | Only if Circle declines: a store and one `list_offers` tool | 2 days |

About two engineer-weeks plus the review wait for the first release. No contract, guest or proof changes. The target of section 6.2 adds about two engineer-weeks in `policy-execution`.

## 11. Open questions

- Does Circle accept a quote endpoint whose product settles outside x402? Ask before the seller work starts.
- How long is the provisioning time on io.net? The first task's `settleBy` depends on it.
- What interval length balances fees against exposure for a 0.35 USDC per hour GPU?
- When does the lease guest start? It is the next `policy-execution` guest after the real proof settlement.
- When does the per-seller budget rule replace the human click?
