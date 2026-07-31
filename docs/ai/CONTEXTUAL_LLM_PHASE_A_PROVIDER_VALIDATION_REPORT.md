# Phase A Contextual LLM Provider Validation Report

Date: 2026-07-25  
Updated: 2026-07-26  
Status: provider request shape and diagnostics validated; successful completion
is currently blocked by provider quota/billing

## Executive result

Orbit now has an official OpenAI Python SDK provider implementation for Phase A
shadow interpretation. It uses the Responses API structured-output parser with
the production `ContextualInterpretation` Pydantic model, `store=False`, no
tools, and no tool choice. The deterministic orchestrator remains the only
production authority.

The backend now has an enabled OpenAI shadow configuration, configured
credential, and configured `gpt-5.6-luna` model. The first live calls reached
OpenAI but were collapsed to `provider_transport`. A safe synthetic diagnostic
identified the exact response as HTTP 400 `invalid_request_error` because this
model rejects the optional `temperature` parameter. The official adapter now
omits that parameter.

A subsequent one-call synthetic check passed networking, TLS, authentication,
model lookup, and request-shape handling, then returned HTTP 429 with
`insufficient_quota`. It is safely reported as non-retryable `provider_quota`.
No successful structured output or genuine dataset metric is claimed.

Phase B promotion criteria are not met.

## Provider and model configuration

Implemented provider: `openai`  
SDK: official `openai` Python package, constrained to major version 2  
API: Responses API structured parsing  
Selected validation model: `gpt-5.6-luna`, pending credential and organizational
approval  
Provider-side response storage: disabled  
Executable tools supplied to provider: none

The Luna model is selected as the initial evaluation candidate because the
current OpenAI model guide describes it as the cost-sensitive, high-volume
member of the GPT-5.6 family and lists structured-output support. This is a
validation choice, not a production promotion.

Official references:

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5.6-luna
- https://developers.openai.com/api/docs/guides/latest-model

Required gitignored `backend/.env` values:

```dotenv
CONTEXTUAL_LLM_ENABLED=true
CONTEXTUAL_LLM_SHADOW_MODE=true
CONTEXTUAL_LLM_PROVIDER=openai
CONTEXTUAL_LLM_MODEL=gpt-5.6-luna
CONTEXTUAL_LLM_API_KEY=<server-side key required>
CONTEXTUAL_LLM_BASE_URL=https://api.openai.com/v1
CONTEXTUAL_LLM_TIMEOUT_SECONDS=4
CONTEXTUAL_LLM_RETRY_COUNT=1
CONTEXTUAL_LLM_MAX_INPUT_TOKENS=6000
CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS=700
CONTEXTUAL_LLM_TEMPERATURE=0
CONTEXTUAL_LLM_PROMPT_VERSION=contextual_leave_interpreter_v2
```

No key has been written or hardcoded by this implementation.

## Startup validation and health

Startup fails clearly when Phase A is enabled and any of the following is
invalid:

- shadow mode is false;
- provider is disabled or unsupported;
- model or credential is empty;
- provider base URL is not HTTPS;
- timeout or retry policy is outside its bounded range;
- the input budget is too small;
- the selected prompt template is missing.

`GET /api/v1/ai/shadow-provider-status` is restricted to authenticated admin or
super-admin principals. It reports only safe configuration booleans, provider
and model labels, prompt version/example count, and administrator-aggregated
recent outcome metadata. It never returns or probes the credential.

## Prompt-template version

Template: `contextual_leave_interpreter_v2`  
Examples: 8  
Estimated examples: 1,575 tokens  
Estimated complete system prompt: 2,045 tokens  
Configured input budget: 6,000 tokens  
Reserved for actual context/message: at least 3,000 estimated tokens

Examples are stored once in:

`backend/app/ai/prompt_templates/contextual_leave_interpreter_v2.json`

They cover:

1. starting leave intake;
2. active intake with date, leave type, and reason in one message;
3. date correction;
4. leave-type correction while preserving dates;
5. informal sick leave tomorrow;
6. ambiguous next-week scope;
7. topic switch to balance;
8. unsafe another-employee/SQL request.

All expected outputs validate against the same closed production schema.
Examples contain no employee identity, balance, draft, private record, secret,
or chain-of-thought. Example user text is explicitly delimited as untrusted.

## Evaluation dataset

Dataset: `backend/tests/evals/contextual_leave_phase_a.json`  
Cases: 38

The dataset was expanded with contradictory leave types/durations, additional
multi-field shorthand, misspellings, reference preservation/ambiguity, informal
balance language, topic switching, role/API injection, and contradictory
cancel/submit instructions.

Multi-label segment coverage:

| Segment | Cases |
|---|---:|
| Standalone requests | 3 |
| Active workflow follow-ups | 16 |
| Topic switches | 3 |
| References | 7 |
| Informal language | 8 |
| Adversarial/security | 7 |

## Evaluation runner

`backend/scripts/evaluate_contextual_shadow.py` runs the entire checked-in
dataset in zero-shot, few-shot, or both modes. It:

- validates enabled/provider configuration first;
- enforces the input budget before every call;
- uses the strict provider contract;
- records only case IDs, structured categories, disagreement categories,
  latency, and token counts;
- produces overall and segmented metrics;
- highlights the known multi-field failure case;
- does not query employee data or mutate any database row.

Command:

```powershell
venv\Scripts\python.exe scripts\evaluate_contextual_shadow.py `
  --prompt-mode both `
  --output contextual-shadow-provider-results.json
```

The result filename is gitignored.

## Segmented live metrics

Live provider metrics are pending because the configured OpenAI project
currently returns `insufficient_quota`. Configuration, credential presence,
model selection, and provider activation are no longer the missing pieces.

