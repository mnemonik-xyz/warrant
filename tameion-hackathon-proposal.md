# Warrant × Tameion: decision proposal for the Canteen × Circle × Arc hackathon

**Status.** Decision proposal v2, 2026-09-22, for review. Supersedes v1 same day.
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
reuse the Cedar evaluator, evidence checker, and warrant-schema work already designed.

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

**What changes for the adaptation:**

| Existing showcase | Tameion adaptation |
|---|---|
| Fiscal receipt (FFD 1.2 tags) as source document | Invoice (Factur-X/Peppol UBL or plain upload); deterministic fields = amounts, tax IDs, PO/vendor-registry match |
| Tier 0 hard facts from tags 1212/1163/1030 | Tier 0 hard facts from deterministic invoice fields + screening quorum (`isBlacklisted`, Chainalysis oracle — the self-enforcing sources per Datum) |
| Child wallet, parent approves policy | Business vault, owner approves policy |
| RUB-kopecks `unit` field | USDC 6-decimals `unit` on Arc |
| Cedar per-item + document-level queries (no universal quantifier — tech-design §11) | Same structure: per-line-item + invoice-level query; `unknown` → Ask-owner in demo, Deny in strict mode |
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
  Cedar evaluation → signed warrant → on-chain verification) is not something other
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

## 4. Decisions already made — do not reopen

From `proving-language-compare.md:194` and its phasing table (:186–192):

1. **Evaluator = the Cedar Rust engine**, `evaluator_id = blake3(binary)` with the
   schema version; evidence checker in Rust with Kani harnesses; **Halmos properties on
   the vault contract** (Phase 1). No custom DSL, no zkVM, no Lean work this window —
   those are Phases 2–4 and belong on the roadmap slide only.
2. **Wallet = the lean custom contract from tech-design §10**, not a Safe and not
   Zodiac Roles. Reasons, now documented: Zodiac Roles is **not deployed on Arc**
   (`../RFB-004/review-2.md` §7), Safe-on-Arc availability is unverified, and the
   contract is ~20 lines doing one thing. The honest cost, stated per house style:
   this is unaudited code in the position of maximum consequence (review-1's warning
   applies). Mitigations: minimal surface (single `pay` function, no delegatecall, no
   external calls except USDC transfer), Halmos properties per the phasing table, the
   fixture suite, and stating the bound as `maxRefill + refill` if a periodic ceiling
   is added. Deploying Zodiac Roles to Arc as a public good is a *stretch goal*, not
   the plan.
3. **Signature scheme = EIP-712 oracle signature on-chain + COSE_Sign1 provenance
   off-chain**, per tech-design §9.5. Not COSE-only on-chain.
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
   oracle" is not "derived on chain." Do not overclaim; zkVM is the honest fix
   (Phase 2). Acceptance: the verifier CLI re-executes every demo warrant live.
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

1. Owner writes a policy in plain English; approves the generated Cedar term;
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
- **D2–5:** port vault contract to Arc (USDC 6-decimals), Halmos properties; Cedar
  evaluator service; warrant schema (unchanged format, invoice facts).
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
