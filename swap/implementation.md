# Warrant for swaps: implementation specification for W1 and W2

Version 0.2 · 2026-10-07 · Written for spec version 0.2. Status: **W1 and W2
implemented against spec version 0.2** at `policy-execution` commit `e9e9d31`
(section 5). Companion to [the swap specification](spec.md). Task list:
[tasks.md](tasks.md).

This document proposes the decisions of step W0, pending owner sign-off
(tasks.md T0.4). It specifies the two crates of steps W1 and W2. Section
references like "spec 7.3" point to [spec.md](spec.md).

Spec version 0.3 changes several rules. Spec section 13.4 lists each
difference from the code with an id: D1 to D9 for defects, G1 to G24 for gaps.
The sections below that version 0.3 changes have a note with these ids. Where
this document and spec 13.4 differ, spec 13.4 gives the target.

---

## 1. Decisions of step W0

| # | Question (spec 14) | Decision | Effect on W1 and W2 |
|---|---|---|---|
| 1 | Policy disclosure | The policy term goes to an auditor only. The counterparty sees the warrant, not the policy. | The warrant carries `policy_hash`, not the policy. |
| 2 | Key custody | Deferred to W3. Only `swap-signer` touches keys (spec 13.2). | None. `swap-core` produces unsigned payloads. |
| 3 | DSL | The JSON mini-DSL of spec 6.3. | `swap-core` parses it into the verified `SwapRule`. |

Other choices that this document makes, all inside the spec's freedom:

- **Identifiers in the evaluator.** The verified evaluator compares 32-byte
  identifiers only. `swap-core` maps every CAIP string to
  `sha256(canonical CAIP string)`. Verus then never handles strings.
- **Amounts in the warrant payload.** JCS (RFC 8785) represents numbers as
  IEEE 754 doubles. Base-unit amounts exceed 2^53 (for example wei). The
  payload therefore carries amounts as strings of decimal digits. They stay
  integers in base units (spec 3.2); the string is only the encoding.
- **Bytes in the payload.** Lowercase hexadecimal, no `0x` prefix.
- **Hashes.** `terms_hash`, `inner_sig_hash`, warrant hashes and the Solana
  transaction binding use BLAKE3. CAIP identifiers use SHA-256 (as above).
- **Relative timelocks.** `swap-core` converts a relative timelock to an
  absolute height or time from the observed confirmation of the lock. The
  verified arithmetic handles absolute timelocks only. The responder's leg
  (leg B) needs an absolute timelock: a relative one starts at an unknown
  future confirmation, and S11 could not bound it.
- **Own Bitcoin coins** are Taproot key-path outputs, so the signer computes
  every BIP 341 sighash itself. PSBT version 0 only.
- **Validity windows** of warrants use the signer's real time, for every action
  (spec 4.1).
- **Reference HTLC interfaces.** The EVM and Solana decoders check calls
  against a reference interface (section 4.6). A venue adapter (W4) maps a
  different contract onto the same intent.

## 2. Crate layout

The crates join the `policy-execution` workspace. The invoice crates do not
change, so the invoice guest image id does not change (spec 13.1).

```text
policy-execution/
  swap-verified/   warrant-swap-verified   W1  vstd, optional serde
  swap-core/       warrant-swap-core       W2  swap-verified, serde, serde_json,
                                                sha2, sha3, blake3, k256,
                                                curve25519-dalek, bs58,
                                                rand_core, zeroize
```

Rules:

- `swap-core` → `swap-verified` only. No RISC Zero, no Mnemonik, no network,
  no clock, no keys. Time enters as an input value.
- Neither crate depends on the invoice crates.
- `swap-core` builds for `wasm32-unknown-unknown`.
- Test-only cross-checks may use heavier crates as dev-dependencies (for example
  `bitcoin` as an oracle for Taproot and PSBT handling).

---

## 3. `swap-verified` (W1)

### 3.1 Types

