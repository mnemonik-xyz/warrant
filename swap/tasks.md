# Warrant for swaps: tasks

Status on 2026-10-07: W1 and W2 done against spec version 0.2. Alignment with
spec version 0.3 is open (section W2.1). Specification: [spec.md](spec.md). Implementation
specification: [implementation.md](implementation.md). Code lives in the
`policy-execution` submodule.

Legend: `[x]` done, `[ ]` open, `[-]` deferred to a later step.

## W0 — specification review

- [x] T0.1 Fix the review findings on the specification: unclosed Mermaid
      fence; Bitcoin sighash types; gross approval for fee tokens; Solana
      nonce-advance and Ed25519 instructions.
- [x] T0.2 Decide open questions 1 to 3 (implementation.md section 1).
- [x] T0.3 Write the implementation specification for W1 and W2.
- [x] T0.5 Fix the review findings on PR #7: the CLTV first valid block (code
      and test), one clock for warrant validity, the `approve` and `lock` pair
      under one warrant, the stale status lines.
- [ ] T0.4 Owner sign-off; freeze the schemas.

## W1 — `swap-verified`

- [x] T1.1 Crate skeleton in the workspace; `vstd` pinned like `verified`.
- [x] T1.2 `SwapRule`, `SwapFacts`, `SwapFacts3`, `completes`.
- [x] T1.3 `satisfies` and `kleene` specifications for every atom.
- [x] T1.4 `evaluate3` with the postcondition `== kleene`; `decide`.
- [x] T1.5 `kleene_sound` and `decision_sound`.
- [x] T1.6 Timeout arithmetic: `pending`, `earliest_real`, `latest_real`,
      `timeout_gap`, `reveal_window`, `s11_holds`, `s12_holds`.
- [x] T1.7 Clock-model theorems: height model, time model, S11 and S12
      soundness.
- [x] T1.8 `verify.py` with pinned Verus, `--no-cheating` and mutations
      (including "Ask treated as Allow").
- [x] T1.9 Plain Rust unit tests for the evaluator and the arithmetic.

Acceptance: Verus passes with `--no-cheating`; every mutation fails
verification; `cargo test -p warrant-swap-verified` passes.
Result: 49 verified, 0 errors; 29 of 29 mutations rejected; 12 tests passed.

## W2 — `swap-core`

- [x] T2.1 Crate skeleton; dependencies limited as in implementation.md 2.
- [x] T2.2 `caip`: CAIP-2, CAIP-10, CAIP-19 parsing; family; `Id` mapping.
- [x] T2.3 `types`: legs, locks, timelocks, terms, actions, risk flags.
- [x] T2.4 `jcs`: RFC 8785 canonical JSON; golden tests.
- [x] T2.5 `dsl`: JSON mini-DSL, `SwapPolicy`, `validate_policy`.
- [x] T2.6 `facts`: provenance, quorum agreement, oracle freshness, notional,
      derived clock facts, ledger facts, fact builder.
- [x] T2.7 `profile`: profile parameters; Bitcoin, EVM and Solana profiles;
      contract identity (S7) including the Taproot output derivation.
- [x] T2.8 `tx`: Bitcoin PSBT, EVM EIP-1559 and Solana message decoders;
      intent matching (S24); transaction binding.
- [x] T2.9 `checks`: S1 to S25 with reason codes (spec version 0.2).
- [x] T2.10 `secret` and `ledger`.
- [x] T2.11 `warrant`: payload, hash, record chain, binding verification (S20).
- [x] T2.12 `authorize`: entry and exit pipelines.
- [x] T2.13 Tests: one negative test per check, one fixture per risk flag,
      fault-injection tests 1, 2, 3, 5, 6, 7, 8 and 10 (decision part).
- [x] T2.14 Cross-checks with `rust-bitcoin`; `wasm32` build.

Acceptance: `cargo test -p warrant-swap-core` passes; each check has a test
that fails without the check; `swap-core` builds for `wasm32-unknown-unknown`.
Result: 78 tests passed; 18 of 18 disabled checks caught; wasm32 build succeeds.

## W2.1 — spec version 0.3 gaps

Spec section 13.4 describes each item. Fix D1 to D9 before G1 to G24, because
they break version 0.2 rules too. Each fix adds a test that fails without it.

Defects:

- [x] D1 S5 and S6 on Bitcoin: put the own claim key and refund key in the
      policy. Require counterparty-leg `claim_key` and own-leg `refund_key` to
      equal them at accept, lock and reveal (policy-execution `33f8cdf`; an
      observed lock must also carry its output script).
- [x] D2 Notional is unknown unless the price of each leg is known
      (policy-execution `83e7e57`).
