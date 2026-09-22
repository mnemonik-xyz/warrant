# Warrant — тексты для заявок на хакатон / hackathon submission texts

Черновик 2026-09-18. Основа — `bsdg-poc-design.md`. Оба блока ниже готовы к вставке в формы.

Сокращения / abbreviations: PoC — Proof of Concept; LLM — Large Language Model; DSL — Domain-Specific Language; ZK — Zero-Knowledge; zkVM — zero-knowledge virtual machine; ФФД / FFD — формат фискальных документов; ОФД — оператор фискальных данных; COSE — CBOR Object Signing and Encryption.

## Название / Name

**Warrant** (витрина / showcase: **Warrant Kids**). Ордер — подписанное, воспроизводимое основание, по которому кошелёк исполняет действие агента. Альтернативы: ProofGate, Vouch.

Слоган: *Warrant — policy-attested actions for AI agents* / *Каждое действие агента — с ордером.*

---

# RU

## Название проекта
Warrant — действия ИИ-агентов с ордером о соответствии политике (витрина: Warrant Kids)

## Короткое описание
Warrant — PoC верифицируемого действия ИИ-агента. Решение агента исполняется только вместе с ордером: подписанным, воспроизводимым доказательством того, что действие соответствует заранее утверждённой политике. LLM извлекает факты, но не принимает решение — его принимает формально верифицированный эвалюатор политики. Prompt injection или подмена провайдера модели не могут изменить результат. Витрина: смарт-кошелёк ребёнка с правилами трат, заданными родителем.

## Подробное описание

**Проблема.** Агенты на LLM начинают распоряжаться деньгами и правами, но «агент сделал всё правильно» остаётся вопросом доверия: инференс невоспроизводим, модель уязвима к инъекциям через входные данные, провайдер — единая точка зависимости. Подпись на выходе модели удостоверяет источник, а не правильность; ZK-доказательство над такой подписью лишь маскирует этот разрыв.

**Идея.** Разделить три роли и три вида доверия. Факты берутся из криптографически подписанных источников (фискальные данные чека) и из LLM-извлечения, которое обязано нести машинно-проверяемое обоснование. Политика — терм фиксированного DSL, полученный из намерения человека на естественном языке и явно им утверждённый; хеш терма фиксируется. Решение вычисляет верифицированный эвалюатор eval(политика, факты), доказанный один раз и воспроизводимый любым проверяющим. Каждое действие порождает ордер: хеш входных данных, принятые факты, хеш политики, идентификатор эвалюатора, решение, подпись. Это принцип proof-carrying code, применённый к агентам: недоверенный производитель прилагает свидетельство, дешёвый доверенный чекер его проверяет.

**Витрина: Warrant Kids.** Родитель пишет правила словами («только еда и канцелярия, без алкоголя и табака, не больше 1500 ₽ в день»); LLM предлагает терм DSL, родитель его проверяет и утверждает. На кассе ребёнок сканирует QR-код фискального чека. Факты уровня 0 детерминированы и берутся из тегов ФФД 1.2: 1212 «признак предмета расчёта» (значения 2/30/31 — подакцизный товар: алкоголь, табак), 1163 — код маркировки, 1030 — наименование, суммы; жёсткие запреты решаются здесь вообще без LLM. Факты уровня 1 — «мягкие» категории (торт «Птичье молоко» — еда, а не напиток): небольшая локальная модель возвращает метку плюс обоснование (совпавший фрагмент названия), детерминированный чекер его перепроверяет; метки без валидного обоснования отбрасываются в «неизвестно». Эвалюатор (Cedar — язык политик с формальной моделью на Lean 4, либо собственный мини-DSL на Lean) возвращает Разрешить / Запретить / Спросить родителя. Ордер подписывается (COSE_Sign1) и якорится через Mnemonik для provenance. Контракт кошелька платит мерчанту только при валидном ордере; экран аудита показывает, почему платёж разрешён или отклонён.

**Что доказывается, а что нет.** Доказывается, что решение следует из утверждённой политики и зафиксированных фактов через верифицированный эвалюатор, воспроизводимо. Не доказывается истинность «мягких» меток LLM сверх проверенного обоснования — этот остаток ограничен политикой (запрет/вопрос при «неизвестно»), а не доверием к модели. Демо-момент: чек с prompt injection, спрятанной в названии позиции, обманывает LLM, но тег 1212 = 2 всё равно даёт «Запретить», и ордер показывает почему.

**Для кого.** Семьи (контроль трат без слежки за корзиной; ZK-приватность на шаге 2), корпоративные и командировочные бюджеты (тот же движок политик, другие категории) и разработчики агентов: ядро Warrant переносимо на любое действие агента — намерение → политика → ордер → исполнение — и служит референсной реализацией escrow, который разблокируется по ордеру.

**Стек.** Cedar (Rust) / Lean 4 для DSL и эвалюатора; FastAPI или Node.js — сервис извлечения и сборки ордеров; локальная LLM с JSON-схемой (облачный API как запасной вариант); COSE_Sign1 + Mnemonik — подпись и provenance; Solidity-кошелёк в тестовой сети с ecrecover; Next.js — экраны родителя, кассы и аудита.