```text
Id     = [u8; 32]                         sha256 of a CAIP string, or an identity hash
Pair   { give: Id, take: Id }

SwapRule =
    All(Vec<SwapRule>) | Any(Vec<SwapRule>)
  | ChainIn(Vec<Id>)                      both leg chains in the set
  | AssetIn(Vec<Id>)                      both leg assets in the set
  | CounterpartyIn(Vec<Id>)
  | CounterpartyNotListed(Id)             Id = hash of the list snapshot
  | NotionalAtMost(u64)                   whole units of the policy reference currency
  | PeriodNotionalAtMost(u64, u64)        (period in seconds, cap)
  | OpenSwapsAtMost(u64)
  | EvidenceAtLeast(u8)                   0 single RPC, 1 quorum, 2 light client, 3 own node
  | PairIn(Vec<Pair>)
  | PriceDeviationAtMost(u64)             basis points
  | TimeoutGapAtLeast(u64)                seconds
  | RevealWindowAtLeast(u64)              seconds
  | FinalityAtLeast(Id, u64)              (chain, depth)
  | AssetRiskWithin(u32)                  bit set of allowed risk flags
  | ContractPinned
  | CollateralAtLeast(u64)                basis points
```

`SwapFacts3` holds the facts that the evaluator reads. Selecting facts are
always known: the two chains and the two assets. Every other fact is an
`Option`; `None` means unknown.

| Field | Type | Unknown when |
|---|---|---|
| `give_chain`, `take_chain`, `give_asset`, `take_asset` | `Id` | never |
| `counterparty` | `Option<Id>` | no valid identity credential |
| `list_check` | `Option<ListCheck { list_hash, listed }>` | no signed snapshot |
| `notional` | `Option<u64>` | no valid price fact |
| `period_spent` | `Vec<PeriodSpent { period, spent: Option<u64> }>` | ledger lost (spec S25) |
| `open_swaps` | `Option<u64>` | ledger lost |
| `evidence` | `Option<u8>` | no chain fact has provenance |
| `price_deviation_bps` | `Option<u64>` | no valid oracle price |
| `timeout_gap` | `Option<u64>` | a clock input is unknown; negative gaps are 0 |
| `reveal_window` | `Option<u64>` | as above |
| `counterparty_lock` | `Option<LockObs { chain, depth: Option<u64>, finalized: Option<bool> }>` | `None` means the action does not depend on a counterparty lock |
| `asset_risk` | `Option<u32>` | the risk flags cannot be read |
| `contract_pinned` | `Option<bool>` | the lock is not observed |
| `collateral_bps` | `Option<u64>` | no collateral fact |

`SwapFacts` is the same record with every unknown filled in.
`completes(f3, facts)` says that `facts` is one way to fill in `f3`.

### 3.2 Meaning of the atoms

`satisfies(rule, facts)` is the declarative meaning on complete facts:

| Atom | True when |
|---|---|
| `ChainIn(s)` | `give_chain ∈ s` and `take_chain ∈ s` |
| `AssetIn(s)` | `give_asset ∈ s` and `take_asset ∈ s` |
| `CounterpartyIn(s)` | `counterparty ∈ s` |
| `CounterpartyNotListed(h)` | `list_check.list_hash = h` and not `list_check.listed` |
| `NotionalAtMost(c)` | `notional ≤ c` |
| `PeriodNotionalAtMost(p, c)` | some entry has period `p`, and every entry with period `p` has `spent + notional ≤ c` |
| `OpenSwapsAtMost(n)` | `open_swaps ≤ n` |
| `EvidenceAtLeast(m)` | `evidence ≥ m` |
| `PairIn(s)` | `(give_asset, take_asset)` is a pair in `s` |
| `PriceDeviationAtMost(b)` | `price_deviation_bps ≤ b` |
| `TimeoutGapAtLeast(t)` | `timeout_gap ≥ t` |
| `RevealWindowAtLeast(t)` | `reveal_window ≥ t` |
| `FinalityAtLeast(c, d)` | no counterparty lock, or its chain is not `c`, or it is finalized, or `depth ≥ d` |
| `AssetRiskWithin(a)` | `asset_risk & !a = 0` |
| `ContractPinned` | `contract_pinned` |
| `CollateralAtLeast(b)` | `collateral_bps ≥ b` |

Sums use mathematical integers in the specification and `u128` in executable
code, so no overflow exists.

