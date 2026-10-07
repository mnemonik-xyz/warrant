# Warrant

One prototype explores policy-controlled agent payments:

- [Policy execution](policy-execution/README.md): a fixed Rust policy evaluator,
  Verus correctness proofs, authenticated evidence and RISC Zero execution proofs.

The directory is a Git submodule pinned to a specific commit. To fetch its
contents after cloning this repository, run `git submodule update --init --recursive`.
The prototype documents its own setup, tests, diagrams and limitations.

## Design documents

- [Whitepaper](whitepaper.md) (the full argument and the protocol, in
  ASD-STE100 Simplified Technical English)
- [Short proposal](short.md)
- [Technical design](tech-design.md)
- [Hackathon proposal](tameion-hackathon-proposal.md)
- [The case, with flow diagrams](case.md)
- [Flow, trust assumptions and attack surface](design-review.md)
- [Descriptions and pitch scripts](pitch.md)
- [Showcase deck, PDF](showcase/warrant-showcase.pdf) (10 slides, 1280×720; last slide carries a QR code to this repository)
- [Real invoices: specification and collection guide](real-invoices/spec.md) ([по-русски](real-invoices/spec.ru.md))
- [Use case: automated hardware purchase between agents](hardware-purchase/spec.md)
- [Solver bounty: proof-based acceptance and result delivery](solver-bounty/README.md)
- [Warrant for swaps: policy-attested cross-chain settlement](swap/spec.md) (chain-agnostic HTLC swap authorization, safety checks and chain primitives; [implementation specification](swap/implementation.md), [tasks](swap/tasks.md))

## Restoration on 2026-09-22

Missing implementation files were reconstructed from recorded source contents and
patches. The policy evaluator and both Cargo lockfiles match the SHA-256 hashes
recorded before the loss. The rebuilt guest verifies the existing receipts.

Validation after restoration: 24 policy tests, 24 payment-prototype tests, Verus
verification (7 verified, 0 errors), and rejection of all eight deliberate
evaluator mutations. These results do not extend the formal proof beyond the
[documented evaluator scope](policy-execution/verified/README.md).

These are new commits in the repositories initialized after the loss; the deleted
original Git history has not been recovered. Surviving build artifacts and proof
receipts remain local and ignored. Investigation of the deletion is still open.
