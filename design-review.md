# Warrant for USDC: flow, trust assumptions and attack surface

Status: 2026-09-24. Review notes behind the signer, approval and signing-service design in
`policy-execution/contracts/src/InvoiceEscrow.sol` and `host/src/signer.rs`.
Companion to [`case.md`](case.md) (the case with diagrams) and
[`pitch.md`](pitch.md).

Abbreviations: PO — purchase order; USDC — USD Coin; zkVM — zero-knowledge
virtual machine; LLM — large language model; TCB — trusted computing base;
UBL — Universal Business Language; ERC-20 — Ethereum token standard.

## 1. Flow

**Setup**

1. Deploy `InvoiceEscrow` with three immutables: token (USDC), RISC Zero verifier
   and invoice interpreter image ID. Nothing about signers is fixed here.
2. The buyer approves an `InvoicePolicy`: rule tree, vendor registry key, PO key,
   optional reviewer key, PO bounds, category lexicon, denied terms. Its hash is
   what orders and journals cite. The signing service gets a copy of this file.
3. The buyer funds an order: `offer(Terms)` with policy hash and version, order
   number, vendor, ceiling, `signer` address, `signerAllowance`, `proofThreshold`,
   `acceptBy`, `settleBy`. The full ceiling is transferred. A zero signer means
   proofs and approvals only; a signer needs a nonzero allowance and threshold and
   cannot be the vendor.
4. The vendor accepts. From then on the buyer cannot cancel before `settleBy`.

**Per invoice**

5. The invoice (UBL XML) arrives through any channel. The untrusted agent
   assembles a `SignRequest`: document bytes, its per-line claims, the signed
   vendor credential and PO, optional acceptance. It cannot include a policy or a
   spend figure; the type rejects unknown fields.
6. Below the threshold: the buyer-run signing service reads the order from the
   escrow (state, policy hash, signer, spend, allowance, threshold, deadline),
   refuses unless the order names its key and is live, runs `authorize_invoice`
   with its own policy and the live spend, and signs the journal on Allow.
   Anyone relays `settleSigned(journal, signature)`.
7. At or above the threshold: a prover runs the same code in the zkVM
   (`invoice-prove`, `wrap`, `export-evm`) on the full `InvoiceInput`. The
   prover is untrusted, so it may hold any input; the contract's live checks
   bound it. Anyone relays `settle(seal, journal)`.
8. Ask: the service writes an ask record (reasons, obligation ID, document hash,
   payable) and signs nothing. The buyer reads the invoice and, if they agree,
   calls `settleApproved(orderId, obligationId, amount, documentHash)` with
   their own key.
9. The escrow checks the journal or the approval against the order and pays the
   vendor. Each obligation ID pays once, across all three paths.
10. After `settleBy`, anyone closes the order; the unpaid remainder returns to
    the buyer. The buyer may `revokeSigner(orderId)` at any time; proofs and
    approvals still settle.

## 2. Trust assumptions

| Party or component | Trusted for | Compromise buys |
|---|---|---|
| Signing service and key (buyer-run, named per order) | Running the exact interpreter on the agent's raw request, its own policy and the live order | Signatures the policy would not allow, inside that order's allowance and threshold |
| Buyer | Their own funds, policy, PO key, and approvals of undecided invoices | Their own risk; approval pays only the accepted vendor within the ceiling |
| Vendor registry key | Tax ID → address and category | Cannot redirect funds: the order's recipient is fixed at `offer` and mismatches revert |
| PO key (buyer) | Order lines and ceilings | Bounded by the policy's PO limits |
| Rust interpreter (`authorize_invoice`, parser, checker) | Correct decisions | Verus proves only `evaluate`/`evaluate3`; the rest is tested, not proved |
| RISC Zero verifier and image ID | Proof path only | A wrong image ID at deployment accepts nothing, or the wrong program |
| Token (USDC) | Standard ERC-20 | A blocklisted vendor makes `settle` revert; funds return to the buyer after `settleBy` |
| Relayer | Nothing | Anyone may submit |
| Chain | Timestamps and finality | Windows and deadlines use `block.timestamp` |

