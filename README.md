# Warrant

Two independently versioned prototypes explore policy-controlled agent payments:

- [Policy execution](policy-execution/README.md): a fixed Rust policy evaluator,
  Verus correctness proofs, authenticated evidence and RISC Zero execution proofs.
- [Proof-backed payments](proof-execution/README.md): the earlier Circom/Groth16
  prototype with an ERC-20 payment vault and local EVM tests.

The directories are Git submodules pinned to specific commits. To fetch their
contents after cloning this repository, run `git submodule update --init --recursive`.
Each prototype documents its own setup, tests, diagrams and limitations.

## Design documents

- [Short proposal](short.md)
- [Technical design](tech-design.md)
- [Hackathon proposal](tameion-hackathon-proposal.md)

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