`kleene(rule, f3)` is the strong Kleene meaning on partial facts. `evaluate3`
computes it. `decide` maps `Some(true)` to `Allow`, `Some(false)` to `Deny` and
`None` to `Ask`.

Version 0.3 (planned, spec 13.4): `PeriodNotionalAtMost` takes a reference
currency (G17). `CounterpartyIn` and `CounterpartyNotListed` use a Mnemonik
agent record resolved to `active` (G19). `AssetRiskWithin` has a known or
unknown state for each flag, and a present forbidden flag gives `false` (G18).

### 3.3 Theorems

| Name | Statement |
|---|---|
| `evaluate3` postcondition | `evaluate3(rule, f3) == kleene(rule, f3)` for every rule and facts |
| `kleene_sound` | `completes(f3, facts)` and `kleene = Some(true)` ⇒ `satisfies`; `Some(false)` ⇒ not `satisfies` |
| `decision_sound` | `Allow` ⇒ the rule holds for every completion; `Deny` ⇒ it fails for every completion |
| `decide` postcondition | `Allow` ⇔ `kleene = Some(true)`; `Deny` ⇔ `kleene = Some(false)` |

### 3.4 Timeout arithmetic

This section implements spec version 0.2. Version 0.3 replaces the fixed block
interval with an n-block bound at a stated failure probability and adds
`D_refund(B)` to S11 (G1, D5). `reveal_window` must also subtract `D_margin`
(D6). These changes are planned (spec 13.4).

```text
ClockBounds { min_block_secs, max_block_secs, max_lead_secs, max_lag_secs }
Timelock    = Height(u64) | Time(u64)        absolute; the first height or chain time
                                              at which the refund is valid
ChainNow    { tip_height, now_real }
```

`Leg::refund_valid_from` in `swap-core` converts a lock's timelock into this
form. On Bitcoin, `OP_CHECKLOCKTIMEVERIFY` with operand `h` needs
`nLockTime ≥ h`, and a transaction with `nLockTime = h` is final only in a
block above `h`, so the first valid height is `h + 1` (for a time: `t + 1`,
once the median time past exceeds `t`). The reference EVM and Solana HTLCs
refund once the block time is at least `t`, so their `t` is used unchanged.

Specification functions on integers:

```text
pending(Height h)       = h > tip_height
pending(Time t)         = t > now_real + max_lead_secs
earliest_real(Height h) = now_real + (h − tip_height − 1) · min_block_secs
latest_real(Height h)   = now_real + (h − tip_height) · max_block_secs
earliest_real(Time t)   = t − max_lead_secs
latest_real(Time t)     = t + max_lag_secs
```

`pending` means that the refund is certainly not valid yet. The bounds are
defined only for a pending timelock. A timelock that is not pending fails S11
and S12, and gives a gap or window of 0. Executable functions use `u128`
internally, so no intermediate value overflows.

| Function | Spec check | Result |
|---|---|---|
| `timeout_gap(T_A, now_A, bounds_A, T_B, now_B, bounds_B)` | Fact `timeout_gap` | `earliest_real(T_A) − latest_real(T_B)`, 0 if negative |
| `s11_holds(…, d_observe, d_confirm, d_margin)` | S11 | gap ≥ `d_observe + d_confirm + d_margin` |
| `s12_holds(T_B, now_B, bounds_B, d_confirm, d_margin)` | S12 | `now_real + d_confirm + d_margin ≤ earliest_real(T_B)` |
| `reveal_window(…)` | Fact `reveal_window` | `earliest_real(T_B) − now_real − d_confirm`, 0 if negative |

Theorems, over a model of the chain:

- **Height model.** For a pending height timelock, future block `k ≥ 1` has real time `b(k)` with
  `0 ≤ b(1) − now_real ≤ max_block_secs` and
  `min_block_secs ≤ b(k+1) − b(k) ≤ max_block_secs`. Then the block that makes
  the refund valid has a time in `[earliest_real, latest_real]`.
- **Time model.** The chain clock `c(r)` at real time `r` satisfies
  `r − max_lag_secs ≤ c(r) ≤ r + max_lead_secs`. Then `c(r) ≥ t` implies
  `r ≥ earliest_real(Time t)`, and `r ≥ latest_real(Time t)` implies `c(r) ≥ t`.