**Key property.** A stolen signer key cannot redirect money. The escrow pays only
the accepted vendor of an order. Without a complicit vendor the attacker gains
nothing; with one, the loss is at most `min(remaining ceiling, signerAllowance)`
of the orders that name that key, in sub-threshold pieces, from funds the buyer
already committed to those vendors. Orders naming other keys are untouched.

## 3. Attack surface

| Attack | Result | Mitigation |
|---|---|---|
| Stolen signer key, honest vendor | Nothing | Recipient bound on chain |
| Stolen signer key, complicit vendor | Fake invoices under a real order | `proofThreshold` per payment; `signerAllowance` per order; only orders naming that key; obligation IDs consumed; `revokeSigner` |
| Splitting a large payment into sub-threshold pieces | Same as above | The allowance caps the total, not just each payment |
| Replaying a signed journal | Paid once | `consumed[taskId]` across orders and both paths |
| Replay on another chain or escrow | Rejected | Journal binds chain ID and escrow; the signing digest binds them again |
| Signature malleability | Second valid encoding | OpenZeppelin `ECDSA.recover` rejects high-s; replay is blocked anyway |
| Stale `po_spent` given to the signer or prover | Over-ceiling authorization | The service reads `spent` from the escrow; the contract uses live `spent` on every path |
| Long validity window signed | Long-lived signature | `settleBy` applies; the window comes from the policy the signer runs |
| Agent feeds the signer a policy or spend figure | Bypasses the checker or the ceiling | `SignRequest` rejects unknown fields; the policy is the service's own file; refused before evaluation |
| Signer key used on an order that names another signer | Cross-order signing | Contract recovers against the order's `signer`; the service refuses to sign for such orders |
| Buyer approves a fabricated invoice | Buyer pays their own vendor | Their own funds, the accepted vendor, within the ceiling; a later proof of the same obligation reverts |
| Vendor named as its own signer | Vendor signs its own invoices | `offer` rejects `signer == recipient` |
| Prompt injection in an invoice line | Model mislabels a line | Selecting fields never come from text; a wrong label can only cause Ask |
| Payment details printed on the invoice | Redirect | Ignored: address comes from the vendor credential |
| Duplicate invoice, new number | Double payment | Obligation ID = seller tax ID + invoice number; per-PO ceiling |
| Order-ID squatting | Denial of service | Squatter's funds can only pay the same vendor under the same policy; use unguessable order numbers |
| Vendor and agent collude with real credentials | Fake invoices within a real PO | Bounded by the PO ceiling; the checker verifies text, not truth |
| Malicious XML (DTD, entity expansion) | Parser abuse | Own restricted parser: no DTD, size and depth limits |

## 4. What is proved, tested, or assumed

- **Proved (Verus):** the rule evaluator matches its specification; Allow and
  Deny are sound for every completion of unknown facts. 16 obligations, 14
  deliberate bugs rejected.
- **Tested:** 40 Rust tests in the checker (fixtures E1–E13 and authority checks)
  and 3 in the signer service, 57 Solidity tests including fuzzing on the ceiling
  and the allowance, per-order signer isolation and buyer-approval bounds,
  removed-check experiments on the settlement paths, and cross-language fixtures
  for the journal and the signature. The local demo exercises all three paths,
  a smuggled `po_spent` and an unnamed signer.
- **Assumed:** honest signer service (per order), honest registry and buyer keys,
  an honest RPC endpoint for the service's reads (a lying endpoint can only make
  it refuse or sign something the contract then rejects), a standard token, and a
  correct RISC Zero verifier.

## 5. Open points

- Guest image IDs are build-specific unless built with `RISC0_USE_DOCKER=1`;
  deploy with the reproducible ID. Not yet exercised on a Docker machine.
- The Groth16 wrap needs Docker or a GPU prover; proving takes minutes on a CPU.
- Only USD invoices in UBL are parsed; Factur-X/CII and other currencies go to Ask.
- No per-category or per-period budgets yet; the escrow bounds per order.
