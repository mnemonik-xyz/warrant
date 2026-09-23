# Warrant × Tameion: decision proposal for the Canteen × Circle × Arc hackathon

**Status.** Decision proposal v2, 2026-09-22, for review. Supersedes v1 same day.
Updated 2026-09-23 with the RFB alignment and gaps (§3a), and §4 rewritten to match
the implemented code in `policy-execution/`.
This is **not a new design**. It is the decision to adapt the existing Warrant
proof-of-concept design (`warrant/tech-design.md`, `warrant/proving-language-compare.md`,
`warrant/short.md`) from its showcase (a child's wallet governed by fiscal-receipt
tags) to the Tameion hackathon vertical (a business's payables governed by an approved
policy), and the decisions that adaptation forces. Facts about the hackathon are in
`../Tameion-brief.md`; the sibling proposals it must stay consistent with are
`../RFB-001` through `../RFB-005`.

---

## 1. The decision to make

The Tameion hackathon (27 Sep – 10 Oct 2026) requires choosing what to build, for
which RFB, on which stack, optimizing for which judging criterion — in a two-week
window.

**Proposed decision.** Adapt Warrant into **Warrant for USDC**: an agent that runs a
business's payables, where every payment executes only with a *warrant* — a signed,
replayable proof of compliance with a hash-pinned policy — enforced on-chain by a lean
payment vault on Arc. Demo vertical: vendor/contractor invoices, touching RFB-02
(AP/AR), RFB-03 (contractor payments) and RFB-04 (autonomous operator) at once.
RFB-05's screening quorum becomes a warrant fact source, not the product. New repo;
reuse the implemented policy interpreter (`policy-execution/`), and add the evidence
checker designed in `policy-execution/evidence-checker.md`.

**What carries over from the existing design unchanged** (per `tech-design.md`):
the warrant bundle format (§9.5: EIP-712 oracle signature over
`WarrantDigest{wallet, merchant, amount, policy_hash, receipt_hash, decision, nonce,
expires_at, bundle_hash}`, verified on-chain via `ecrecover`; COSE_Sign1 provenance
layer, off-chain in step 1); the vault contract interface (§10: `setPolicy` /
`setOracle` / `pay(WarrantDigest, sig)`, ~20 lines of Solidity); nonce + expiry +
`usedNonce` replay handling; the seven-claim proving structure (§6) and the fixture
suite F1–F9 including the injection-in-name case (F6) and tampered-totals (F8);
the verification-vs-re-execution discipline — the warrant is *verification*
(recorded inputs + pinned logic version hash to the recorded output), never claimed
as re-execution.

*Superseded in part by §4 (2026-09-23):* the signed digest is now the 12-word
authorization journal from `policy-execution/` (13 with `po_id`), and the vault has
no `setPolicy` — the policy is fixed at deployment.

**What changes for the adaptation:**

| Existing showcase | Tameion adaptation |
|---|---|
| Fiscal receipt (FFD 1.2 tags) as source document | Invoice (Factur-X/Peppol UBL or plain upload); deterministic fields = amounts, tax IDs, PO/vendor-registry match |
| Tier 0 hard facts from tags 1212/1163/1030 | Tier 0 hard facts from deterministic invoice fields + screening quorum (`isBlacklisted`, Chainalysis oracle — the self-enforcing sources per Datum) |
| Child wallet, parent approves policy | Business vault, owner approves policy |
| RUB-kopecks `unit` field | USDC 6-decimals `unit` on Arc |
| Cedar per-item + document-level queries (no universal quantifier — tech-design §11) | Warrant policy language: `all`/`any` rule tree plus per-line atoms (`LineLabelsWithin`); `Unknown` → `Ask` via three-valued evaluation |
| Mock OFD signature as source trust root | The *submitting channel* is untrusted by definition (invoices are attacker-controlled text); source_sig becomes "document as received", and trust comes from the evidence checker + deterministic validators, not from the sender |

## 2. Why — read off the judging rubric

Judging: Agentic Sophistication 30% / Traction 30% / Circle Tool Usage 20% /
Innovation 20%. Rules: autonomy bounded by **on-chain enforcement, "not prompts
alone"**; testnet USDC acceptable, mainnet preferred; **synthetic data disqualified**.