- **S11 soundness.** If `s11_holds` and both models hold, the real moment at
  which leg A becomes refundable is at least `d_observe + d_confirm + d_margin`
  after the real moment at which leg B becomes refundable.
- **S12 soundness.** If `s12_holds` and the model holds, leg B is not refundable
  before `now_real + d_confirm + d_margin`.

### 3.5 Verification

`swap-verified/verify.py` follows `verified/verify.py`: pinned Verus
`0.2026.09.20.aef82ed`, `--no-cheating`, a source hash, and mutation checks.
Each mutation changes executable code only and must produce a postcondition
failure. The mutations include "unknown conjunct ignored", "Ask treated as
Allow", each atom bypassed, each comparison reversed and each clock bound
swapped.

---

## 4. `swap-core` (W2)

### 4.1 Modules

| Module | Content |
|---|---|
| `caip` | Parse and validate CAIP-2, CAIP-10 and CAIP-19; chain family; `Id` mapping |
| `types` | `Leg`, `Lock`, `Timelock`, `Terms`, `Action`, `Role`, `RiskFlag` |
| `jcs` | RFC 8785 canonical JSON for the values that warrants use |
| `dsl` | JSON mini-DSL → `SwapRule`; `SwapPolicy`; `validate_policy` |
| `facts` | Observations with provenance; quorum; oracle; fact builder → `SwapFacts3` |
| `checks` | Obligatory checks S1 to S25 of spec version 0.2 with fixed reason codes. The Bitcoin decoder enforces S26. S27 is planned (G15). |
| `profile` | `ChainProfile` parameters; Bitcoin, EVM and Solana profiles |
| `tx` | Transaction decoders and intent matching (S24) |
| `warrant` | `SwapWarrant`, `DecisionRecord`, `TxBinding`, payload bytes, hash chain |
| `authorize` | The pipeline: checks → facts → evaluator → warrant or record |
| `secret` | Secret type for S4 (CSPRNG input, no `Debug`, no `Serialize`, zeroized) |
| `ledger` | Ledger state for ledger facts and the consumed sets (S10, S21, S22, S25) |
| `negotiation` | Planned (G5): message bodies, `intent_id`, `terms_hash`, transcript rules of spec 3.5 |

### 4.2 The JSON mini-DSL

```json
{
  "version": 3,
  "ref_ccy": "USD",
  "evaluator_id": "<64 hex>",
  "chains": { "<CAIP-2>": { "profile_hash": "<64 hex>", "contracts": ["…"] } },
  "rule": { "all": [ … atoms of spec 6.3 … ] }
}
```

Atoms take the spec 6.3 form: `{"pair_in": [[give, take], …]}`,
`{"notional_at_most": ["USD", 50000]}`, `{"period_notional_at_most": ["P1D",
200000]}` and so on. Periods accept `PT<n>H`, `P<n>D` and `P<n>W`.
Risk flags are names from spec 8.5.

`validate_policy` rejects:

- an unknown key, an unknown atom or a malformed CAIP identifier;
- an empty `all` or `any`;
- a currency that differs from `ref_ccy`;
- a chain in an atom that has no entry in `chains`, or whose profile misses an
  obligatory item (spec 8.8);
- the flags `confidential_amount` and `non_transferable` in `asset_risk_within`;
- any field that names an exit action (spec 3.3).

### 4.3 Facts and provenance

Every fact carries a `Provenance`:

```text
Provenance = Signed { authority, signature_ok } | Chain { method, block_hash,
             height, providers } | Derived { inputs } | Ledger { counter }
```

- A chain value that comes from a quorum is known only if every provider gives
  the same block hash and the same value (spec 5.3). Otherwise it is unknown.
- `evidence` is the weakest method over the chain facts that the action reads.
- A price fact is unknown when it is older than `max_age` or its confidence
  interval is wider than `max_conf_bps` (spec 5.4). When `decide` returns `Ask`
  and the rule reads an unknown notional or price deviation, the pipeline
  denies with `PRICE_UNKNOWN` (spec 5.4, decided after W2).
- `notional` rounds up to whole units of the reference currency.
- Ledger facts are unknown when the ledger counter is behind the last
  persisted counter (S25).