- [ ] D3 Solana: check the escrow account discriminator in `ProgramPin`.
- [ ] D4 Record every fact that the evaluator read, with provenance and the
      observed value.
- [ ] D5 Remove the Bitcoin `min_block_secs > 0` rule (with G1).
- [ ] D6 Subtract `D_margin` in `reveal_window`; run Verus again.
- [ ] D7 Put only fixed reason codes in `reasons`.
- [ ] D8 S20: check the window against the verifier's real time with a skew
      allowance.
- [ ] D9 S22: keep the policy hash with the version; reject a different hash
      at the same version.

Gaps:

- [ ] G1 Clock model with n-block bounds at a stated failure probability, the
      Bitcoin median-time-past lag and the sequencer window. Add `D_refund(B)`
      to S11 and its proof.
- [ ] G2 Reject a relative leg B timelock at accept. Compute the absolute leg A
      timelock from the observed confirmation.
- [x] G3 No signed Bitcoin transaction waits: lock and claim final now; refund
      `nLockTime` from `T` up to the tip, no relative lock (policy-execution
      `33f8cdf`).
- [ ] G4 `lock_id` keys every lock; `<lock_id> OP_DROP` claim leaf; fields
      `claim_key` and `refund_key`.
- [ ] G5 `negotiation` module: bodies, `intent_id`, `terms_hash`, transcript
      rules 1 to 5, receiver checks; `swap_id` from the ACCEPT; `hashlock`,
      `payout_basis` and `valid_until` in the terms.
- [ ] G6 Cap `warrant(accept).valid_until` at the ACCEPT `expires_at`.
- [ ] G7 Warrant fields `class`, `fee_ceiling`, `owner_approval`, `replaces`
      and `onchain_digest`; `"structural"` evaluator id for exits.
- [ ] G8 A reveal after its first broadcast is an exit action.
- [ ] G9 A failed exit check rejects only that transaction. Add claim and
      refund builders from the recorded lock parameters.
- [ ] G10 Fee-only variants and fee raises for each chain family (S19, S21, S24).
- [ ] G11 Bitcoin prepared refund (version 3, pay-to-anchor) and its binding.
- [ ] G12 Bitcoin prevouts from chain facts, not from the PSBT.
- [ ] G13 EVM `approve(spender, 0)` reset and EIP-2612 permit.
- [ ] G14 S10 set of consumed counterparty locks.
- [ ] G15 S27 receiver checks before lock and before reveal.
- [ ] G16 S15 earmarks for open swaps; L1 data fee, Solana rent and fee-payer
      minimum in the worst-case fees.
- [ ] G17 `period_notional_at_most` as `[period, ref_ccy, amount]`.
- [ ] G18 Per-flag unknown state; `ui_multiplier`; EVM reviewed-list reader for
      a proxy and its implementation.
- [ ] G19 Identity atoms from a Mnemonik agent record resolved to `active`.
      Needs the Mnemonik record resolver (planned).
- [ ] G20 EVM beacon, legacy-slot and diamond proxies in S7.
- [ ] G21 Solana loader, ProgramData, code hash and escrow token account in S7.
- [ ] G22 Solana instruction table of spec 4.2: compute bounds, associated
      token account creates, token program, nonce scope. HTLC accounts: done
      (policy-execution `83e7e57`).
- [ ] G23 E2 Ed25519 message builder.
- [ ] G24 Reason codes for S9, S10, S26 and S27.

Done outside this list, from the review of policy-execution#7 (`83e7e57`): no
warrant without a verified ACCEPT of the proposed terms; Bitcoin fee limits
from the profile; Solana lookup tables from chain facts. From the owner's
decision on open question 5 (`33f8cdf`): an `Ask` caused by an unknown price
becomes `Deny` (`PRICE_UNKNOWN`).

Acceptance: every item above has a test that fails without the fix; Verus and
the mutation script pass again after D6 and G1.

## Later steps

- [-] W3 `swap-signer` at tier E0: keys (custody decision); sealing and
      opening negotiation messages with the receiver checks of spec 3.5; Ask
      queue; watchers; durable ledger (S10, S21, S22, S25); anchoring through
      Mnemonik. One failing test for each operational duty S4, S16, S17, S19
      and S25; fault tests 4, 9 and 10. Needs from Mnemonik (planned): a
      `Signer` trait, `verify_cose_payload` and an agent record resolver.
- [-] W4 Venue adapter (Flo.tc `UserSDK`); testnet swap; secret-hygiene audit.
- [-] W5 Tier E1 co-signing; external security review; capped mainnet pilot.
