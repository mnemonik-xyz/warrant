# Hardware requirements to run the Warrant flow

Status: 2026-10-12. Numbers marked **measured** come from the records in
[policy-execution](policy-execution/README.md) (its README, `validation-results.md`,
`solver-bounty/validation.md` and the GitHub Actions workflows). Numbers marked
**estimate** are sizing guidance, not recorded benchmarks. Re-measure before
committing to a procurement or a provider quote.

Abbreviations: zkVM — zero-knowledge virtual machine; CPU — central processing
unit; GPU — graphics processing unit; RAM — random-access memory; SSD — solid-state
drive; RPC — remote procedure call; LLM — large language model; CaaS — container
as a service.

## 1. Model / Workload Details

Warrant is not a model-serving workload. The flow has no trained model in its
trusted path. The heavy workload is **CPU-bound zero-knowledge proving** of a
small fixed program in the RISC Zero zkVM (`r0vm` 3.0.5), followed by a Groth16
wrap in a Docker container. Everything else (policy evaluation, signing,
contract settlement, agent messaging) is light.

| Workload | What runs | Shape of the load |
| --- | --- | --- |
| Policy evaluation and signing | Fixed Rust interpreter, Verus-proved evaluator, secp256k1 signature checks | Milliseconds; **measured** signed flow 0.04 s |
| Guest execution (no proof) | Same interpreter inside the zkVM executor | Seconds; **measured** 59,446 cycles (solver guest), about 2.1 M cycles (invoice guest) |
| Succinct proof | RISC Zero CPU prover, STARK, segment exponent 18 | Minutes, multi-core, memory-heavy; **measured** 135 to 148 s (solver guest, 1 segment), 446 s (invoice guest, 8 segments), four Rayon workers |
| Groth16 wrap | `risczero/risc0-groth16-prover:v2025-04-03.1`, x86_64 Docker image | **Measured** 80 s on an Apple Silicon host under x86 emulation; faster on native x86_64 |
| Reproducible guest build | `RISC0_USE_DOCKER=1` build in RISC Zero's pinned Docker image | Minutes, x86_64 Docker only |
| Contract settlement | Foundry (`forge`, `cast`, `anvil`), relayer transaction to Arc or a local Anvil chain | Light; network-bound |
| Formal verification (release time only) | Verus 0.2026.09.20 with Rust 1.98.1, 16 + 52 obligations, mutation runs | Minutes on one core; **estimate** a few GB of RAM |
| Optional transcription workload (solver-bounty showcase) | `faster-whisper-small` (about 244 M parameters), CTranslate2, FP16 on CUDA | GPU inference, one job at a time, one GPU, one replica, one hour |

Two points matter for sizing:

- **No LLM is hosted by Warrant.** The current release turns no natural-language
  intent into a policy ([tech-design](tech-design.md), release scope). Where a
  buyer or seller agent uses an LLM to extract facts, that LLM runs in the
  agent's own environment or behind an API, outside the trusted computing base.
  The showcase seller is a deterministic heuristic.
- **Proving does not use a GPU.** The host crate builds `risc0-zkvm` with the
  `client` and `disable-dev-mode` features only; the CUDA prover feature is not
  enabled. The only GPU in the flow is the optional transcription worker that a
  solver bounty pays for; it is the purchased workload, not part of Warrant.

## 2. Reference configuration that ran the complete flow