- A bare assertion from the agent never becomes a fact.

### 4.4 Obligatory checks

Each check is a function that returns `Ok(())` or a `Violation` with a fixed
reason code (`S1_HASH_ALG`, `S2_PREIMAGE_LEN`, …). The checks that the
signer runtime owns (watchers, fee raising, prepared refund) take the
runtime state as an input value and check it.

| Check | Input | Rule |
|---|---|---|
| S1 | both locks | `hash_alg = sha256` on both |
| S2 | both locks, profiles | `preimage_len = 32` and the profile template enforces it |
| S3 | both locks | same `H` |
| S4 | consumed hashlocks | `H` not used before |
| S5, S6 | terms, observed lock | receiver and refund account equal the terms |
| S7 | observed contract, policy pins | identity equals a pinned identity (profile derivation) |
| S8 | terms, observed lock, risk flags | amount, asset and decimals equal; net amount for `transfer_fee`; forbidden flags deny |
| S9 | asset fact | provenance is `Chain` |
| S10 | lock, consumed swap ids | `swap_id` bound where the profile supports it; not consumed |
| S11 | timelocks, profiles | `s11_holds` |
| S12 | `T_B`, profile | `s12_holds` (reveal only) |
| S13 | initiator lock, planned `T_B` | S14 and S11 for the planned `T_B` (responder lock only) |
| S14 | counterparty lock | depth or finalized status per profile and value band |
| S15 | fee reserves | reserve ≥ worst-case claim fee + refund fee on each chain |
| S16 | runtime state | watchers armed for the swap |
| S17 | profile, runtime state | prepared refund stored, or profile refund is permissionless |
| S18 | action | exit actions never reach the evaluator |
| S19 | profile | a fee-raising method exists |
| S20 | warrant | binds chain id, contract, swap id, nonce and validity window |
| S21 | consumed warrants | warrant hash not consumed |
| S22 | ledger | policy version ≥ last seen version |
| S23 | policy, build | `evaluator_id` equals the pinned build id |
| S24 | decoded transaction, intent | exact match (section 4.6) |
| S25 | ledger | counter monotonic; otherwise ledger facts unknown |

The rows describe the code, which follows spec version 0.2. Version 0.3
changes these rows (planned, spec 13.4): S4 becomes an operational duty of
`swap-signer`. Hashlock reuse moves to S10 and forbidden flags move to S9
(G24). S5 and S6 compare the Bitcoin claim and refund keys (D1, done in
`33f8cdf`). S8 checks
`payout_basis` (G5). S10 checks `lock_id` and consumed counterparty locks (G4,
G14). S15 uses earmarks (G16). S22 keeps the policy hash (D9). S23 allows
`"structural"` for exits and needs `owner_approval` for `human-review` (G7).
S24 allows fee-only variants (G10). S26 gets its own reason code, and S27 is
new (G24, G15).

### 4.5 Chain profiles

```text
ProfileParams {
  chain: CAIP-2, mainnet: bool, family: Bitcoin | Evm | Solana,
  clock: ClockBounds, finality: Confirmations(k by value band) | FinalizedTag,
  min_evidence: by value band, fee: { worst_lock, worst_claim, worst_refund, raise: method },
  refund: Prepared | Permissionless, swap_id_binding: bool,
  template_enforces_len32: bool, profile_hash
}
```

Family details:

- **Bitcoin.** Taproot HTLC (spec 8.2). Claim leaf
  `OP_SIZE 32 OP_EQUALVERIFY OP_SHA256 <H> OP_EQUALVERIFY <receiver> OP_CHECKSIG`.
  Refund leaf `<T> OP_CHECKLOCKTIMEVERIFY OP_DROP <refund> OP_CHECKSIG`.
  Internal key: the BIP 341 NUMS point. `swap-core` derives the output key and
  the `scriptPubKey` itself with `k256` (S7). Tests compare it with
  `rust-bitcoin`.
- **EVM.** Contract identity is the address plus the `EXTCODEHASH` fact; a
  proxy fact (EIP-1967 slot set) fails S7 unless the policy pins it.
- **Solana.** Contract identity is the program id plus the upgrade authority
  fact; the escrow address must be the expected PDA.

