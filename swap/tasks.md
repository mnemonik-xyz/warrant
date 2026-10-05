# Warrant for swaps: tasks

Status on 2026-10-05: W1 and W2 done. Specification: [spec.md](spec.md). Implementation
specification: [implementation.md](implementation.md). Code lives in the
`policy-execution` submodule.

Legend: `[x]` done, `[ ]` open, `[-]` deferred to a later step.

## W0 — specification review

- [x] T0.1 Fix the review findings on the specification: unclosed Mermaid
      fence; Bitcoin sighash types; gross approval for fee tokens; Solana
      nonce-advance and Ed25519 instructions.
- [x] T0.2 Decide open questions 1 to 3 (implementation.md section 1).
- [x] T0.3 Write the implementation specification for W1 and W2.
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
- [x] T2.9 `checks`: S1 to S25 with reason codes.
- [x] T2.10 `secret` and `ledger`.
- [x] T2.11 `warrant`: payload, hash, record chain, binding verification (S20).
- [x] T2.12 `authorize`: entry and exit pipelines.
- [x] T2.13 Tests: one negative test per check, one fixture per risk flag,
      fault-injection tests 1, 2, 3, 5, 6, 7, 8 and 10 (decision part).
- [x] T2.14 Cross-checks with `rust-bitcoin`; `wasm32` build.

Acceptance: `cargo test -p warrant-swap-core` passes; each check has a test
that fails without the check; `swap-core` builds for `wasm32-unknown-unknown`.
Result: 77 tests passed; 18 of 18 disabled checks caught; wasm32 build succeeds.

## Later steps

- [-] W3 `swap-signer` at tier E0: keys (custody decision), watchers, ledger
      persistence, anchoring through Mnemonik. Fault tests 4, 9 and 10.
- [-] W4 Venue adapter (Flo.tc `UserSDK`); testnet swap; secret-hygiene audit.
- [-] W5 Tier E1 co-signing; external security review; capped mainnet pilot.
