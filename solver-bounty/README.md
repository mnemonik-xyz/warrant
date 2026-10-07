# Solver bounty

Status: implementation prototype. The bundled workload and all demo funds are synthetic.

An agent buys a schedule that meets fixed constraints and a cost ceiling.
The buyer reserves the fee before the seller accepts the task.
A deterministic checker decides whether the result qualifies.
The seller can settle after the buyer goes offline.

## What the proof establishes

- The schedule uses the workload that the buyer committed.
- Every job appears exactly once.
- Jobs meet release times, deadlines, dependencies, and machine capacity.
- The checker computes the cost and checks the buyer's ceiling.
- The authorization binds the accepted seller, fee, task, policy, and payment scope.

The proof does not establish global optimality or future machine performance.
The parties agree to the workload's durations and prices.

## What settlement establishes

The escrow requires a proof for its fixed solver program and the exact result bytes.
It pays the accepted seller and publishes the complete schedule.
The buyer cannot cancel an accepted task before the deadline.
An unfinished task permits a refund after the deadline.

The result is public and nonexclusive.
Calldata can expose it before finality, even if settlement fails.
Payment requires timely transaction inclusion.

## Run

From the Warrant repository:

```sh
git submodule update --init --recursive
cd policy-execution
python3 scripts/solver-demo.py --native-only
```

The native mode creates no proof.
For contract integration, install Foundry and run:

```sh
npm ci --prefix contracts --ignore-scripts
python3 scripts/solver-demo.py --mock-settlement
```

The mock mode records `realProof: false`.
For real proof settlement, follow the [toolchain setup](../policy-execution/solver-bounty/README.md), then run:

```sh
python3 scripts/solver-demo.py
```

The default run needs Docker for Groth16.
It uses a private local Anvil, test accounts, and test tokens.
The reference seller is a deterministic tool that an AI agent can call.

## Evidence and scope

See the [implementation specification](../policy-execution/solver-bounty/README.md)
and [observed validation results](../policy-execution/solver-bounty/validation.md).

The existing Verus proof covers the shared rule evaluator.
It does not cover the new checker, contracts, serialization, or cryptographic implementation.