Version 0.3 (planned, spec 13.4): the claim leaf starts with
`<lock_id> OP_DROP`, and the keys are `claim_key` and `refund_key` (G4). The
refund input has `nSequence` `0xFFFFFFFD` (G3). EVM S7 covers beacon,
legacy-slot and diamond proxies (G20). Solana S7 checks the loader, the code
hash, the escrow discriminator and the escrow token account (G21, D3). The
profile clock follows G1, and `swap_id_binding` becomes `lock_id_binding`
(G4).

### 4.6 Transaction decoders (S24)

| Family | Input | Accepted shape |
|---|---|---|
| Bitcoin | PSBT version 0 | Inputs: own coins (witness UTXO script in the own set). Outputs: exactly one HTLC output with the derived `scriptPubKey` and the leg amount, plus at most one change output to an own script. Sighash type absent, `0x00` or `0x01`. Fee (input value minus output value) at most the profile's worst-case fee of the action. No signed transaction waits: a lock or a claim has an `nLockTime` of 0 or at most the observed tip and no relative lock (bit 31 of every `nSequence` set); a refund follows spec 8.2. An observed lock passes S7 only with its output script and outpoint. |
| EVM | Unsigned EIP-1559 transaction | `chain_id` equals the leg chain; empty access list. Lock: `to` = pinned HTLC; native: `value` = amount; token: `value` = 0. Approve: `to` = token, `approve(htlc, gross_debit)`. Claim and refund calls as in the reference ABI. |
| Solana | Legacy or version 0 message | Every instruction's program is allowed for the mode (spec 4.2 with the fixes). Compute budget: only unit limit and unit price. System: only `AdvanceNonceAccount`, first, pinned accounts, durable-nonce mode only. Ed25519: E2 mode only. Lookup-table addresses come from tables observed on the chain, by table address and index. The HTLC instruction has exactly the reference accounts, in order, with their signer and writable flags. |

Reference EVM HTLC ABI:

```text
lock(bytes32 swapId, address receiver, address refundTo, address token,
     uint256 amount, bytes32 hashlock, uint64 timelock)
claim(bytes32 swapId, bytes32 preimage)
refund(bytes32 swapId)
```

Reference Solana HTLC instruction data: one tag byte (`0` lock, `1` claim, `2`
refund) and then the fields in the order of the EVM ABI, little-endian
integers, 32-byte keys.

Reference Solana HTLC accounts. Lock: the sender (signer, writable) and the
escrow PDA (writable). A token lock then has the sender's and the escrow's
associated token accounts (writable), the mint and the token program. The
System Program is last. Claim and refund: the caller (signer, writable), the
escrow PDA (writable) and the payee (writable). The payee is the receiver for a
claim and `refund_to` for a refund. For a token, the payee's associated token
account takes the payee's place, followed by the escrow's token account, the
mint and the token program.

Transaction binding:

| Family | Binding |
|---|---|
| Bitcoin | unsigned txid (hex, display order), each BIP 341 sighash and its type |
| EVM | `keccak256(0x02 ‖ rlp(unsigned fields))` of each transaction, in order (`approve`, then lock) |
| Solana | `blake3(message bytes)` |

This is the reference interface of spec version 0.2. Version 0.3 (planned,
spec 13.4) keys each lock by `lockId` in the EVM calls, in the Solana
instruction data and in the PDA seeds (G4). It binds the prepared refund in
`warrant(lock)` (G11), allows a zero-allowance reset and a permit (G13),
follows the Solana instruction table of spec 4.2 (G22) and takes Bitcoin
prevouts from chain facts (G12).

### 4.7 The authorization pipeline

```text
authorize(request, context) →
  no verified ACCEPT of the proposed terms — entry: Deny record; exit: Halt
  entry action:  checks (S1–S15, S20–S25 as they apply) — fail → Deny record
                 facts → decide(rule, facts) — Allow → SwapWarrant
                                               Ask   → Ask record, or Deny
                                                       (PRICE_UNKNOWN) when
                                                       the rule reads an
                                                       unknown price value
                                               Deny  → Deny record
  exit action:   structural checks only — fail → Halt (stop and alert)
                 otherwise → SwapWarrant with reasons ["EXIT_ACTION"],
                 evaluator not called
```

