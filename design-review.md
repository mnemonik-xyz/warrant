# Warrant for USDC: flow, trust assumptions and attack surface

Status: 2026-09-23. Review notes behind the signer path in
`policy-execution/contracts/src/InvoiceEscrow.sol` (mnemonik-dev/policy-execution#2).
Companion to [`case.md`](case.md) (the case with diagrams) and
[`pitch.md`](pitch.md).

Abbreviations: PO — purchase order; USDC — USD Coin; zkVM — zero-knowledge
virtual machine; LLM — large language model; TCB — trusted computing base;
UBL — Universal Business Language; ERC-20 — Ethereum token standard.

## 1. Flow

**Setup**

1. Deploy `InvoiceEscrow` with immutables: token (USDC), RISC Zero verifier,
   invoice interpreter image ID, `signer` address (zero = proofs only) and
   `proofThreshold` (amounts at or above it need a proof).
2. The buyer approves an `InvoicePolicy`: rule tree, vendor registry key, PO key,
   optional reviewer key, PO bounds, category lexicon, denied terms. Its hash is
   what orders and journals cite.
3. The buyer funds an order: `offer(policyHash, version, poId, vendor, maxTotal,
   signerAllowance, acceptBy, settleBy)`. The full ceiling is transferred.
4. The vendor accepts. From then on the buyer cannot cancel before `settleBy`.

**Per invoice**

5. The invoice (UBL XML) arrives through any channel. The untrusted agent
   assembles the input: document bytes, its per-line claims, the signed vendor
   credential and PO, and `po_spent` read from the chain.
6. `authorize_invoice` runs: parse (Tier 0), admit claims only with checkable
   evidence (Tier 1), verify signatures and bindings, evaluate the policy with
   three-valued logic. Result: Allow with a 14-word journal, Ask, or a denial.
7. Below the threshold: the buyer-run signing service runs step 6 natively and
   signs the journal (`warrant-host invoice-sign`). Anyone relays
   `settleSigned(journal, signature)`.
8. At or above the threshold: a prover runs the same code in the zkVM
   (`invoice-prove`, `wrap`, `export-evm`). Anyone relays `settle(seal, journal)`.
9. The escrow checks the journal against the order and pays the vendor. Each
   obligation ID pays once, across both paths.
10. After `settleBy`, anyone closes the order; the unpaid remainder returns to
    the buyer. The buyer may `revokeSigner(orderId)` at any time; proofs still
    settle.

## 2. Trust assumptions

| Party or component | Trusted for | Compromise buys |
|---|---|---|
| Signing service and key (buyer-run) | Running the exact interpreter honestly on raw inputs | Signatures the policy would not allow, inside the on-chain bounds in §3 |
| Buyer | Their own funds, policy and PO key | Their own risk |
| Vendor registry key | Tax ID → address and category | Cannot redirect funds: the order's recipient is fixed at `offer` and mismatches revert |
| PO key (buyer) | Order lines and ceilings | Bounded by the policy's PO limits |
| Rust interpreter (`authorize_invoice`, parser, checker) | Correct decisions | Verus proves only `evaluate`/`evaluate3`; the rest is tested, not proved |
| RISC Zero verifier and image ID | Proof path only | A wrong image ID at deployment accepts nothing, or the wrong program |
| Token (USDC) | Standard ERC-20 | A blocklisted vendor makes `settle` revert; funds return to the buyer after `settleBy` |
| Relayer | Nothing | Anyone may submit |
| Chain | Timestamps and finality | Windows and deadlines use `block.timestamp` |

**Key property.** A stolen signer key cannot redirect money. The escrow pays only
the accepted vendor of an order. Without a complicit vendor the attacker gains
nothing; with one, the loss is at most `min(remaining ceiling, signerAllowance)`,
in sub-threshold pieces, from funds the buyer already committed to that vendor.

## 3. Attack surface

| Attack | Result | Mitigation |
|---|---|---|
| Stolen signer key, honest vendor | Nothing | Recipient bound on chain |
| Stolen signer key, complicit vendor | Fake invoices under a real order | `proofThreshold` per payment; `signerAllowance` per order; obligation IDs consumed; `revokeSigner` |
| Splitting a large payment into sub-threshold pieces | Same as above | The allowance caps the total, not just each payment |
| Replaying a signed journal | Paid once | `consumed[taskId]` across orders and both paths |
| Replay on another chain or escrow | Rejected | Journal binds chain ID and escrow; the signing digest binds them again |
| Signature malleability | Second valid encoding | OpenZeppelin `ECDSA.recover` rejects high-s; replay is blocked anyway |
| Stale `po_spent` given to the signer or prover | Over-ceiling authorization | Contract uses live `spent` |
| Long validity window signed | Long-lived signature | `settleBy` applies; the window comes from the policy the signer runs |
| Agent feeds the signer pre-computed facts | Bypasses the checker | The service accepts only raw `InvoiceInput`; an operational rule |
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
- **Tested:** 40 Rust tests (fixtures E1–E13 and authority checks), 54 Solidity
  tests including fuzzing on the ceiling and the allowance, removed-check
  experiments on both settlement paths, and cross-language fixtures for the
  journal and the signature.
- **Assumed:** honest signer service, honest registry and buyer keys, a standard
  token, and a correct RISC Zero verifier.

## 5. Open points

- Guest image IDs are build-specific; deploy with the ID of the build that proves.
- The Groth16 wrap needs Docker or a GPU prover; proving takes minutes on a CPU.
- Only USD invoices in UBL are parsed; Factur-X/CII and other currencies go to Ask.
- No per-category or per-period budgets yet; the escrow bounds per order.