- *Agentic sophistication:* the agent ingests invoices, extracts facts, assembles
  warrants, executes payments, escalates — with a decision record that is the product.
- *Circle tool usage:* USDC settlement on Arc (~$0.01, sub-second finality), Paymaster
  for gas, ERC-8004 agent identity registration (live on Arc testnet), one cross-chain
  leg. **The warrant vault is also the answer to a documented Circle gap:**
  developer-controlled Smart Accounts ship no policy engine (`../RFB-002`:148), so
  "every spend control is code we write" — our code is on-chain, verifiable, and
  completing that roadmap rather than competing with it.
- *Innovation:* proof-carrying payments. The warrant chain (evidence-checked facts →
  verified policy evaluation → signed warrant or zkVM receipt → on-chain verification) is not something other
  teams will have.
- *"Not prompts alone":* satisfied structurally — the vault pays only against a valid
  oracle signature over a digest pinned to the approved `policyHash`, with the
  contract's own allowance arithmetic as a second, signature-independent bound.

## 3. Position relative to the sibling proposals

- **vs Quittance (RFB-02):** Quittance enforces approval limits "in code"
  (application layer), with only the destination timelock and sanctions `require`
  on-chain — because Circle wallets ship no policy engine. The warrant vault fills
  exactly that hole: every money-authorizing control becomes deterministic *and*
  on-chain *and* third-party-verifiable. Quittance also mandates that over-limit
  invoices always reach a human regardless of confidence; we adopt that position
  explicitly (§5).