**Дорожная карта.** Шаг 1 (хакатон): всё выше на моке поставщика фискальных данных. Шаг 2: eval и чекер обоснований внутри zkVM (RISC Zero) — исполнение политики проверяется ончейн, чек остаётся приватным. Шаг 3: собственный DSL на Lean 4 с теоремой «Разрешить ⇒ нет запрещённых позиций». Шаг 4: живая выгрузка чеков и новые витрины (корпоративные траты, агентские закупки).

---

# EN

## Project name
Warrant — policy-attested actions for AI agents (showcase: Warrant Kids)

## Short description
Warrant is a proof of concept for verifiable AI-agent actions. An agent's decision executes only together with a warrant: a signed, reproducible proof that the action complies with a pre-approved policy. The LLM extracts facts but never decides; a formally verified policy evaluator does. Prompt injection or a swapped model provider cannot change the outcome. Showcase: a child's smart wallet with parent-defined spending rules.

## Detailed description

**Problem.** LLM-based agents are starting to control money and permissions, yet "the agent did the right thing" is still a matter of trust: inference is not reproducible, models are vulnerable to prompt injection through their inputs, and the provider is a single point of dependency. Signing a model's output proves the source, not correctness — and a ZK proof over such a signature only hides that gap.

**Idea.** Separate three roles and three kinds of trust. Facts come from cryptographically signed sources (in our showcase, fiscal receipt data) plus LLM extraction that must carry a machine-checkable justification. The policy is a term of a fixed domain-specific language (DSL), derived from the human's natural-language intent and explicitly approved by them; its hash is pinned. The decision is computed by a verified evaluator, eval(policy, facts), proven once and re-executable by anyone. Every action yields a warrant: hash of inputs, accepted facts, policy hash, evaluator id, decision, and a signature. This is proof-carrying code applied to agents: an untrusted producer attaches evidence, a cheap trusted checker verifies it.

**Showcase: Warrant Kids.** A parent writes rules in plain language ("food and stationery only, no alcohol or tobacco, max 1500 RUB per day"); an LLM proposes a DSL term, the parent reviews and approves it. At checkout the child scans the receipt's fiscal QR code. Tier 0 facts are deterministic: Russian fiscal format FFD 1.2 tags 1212 ("payment object attribute"; values 2/30/31 mark excisable goods such as alcohol and tobacco), 1163 (marking code), 1030 (item name), amounts — hard bans are decided here with no LLM at all. Tier 1 facts are soft categories (a "Bird's Milk" cake is food, not a drink): a small local model returns a label plus evidence (matched text span), and a deterministic checker re-verifies it; labels without valid evidence are dropped to "unknown". The evaluator (Cedar, a policy language with a Lean 4 formal model, or our own Lean mini-DSL) returns Allow / Deny / Ask-parent. The warrant is signed (COSE_Sign1) and anchored via Mnemonik for provenance. The wallet contract pays the merchant only with a valid warrant; an audit screen shows exactly why a payment was allowed or denied.

**What it proves / doesn't.** It proves the decision follows from the approved policy and pinned facts via a verified evaluator, reproducibly. It does not prove soft LLM labels beyond their checked evidence — that residual is bounded by the policy (deny/ask on unknown), not by trusting the model. Demo moment: a receipt with a prompt injection hidden in an item name fools the LLM, but tag 1212 = 2 still yields Deny, and the warrant shows why.

**Who it's for.** Families (controlled spending without surveillance of the basket; ZK privacy in step 2), corporate and travel budgets (same policy engine, different categories), and agent developers: the Warrant core is portable to any agent action — intent → policy → warrant → execution — and serves as a reference implementation for escrow that unlocks on a warrant.

**Stack.** Cedar (Rust) / Lean 4 for the DSL and evaluator; FastAPI or Node.js extraction and warrant service; local LLM with JSON schema (cloud API as fallback); COSE_Sign1 + Mnemonik for signing and provenance; Solidity wallet on a testnet with ecrecover; Next.js parent, checkout and audit screens.

**Roadmap.** Step 1 (hackathon): the above with a mock fiscal-data provider. Step 2: run eval + evidence checker inside a zkVM (RISC Zero) so policy execution is verified on-chain while the receipt stays private. Step 3: our own Lean 4 DSL with the theorem "Allow ⇒ no forbidden items". Step 4: live receipt retrieval and new showcases (corporate spend, agent procurement).

---

## Источники / Sources
- Cedar & Lean: https://lean-lang.org/use-cases/cedar/ ; https://github.com/cedar-policy/cedar-spec ; https://dl.acm.org/doi/10.1145/3649835
- Тег 1212 ФФД 1.2: https://help.atol.online/article/26852 ; тег 1163: https://teletype.in/@shtrih-support/1163
- Proof-Carrying Code (Necula, POPL 1997): https://dl.acm.org/doi/10.1145/263699.263712
- RISC Zero zkVM: https://github.com/risc0/risc0