The complete flow (pinned toolchains, guest build, real succinct proof, Groth16
wrap in Docker, settlement through the real verifier on a private Anvil chain,
mutation and replay rejection) **passed on a GitHub-hosted `ubuntu-24.04`
runner** with `RAYON_NUM_THREADS=4`, `WARRANT_SEGMENT_PO2=18` and a 45-minute
job timeout ([run 37177967347](https://github.com/mnemonik-xyz/policy-execution/actions/runs/37177967347)).
GitHub documents that runner class as 4 vCPU x86_64, 16 GB RAM and 14 GB SSD.
That is therefore a demonstrated lower bound for a single prover, including
toolchain installation inside the time budget.

## 3. Requirements by role

The flow separates roles. A single machine can hold all of them for a demo;
production separates the signer from the agent and the prover.

### 3.1 Prover and signing host (the sizing driver)

| Resource | Minimum (demonstrated) | Recommended (estimate) | Why |
| --- | --- | --- | --- |
| Architecture | x86_64 Linux | x86_64 Linux (Ubuntu 22.04 or 24.04) | The Groth16 wrap image and the reproducible guest build are x86_64 Docker images; Apple Silicon works only through emulation |
| CPU | 4 vCPU | 8 to 16 physical cores, recent AVX2 server or desktop CPU | The STARK prover scales with Rayon workers; 4 workers is the documented setting, more cores shorten proving roughly linearly until memory bandwidth limits |
| RAM | 16 GB | 32 GB, 64 GB if several proofs or a proof plus a wrap run concurrently | Segment exponent 18 keeps peak memory bounded; the original unoptimized run swapped heavily. Peak memory has not been recorded, so leave headroom |
| Swap | Any | 16 GB on SSD as a safety net | Prevents an out-of-memory kill at a larger segment exponent |
| Disk | 14 GB SSD | 60 GB or more NVMe SSD | Rust toolchains (native 1.98.1 and RISC Zero 1.88.0), `r0vm`, the Groth16 prover image (several GB), Docker layers, Cargo `target/` for host and three guests, receipts and artifacts |
| GPU | None | None | Not used by this prover configuration |
| Network | Outbound HTTPS | Outbound HTTPS plus RPC to the target chain | First proof may download public prover assets; relayer submits transactions |
| Software | Docker daemon, Rust 1.98.1, `rzup` with Rust 1.88.0 and `r0vm` 3.0.5, Foundry 1.8.4, Python 3.12, Node/npm | Same | `scripts/prover-vm.sh` installs this set on a fresh Ubuntu machine |

Expected wall time per settled payment on the 4 vCPU reference: about 2.5 to
8 minutes of proving depending on the guest, plus the wrap and transaction
inclusion. Plan the escrow `settleBy` deadline with that margin.

Tuning knobs (they change cost, never policy semantics):

- `RAYON_NUM_THREADS`: number of prover workers; four is documented, raise to the
  physical core count when RAM allows.
- `WARRANT_SEGMENT_PO2`: 16 to 20, default 18. Lower values cut peak memory and
  add segments; higher values do the opposite.

### 3.2 Reproducible build and Groth16 wrap machine

Same as 3.1, and it **must** be x86_64 with a running Docker daemon. A locally
built guest has a different image ID on each machine; only the Docker build
produces the ID that is deployed and that a prover must match. On Apple Silicon
the demo selects `linux/amd64` and runs under emulation (slow, but it worked for
the wrap in the recorded sample).

### 3.3 Verifier, relayer, owner tools and agent

| Role | Requirement (estimate) |
| --- | --- |
| Receipt verifier (`warrant-host verify`) | Any 2 vCPU, 4 GB RAM Linux or macOS host; sub-second |
| Relayer | 1 to 2 vCPU, 2 GB RAM, stable RPC connectivity to Arc (chain 5042, or testnet 5042002) or the target EVM chain; holds only gas |
| Owner tools (`warrant-policy instantiate`, `hash`, issuer signing with `warrant-evidence`) | Laptop class; the issuer key should live on a separate machine or hardware wallet |
| Agent (buyer or seller) | Laptop or small VM; Python 3.12 for the showcase scripts and the io.net MCP client; any LLM it uses is the agent operator's own cost |
| Ledger connector | Python 3, beancount; trivial |

### 3.4 Formal verification host (release time)

Verus release 0.2026.09.20 with Rust 1.98.1, run through `verified/verify.py`
with mutations. One core is enough; allow a few GB of RAM for the SMT solver
and a few minutes per run (estimate). This is a release gate, not a runtime
dependency.

### 3.5 Optional GPU transcription worker (solver-bounty showcase)

This is the workload a solver bounty buys on io.net; it is not needed to run
Warrant itself.

| Item | Value |
| --- | --- |
| Model | `Systran/faster-whisper-small`, pinned revision, downloaded at image build time; about 244 M parameters |
| Runtime | CTranslate2 4.8.2, faster-whisper 1.2.1, CUDA 12.3 base image, cuBLAS 12.3 and cuDNN 9 only |
| Precision | FP16 on CUDA (`WARRANT_COMPUTE_TYPE`), default on CPU |
| GPU | One NVIDIA GPU with a CUDA 12.3-compatible driver; **estimate** under 2 GB of GPU memory, so any current data-centre or consumer GPU class is sufficient. The docs reference io.net classes RTX 4090, L40 and L40S |
| Container | 1 GPU, 1 replica, 1 hour duration billing, HTTP port 8080, image about 1.9 GB compressed; **estimate** 4 GB RAM and 10 GB disk for the container |
| Concurrency | One job at a time; uploads up to 64 MiB |
| CPU fallback | `:pilot-arm64` image with `WARRANT_DEVICE=cpu` for local runs on Apple Silicon; slower, no CUDA |
| Cost guard | Pilot spend cap `--max-cost-usd 1.00`; the first io.net run is also the first GPU test of the image |

### 3.6 Chain and storage

Settlement needs an EVM chain with the pinned RISC Zero Groth16 verifier
(Arc mainnet 5042 or testnet 5042002 via their public RPC, or a local Anvil for
rehearsal). The relayer only needs RPC access and gas. Warrants, receipts and
negotiation records are small files (succinct receipt about 224 KB, Groth16 seal
about 1.5 KB); any object store or decentralized file storage node works for
the archive.

## 4. Suggested procurement tiers

| Tier | Use | Specification (estimate, built on the demonstrated 4 vCPU / 16 GB floor) |
| --- | --- | --- |
| Developer | Build, test, native demo, occasional proof | Laptop or VM, 4+ cores, 16 GB RAM, 50 GB SSD; x86_64 with Docker for image-ID-exact builds, otherwise Apple Silicon with emulation |
| Pilot prover | One settlement at a time, mainnet canary | Dedicated x86_64 VM or bare metal, 8 cores, 32 GB RAM, 100 GB NVMe, Docker, no GPU |
| Production prover | Several concurrent settlements, deadline margin | x86_64 bare metal, 16 to 32 cores, 64 to 128 GB RAM, 500 GB NVMe, Docker; scale horizontally by adding provers, since each proof is independent |
| GPU workload node | Only when the bounty pays for transcription | Rented per hour on io.net or similar: 1 NVIDIA GPU, 4 vCPU, 16 GB RAM |

Capacity rule from the delivery plan: fix the pilot concurrency limit from
measured prover throughput, with explicit queue and expiry behaviour, rather
than from these estimates.

## 5. What is not required

- No GPU for proving, verification, signing or settlement.
- No hosted LLM; the trusted path contains no model.
- No persistent high-memory service: proving is batch work that can run on
  demand or on a queue.
- No administrative chain role: proof generation and submission need none.