- **vs Recourse (RFB-03):** its `criteriaHash` pins *what was agreed*; a warrant pins
  *a policy evaluated at payment time* and travels with the proof. Its optimistic
  release ("silence authorizes") is the deliberate inversion of our claim ("no valid
  warrant, no payment") — worth one sentence in the pitch, not a component to reuse.
- **vs Waterline (RFB-01):** it admits "residual trust in the off-chain signer,
  bounded by the module's hard caps" and that the on-chain module "cannot enforce
  'only if the forecast says we can afford it'" (`:152`). The warrant is the
  generalization that closes both admissions: a signed, reproducible evaluation of
  off-chain facts, checked by the chain. Cite this — it is the strongest statement
  that the warrant layer is the missing piece across all three proposals.
- **vs Bulkhead/Datum (RFB-04/05):** the reviews' invariants transfer wholesale and
  become acceptance criteria for this build (§6): fields that select must be derived
  on the trusted side and the *derived* values bound into the warrant digest
  (category and obligation-reference, per review 2a/2b); the warrant oracle never
  holds a key that can change on-chain policy (Datum's key-separation rule — Zodiac
  permissions are not directional, so tightening is by withholding signature only);
  "tier the investigation, never tier the prohibition" — screening hard facts are
  gates, never gradient inputs to be outvoted.

## 3a. Alignment with the Requests for Builders (checked 2026-09-23)

RFB texts were re-checked against the live hackathon page
(https://tameion.thecanteenapp.com/) and match `../docs/requests-for-builders/`.
✓ covered by the current design · ~ partial · ✗ not covered.

**Primary: RFB-04 Autonomous Business Operator — example build "PolicyWallet".**
The RFB describes it as "a smart-contract wallet with per-category budgets and
per-transaction approval limits, so the agent's authority is enforced on-chain and
cannot be talked past". That is the warrant vault.

| RFB-04 asks for | Status |
|---|---|
| Budgets and approval limits enforced in the contract, not the prompt | ✓ per-payment cap, lifetime budget, per-PO ceiling, policy immutable once published |
| Per-category budgets | ✗ categories are an allowlist only; no per-category or per-period budgets |
| Escalation to a human only when a policy threshold is hit | ✓ `Ask` outcome |
| Decision log: what was done, why, and what it cost | ✓ warrant binds policy hash, document hash and evidence; ~ agent reasoning not yet recorded |
| One complete workflow run by the agent end to end | ✗ no agent implemented |
| Liquidity monitoring; buying services; moving funds to reserve or yield | ✗ out of scope |

**Workflow inside RFB-04: RFB-02 AP/AR Automation (payables only).**

| RFB-02 asks for | Status |
|---|---|
| Read invoices to work out what is actually owed | ✓ evidence checker design (Tier 0 / Tier 1) |
| Detect duplicate invoices and probable fraud | ✓ obligation ID derived from seller tax ID + invoice number; per-PO ceiling; invoice payment details ignored |
| Match payments to invoices without a human | ✓ payment bound to obligation ID and document hash |
| Screen a vendor's wallet address before paying | ~ dropped from the current design; Arc reverts transfers to or from blocklisted addresses, which is a backstop, not screening |
| Payment timing: early-pay discount against preserving cash | ✗ |
| Receivables and collections | ✗ |

**Narrow: RFB-03 Contractor & Vendor Network Manager.** ✓ milestone release after
verified work (reviewer `Acceptance` path); ~ vendor onboarding (signed registry
credential, no screening); ✗ reputation, discovery, rate negotiation, credit limits.

**Not covered: RFB-01 Treasury** (forecasting, USYC yield, allocation) and
**RFB-05 Compliance** beyond screening results usable as policy facts and
reproducible warrants usable in audits.

**Cross-cutting gap.** The rubric scores an agent that "choose[s] when to pay, and
can explain why". Warrant is the guardrail around that agent; the agent's own
decisions are not yet designed.

**Pitch:** PolicyWallet for RFB-04, demonstrated through an RFB-02 payables
workflow. Gaps to close, in priority order:

1. Per-category and per-period budgets in the vault — named explicitly by
   PolicyWallet. Periodic budgets must be stated as `maxRefill + refill` (§4.2).
2. Agent decision layer: which approved obligations to pay and when (due date,
   early-pay discount, balance on hand), with its reasoning written into the log.
3. Address screening as a policy fact (per §6.4; `isBlacklisted` true blocks).
4. One end-to-end run on Arc testnet with real invoices: receive USDC → check
   balance → pay → log → escalate over the limit. RFB-04 asks for exactly this.

Design for gaps 1–3 on the policy side: `policy-execution/evidence-checker.md`.

## 4. Decisions already made — do not reopen

Rewritten 2026-09-23 to match the implemented code. The v2 decision (Cedar, no
custom DSL, no zkVM this window) was overtaken by the implementation; this section
records what exists and what it commits the build to.

1. **Evaluator = the Warrant typed policy language with a fixed Rust interpreter**
   (`policy-execution/`), not Cedar.
   - Policy is data: a rule tree of `all`, `any`, `amount_at_most`,
     `vendor_category_in`, `accepted`, `deliverable_equals`, `recipient_equals`,
     bounded to 128 nodes and 8 levels. New policies need no new code; a new
     operation is an interpreter upgrade.
   - `evaluate()` has a Verus proof that it matches the declarative rule semantics
     (7 verified, 0 errors; 8 deliberate mutations rejected). The proof covers the
     evaluator only, not `authorize()`, signature checks or parsing.
   - `policy_hash` = SHA-256 over domain-tagged bincode of the policy, including
     trusted issuer keys and scope.
   - Evaluator identity = the RISC Zero guest image ID, plus the evaluator source
     SHA-256 recorded in `verified/verification-results.md`.
   - Why it replaced Cedar: one source runs natively, inside the zkVM guest, and
     under Verus, so the proved code is the executed code.
   - Not present yet, and still required: the evidence checker and three-valued
     evaluation (`evidence-checker.md`), Halmos properties on the vault. The
     earlier Kani plan has no code; drop it unless time allows.
2. **Wallet = a lean custom vault on Arc**, not a Safe and not Zodiac Roles — reasons
   unchanged: Zodiac Roles is **not deployed on Arc** (`../RFB-004/review-2.md` §7),
   Safe-on-Arc availability is unverified. New constraints:
   - the policy hash is fixed at deployment (no `setPolicy`); a new policy means a
     new vault. The budget grows only by deposit. The buyer's PO key cannot change
     policy, and the policy bounds what a PO may authorise;
   - the vault checks the authorization journal against its own policy and scope,
     current time, remaining budget and per-PO spend, and consumes the task ID;
   - honest cost: unaudited code in the position of maximum consequence. Mitigations:
     single `pay` path, no delegatecall, no external calls except the USDC transfer,
     Halmos properties, the fixture suite, and `maxRefill + refill` for any periodic
     ceiling.
   Neither existing prototype meets this yet: `policy-execution` has no vault, and
   the Circom `ProofPolicyVault` still has `setPolicy` and `setBudget`.
3. **Authorization reaches the vault through one interpreter, in three modes**:
   - *Signer mode (live path):* an owner-run service runs the native interpreter and
     signs the journal with EIP-712; the vault checks it with `ecrecover`.
     Sub-second. Trust assumption: the signer key, bounded by the vault's caps.
   - *Receipt mode (trustless):* the RISC Zero guest proves the same authorization;
     the vault calls `IRiscZeroVerifier.verify(seal, imageId, journalDigest)` on our
     own verifier deployment (RISC Zero lists none on Arc). Arc testnet's BN254
     precompiles were verified on 2026-09-23. Costs: a Groth16 wrap that needs x86 +
     Docker, and minutes per payment (the native succinct receipts took 224–236 s).
   - *Tiered mode (target):* the vault accepts both, chosen by amount. Not yet
     implemented; it is a threshold check in `pay()` once both paths exist.
     - Below `proofThreshold`: signer signature or receipt. Payment is immediate.
     - At or above `proofThreshold`: receipt required; a signature is not accepted
       in its place. Payment waits for the proof.
     - **Signer-path cap.** Without it, a stolen signer key could split a large
       drain into many sub-threshold payments with invented task IDs. The vault
       therefore tracks cumulative signer-mode spend against its own ceiling
       (per period, stated as `maxRefill + refill`). Worst-case loss from a signer
       key compromise = min(remaining budget, remaining signer-path allowance).
     - Deployment-time immutables, like the policy hash: `signer`, `imageId`,
       verifier address, `proofThreshold`, signer-path cap. Changing any of them
       means a new vault.
     - Both modes carry the same journal, so the vault's checks (policy, scope,
       time, budget, per-PO spend, task ID) are identical; only the authenticator
       differs.
     - Demo: a small invoice pays in under a second; a large one pays after its
       receipt verifies on Arc. Pre-stage the large proof for the video.
     - Build order: signer mode first, receipt mode once one Groth16 receipt
       verifies on Arc testnet, then the threshold.
   COSE_Sign1 provenance stays off-chain and optional. The Circom prototype is kept
   as a reference only: it proves fast (~1.5 s measured) but requires the owner to
   approve every invoice's facts on-chain, and its development setup allows at most
   4,096 constraints (3,895 used).
4. **Name = Warrant.** It reads correctly in both the family and enterprise contexts.

## 5. Open decisions this file does not settle

1. **Team size and skills** — activates the cuts below. Still unanswered.
2. **Arc feasibility (Phase 0, days 1–2, blocking).** Open items documented across the
   sibling proposals, none verified: can arbitrary contracts be deployed to Arc
   testnet via Arc CLI, and is USDC there a standard ERC-20 our vault can call?
   (`../RFB-001` notes Arc is CCTP-Standard-only and that contract-deployment
   openness was unconfirmed.) If Phase 0 fails, fallback = Base Sepolia for the vault
   + Arc for settlement/USDC movement, and we accept the Circle-usage scoring cost.
3. **Human-tier position.** Adopted, not settled by debate: a valid warrant
   *fully authorizes* within policy bounds (no second human gate — that is the whole
   point of bounded autonomy); decisions the policy cannot affirmatively allow —
   over-cap, `unknown` facts, destination mismatch — resolve to `Ask`, and no payment
   path exists for them. Consistent with Quittance's hard gates and Bulkhead's
   escalation design.
4. **Mainnet vs testnet.** Default Arc testnet; one small mainnet payment only if
   dogfooding lands one.
5. **Cross-chain leg.** CCTP on Arc is Standard-only (minutes, not sub-second), so
   the cross-chain beat cannot be the live on-stage moment. Options: pre-stage the
   leg and show finality on-chain, or cut it and spend the time on the revert beat.

## 6. Known weaknesses and acceptance criteria

Stated plainly; each maps to a fixture or rehearsal task.

1. **The oracle key is a trust assumption.** Every warrant is reproducible from
   public inputs by any verifier (the §7 auditor flow from tech-design), and the
   contract's allowance arithmetic is signature-independent — but "signed by the
   oracle" is not "derived on chain." Do not overclaim; the RISC Zero mode (§4.3)
   is the honest fix, and tiered mode bounds the key's exposure to the signer-path
   cap. Acceptance: the verifier CLI re-executes every demo warrant live.
2. **Select-vs-quantify is the load-bearing invariant.** Category and
   obligation-reference are derived on the trusted side *before* eval, and the
   derived values — not model hints — are bound into the digest. Acceptance: fixture
   from review 2a (model proposes a favorable category) is in the demo set and fails
   in the deterministic layer.
3. **The injection demo must actually work.** Rehearse the injection-in-invoice case;
   the soft category may be fooled, the payment must still Deny via Tier 0 facts,
   and the warrant must show why (fixture F6 pattern). Never demo an attack path
   that wasn't run the morning of recording.
4. **Screening traps if Base is the fallback chain**: Chainalysis oracle address
   differs on Base and fails silently to `false` — assert contract code at startup;
   Tornado Cash screens clean everywhere — use `0x7F367cC41522cE07553e823bf3be79A889DEbe1B`
   and pin the snapshot. Per Datum: `isBlacklisted` true is self-enforcing and
   blocks regardless of any quorum.
5. **Escalation is an attack surface.** The Ask path needs a per-period budget, or
   the demo can be spammed into alert fatigue (Bulkhead review §3).
6. **Arc testnet ≠ mainnet.** The submission's "mainnet preferred" gap is real; the
   demo must not claim production readiness it cannot have.

## 7. The demo (3-minute video)

1. Owner writes a policy in plain English; approves the generated policy rule tree;
   `policyHash` lands on Arc.
2. Agent processes three invoices live:
   - normal — pays in under a second, warrant visible;
   - prompt injection hidden in a line item — soft category fooled, payment Denied
     by Tier 0 facts, warrant shows why;
   - over period cap — resolves to `Ask`; no payment path exists.
3. **The revert beat** (the differentiator per `../RFB-004/review.md`: sign a
   violating transaction directly — a forged or stale warrant, an over-cap amount —
   and watch the vault revert it live. "The difference between demonstrating an
   architecture and asserting one.")
4. Audit screen: replay all warrants via the verifier CLI; show `policyHash`,
   ERC-8004 agent identity, and the bounded-loss exposure number (§8).

## 8. Traction without business development

Constraint: synthetic data is disqualified, so payments must be real.

- **Public demo budget:** a faucet-funded policy vault; anyone submits a real
  invoice and watches the agent pay or refuse it. Live dashboard: warrants issued /
  denied, value moved, **bounded-loss exposure** as a headline number (per the
  RFB-04 review's traction guidance).
- **Dogfooding:** route payments the team actually owes during the window through
  the agent. Real obligations, real value moved.

## 9. Rough plan (14 days)

- **D1–2 (Phase 0, blocking):** Arc deployment feasibility; USDC contract interface
  on Arc; Arc CLI + Circle CLI setup, faucet, Paymaster.
- **D2–5:** vault contract on Arc (USDC 6-decimals, immutable policy), Halmos
  properties; signing service around the existing policy interpreter; `Tri` and
  three-valued evaluation with its Verus extension.
- **D6–9:** agent pipeline — invoice ingestion (Factur-X deterministic parse first,
  LLM extraction with evidence spans second, per Quittance's ordering), Tier 0
  validators, evidence checker, warrant assembly; the demo invoice set + fixtures.
- **D10–11:** audit UI / verifier CLI demo path, ERC-8004 registration, dashboard,
  public demo budget.
- **D12–14:** injection rehearsal, revert rehearsal, video, live-link hardening,
  submission.

## 10. Cuts if the team is 1–2 builders

Cross-chain leg → cut or pre-staged only. Audit UI → verifier CLI + static warrant
viewer. ERC-8004 → stretch. Public demo budget → keep (it is the traction story and
it is cheap). Halmos properties → keep at least the nonce/expiry/policyHash
invariants; cut the rest.