The warrant payload is the JCS form of the `SwapWarrant` of spec 4.1, with the
encodings of section 1. `warrant_hash = blake3(payload)`. `prev_warrant` links
the records of one swap and one party.

This is the version 0.2 behavior of the code. Version 0.3 changes it (planned,
spec 13.4). A failed exit check rejects only that transaction and alerts the
owner. The signer then builds the exit from the recorded lock parameters (G9).
An exit warrant has `class: "exit"`, `evaluator_id: "structural"` and the
passed check codes in `reasons` (G7). A reveal after its first broadcast is an
exit action (G8). The warrant also gets `fee_ceiling`, `owner_approval`,
`replaces` and `onchain_digest` (G7).

### 4.8 Tests and acceptance

- One negative test per check: the request passes with the check and fails
  without it, with the expected reason code.
- One fixture per risk flag.
- Fault-injection tests 1, 2, 3, 5, 6, 7, 8 and the decision part of 10 of
  spec 13.3. Tests 4, 9 and the runtime part of 10 need the signer (W3).
- Golden tests for the JCS payload and the hashes.
- Cross-checks against `rust-bitcoin` for the Taproot output and PSBT parsing.
- `cargo build --target wasm32-unknown-unknown -p warrant-swap-core`.

## 5. Results (2026-10-05, commit `e9e9d31`)

Code: `policy-execution` commit `e9e9d31` on branch `ccr-7c731f40-t51t9k`,
crates `swap-verified` and `swap-core`. mnemonik-xyz/policy-execution#7 merged
the branch into `main` as commit `2e19118`. A rerun on 2026-10-07 gave the same test counts.
Verus and the mutation scripts were not run again.

Review fixes at commit `83e7e57` (2026-10-07): 85 `swap-core` tests passed (60
unit, 25 pipeline); `check_mutations.py` caught 18 of 18 disabled checks; the
`wasm32-unknown-unknown` build succeeds. `swap-verified` did not change.

D1, G3 and the price rule at commit `33f8cdf` (2026-10-07): 90 `swap-core`
tests passed (61 unit, 29 pipeline); `check_mutations.py` caught 18 of 18
disabled checks; the `wasm32-unknown-unknown` build succeeds.

| Item | Result |
|---|---|
| Verus `0.2026.09.20.aef82ed`, `--no-cheating` | 49 verified, 0 errors |
| Executable mutations of the evaluator and the arithmetic | 29 of 29 rejected |
| `swap-verified` native tests | 12 passed |
| `swap-core` unit tests | 56 passed |
| `swap-core` pipeline tests (both roles, every action, fault tests 1, 2, 3, 5, 6, 7, 8, 10, every risk flag) | 22 passed |
| Disabled obligatory checks caught by a test (`check_mutations.py`) | 18 of 18; S1 is also enforced by the type |
| Cross-checks | Taproot output, txid and BIP 341 sighashes against `rust-bitcoin`; PDAs against the Solana SDK |
| `wasm32-unknown-unknown` build of `swap-core` and `swap-verified` (with `vstd`) | Succeeds |
| Existing invoice crates (`warrant-policy`, `warrant-verified-policy`) | Unchanged; tests pass with `--locked` |

Found during implementation and fixed:

- `accept` must check S7 itself: a leg that names an unpinned contract is denied
  even when the policy has no `contract_pinned` atom.
- Fee amounts in profiles exceed 2^53 (wei), so they are decimal strings in JCS,
  like leg amounts.
- A Bitcoin CLTV height `h` was used as the first valid refund height; the
  refund is valid only from block `h + 1`. With a Bitcoin leg B, S11
  underestimated the latest refund of B by one block interval (Codex review on
  PR #7). `Leg::refund_valid_from` now adds the block; a regression test shows
  a gap that passed before and fails now.
- The ledger excludes the swap's own accepted notional when the same swap
  reaches `lock` or `reveal`; otherwise the period limit counts it twice.

Open for W3: the exact Bitcoin observation adapter, signing, persistence of the
ledger, watchers, and fault-injection tests 4 and 9.