| Metric | Zero-shot | Few-shot |
|---|---:|---:|
| Schema-validity rate | Not measured | Not measured |
| Unsafe-proposal rate | Not measured | Not measured |
| Routing disagreement rate | Not measured | Not measured |
| Extraction disagreement rate | Not measured | Not measured |
| Latency p50 / p95 | Not measured | Not measured |
| Input/output token usage | Not measured | Not measured |

No placeholder or mocked percentage is presented as real-provider evidence.

## Known failure case

Message:

> For next Monday and mention the reason as holiday and the leave type is
> casual leave.

Expected structured observation:

- domain: leave;
- goal: prepare leave request;
- workflow action: continue;
- date expression: next Monday for start and end;
- leave type: Casual Leave;
- reason category present;
- no ambiguity;
- semantic capability: continue leave intake.

The versioned prompt contains this exact workflow-continuation pattern, and
mocked provider tests confirm that the strict contract accepts all fields
without creating leave/intake/draft rows. Live routing and extraction
disagreement results remain pending the provider credential.

## Zero-shot versus few-shot

The runner supports a same-model, same-dataset `both` mode so zero-shot and
few-shot results are directly comparable. The comparison has not been run
against a real provider because the current project quota blocks successful
completions. The full 38-case `both` run also requires explicit pacing for the
account's 10 RPM limit.

Recommended evaluation decision rule:

- review every security/adversarial error separately;
- require zero cross-employee or executable-capability proposals;
- evaluate active workflow continuation and references independently;
- do not promote based on aggregate accuracy;
- retain the leaner prompt if few-shot gains are not material.

## Security validation

- Identity remains exclusively `AuthenticatedPrincipal`.
- No provider input includes bearer tokens or API keys.
- Context is owner-scoped and PII-redacted.
- Provider request includes no tools.
- Provider output must validate against a closed Pydantic schema.
- Input and output token budgets, timeouts, and retries are bounded.
- Provider errors remain invisible to employees.
- Raw prompts and provider responses are not persisted.
- Only safe shadow evaluation metadata is stored.
- Phase A cannot change deterministic routing or responses.

## Disagreement and adjustment process

Once live results exist, prioritize:

1. unsafe proposals;
2. invalid structured output;
3. workflow continuation versus new-goal disagreements;
4. references and topic switches;
5. multi-field extraction differences;
6. informal/misspelled cases.

Adjust the versioned template first. Expand the schema only for a measured,
domain-valid field that cannot be represented safely. Never add identity,
permission, approver, SQL/API, authoritative balance/status, or executable tool
fields.

## Tests completed before live evaluation

- strict few-shot template parsing;
- required continuation/correction/security examples present;
- token-budget reserve;
- startup configuration fails closed;
- official SDK structured parsing with a mocked SDK transport;
- no provider tool/tool-choice supplied;
- credential excluded from model input;
- admin-only status endpoint;
- credential absent from status response;
- deterministic response unchanged;
- no leave/intake/draft/conversation writes;
- timeout and invalid-output isolation.

Final verification on 2026-07-25:

- backend: `176 passed`;
- frontend: `25 passed`;
- production frontend build: passed;
- Python compile check: passed;
- installed Python dependency check: passed;
- diff whitespace validation: passed.

The evaluation command itself was also exercised without a credential. It
failed closed before any provider call and named the missing provider, model,
API key, and enabled flag.

## Rollback

Immediate:

```dotenv
CONTEXTUAL_LLM_ENABLED=false
```

Then restart the backend. The deterministic orchestrator continues unchanged.
For code rollback, remove the official adapter, prompt template/loader,
evaluation runner, health endpoint, and related configuration validation.
Existing conversation and leave data are independent of this integration.

## Phase B decision

**Not approved.** Phase B must remain disabled because:

- no real-provider dataset metrics exist yet;
- zero-shot versus few-shot performance is not measured;
- live latency and token cost are unknown;
- the known failure case has not been observed from the real model.

Restoring quota/billing, verifying one successful synthetic structured
response, and then running a safely paced evaluation are prerequisites, not
authorization to implement Phase B.

## 2026-07-26 diagnostics remediation

The official provider now maps SDK exceptions and HTTP status into bounded,
safe categories:

- `provider_timeout`
- `provider_connection`
- `provider_dns`
- `provider_tls`
- `provider_authentication`
- `provider_permission`
- `provider_model_not_found`
- `provider_rate_limit`
- `provider_quota`
- `provider_bad_request`
- `provider_structured_output`
- `provider_server_error`
- `provider_invalid_response`
- `provider_unknown`

Persisted diagnostics contain only a safe category/message/code, HTTP status,
provider request ID, retryability, and latency. They do not contain credentials,
headers, prompts, raw requests, raw provider responses, employee text, or stack
traces. Normal employees do not receive provider failures.

The one-call synthetic command is:

```powershell
cd C:\Users\venum\Documents\Reknew_EMS\reknew-orbit\backend
venv\Scripts\python.exe scripts\test_contextual_provider.py
```

It uses fixed synthetic text, the production structured schema, no employee
data, no tools, no database writes, and `retry_count=0`.

Observed result after correcting the request shape:

```text
success=false
safe_error_category=provider_quota
error_code=insufficient_quota
http_status=429
retryable=false
model=gpt-5.6-luna
latency_ms=2480
schema_valid=false
request_id=<safe provider request identifier returned>
can_affect_production=false
```

The exact request ID is intentionally not copied into long-lived
documentation.

Current official references used for this remediation:

- [OpenAI API error codes](https://developers.openai.com/api/docs/guides/error-codes)
- [OpenAI Python SDK error handling and request IDs](https://github.com/openai/openai-python)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
