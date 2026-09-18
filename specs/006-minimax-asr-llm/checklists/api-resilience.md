# API Integration & Resilience Quality Checklist: MiniMax 统一接管 ASR 与智能剪辑 (006-minimax-asr-llm)

**Purpose**: Validate the completeness, clarity, measurability, and consistency of requirements for MiniMax cloud integration and offline fallback.
**Created**: 2026-09-18
**Feature**: [spec.md](../spec.md) | [contracts/api.md](../contracts/api.md) | [plan.md](../plan.md)

## 1. API Integration Completeness & Traceability

- [x] CHK001 Are the exact HTTP request methods, headers, and multipart form parameter requirements documented for the MiniMax ASR endpoint? [Completeness, Spec §FR-001, Contracts §1.1]
- [x] CHK002 Is the response mapping requirement from MiniMax `segments` to the system's `words` array explicitly defined with field names and data types? [Clarity, Spec §FR-003, DataModel §1.2]
- [x] CHK003 Are the model name requirements (`asr-1.0` for STT and `MiniMax-Text-01` for Chat) consistently stated across spec, contracts, and plan? [Consistency, Spec §FR-001, §FR-004]
- [x] CHK004 Are requirements defined for whether glossary hotwords are passed into MiniMax ASR or solely enforced by the LLM correction tier? [Clarity, Spec §UserStory2]
- [x] CHK005 Are the requirements for the `/api/v1/settings/test-connection` endpoint explicit regarding which services are probed and what payload is returned? [Completeness, Contracts §2.3]

## 2. Timing & Acoustic Alignment Quality

- [x] CHK006 Is the latency requirement for ASR transcription quantified with specific, measurable thresholds for standard 60-second inputs? [Measurability, Spec §SC-001]
- [x] CHK007 Are character-level timestamp precision requirements defined with explicit units (e.g. milliseconds / seconds to 3 decimal places)? [Clarity, Spec §FR-002, §SC-003]
- [x] CHK008 Does the spec specify requirements for reconciling acoustic silence gaps between MiniMax word timestamps and punctuation pauses? [Completeness, Spec §UserStory1]
- [x] CHK009 Are requirements defined for preserving word-level timestamps during the downstream 6~12 character golden chunking phase? [Consistency, Spec §FR-003]
- [x] CHK010 Is the maximum allowable audio duration per single ASR request quantified with specific boundary limits? [Edge Case, Spec §EdgeCases]

## 3. Resilience & Fallback Clarity

- [x] CHK011 Are specific trigger conditions (timeout, HTTP 401, HTTP 429, HTTP 500, DNS failure) defined for falling back to local faster-whisper? [Completeness, Spec §EdgeCases, §FR-005]
- [x] CHK012 Is the timeout duration for the cloud ASR HTTP request quantified with a specific second threshold before fallback triggers? [Clarity, Plan §TechnicalContext]
- [x] CHK013 Does the specification define whether the fallback transition to local whisper must be transparent or surface an informational banner to the user? [Clarity, Gap, Spec §UserStory1]
- [x] CHK014 Are user notification requirements defined when fallback fails (e.g. both cloud and local ASR fail on corrupted audio)? [Edge Case, Gap]
- [x] CHK015 Is the anti-mock / anti-fake-data rule explicitly upheld in all exception paths without synthetic text fallbacks? [Consistency, Constitution §CorePrinciples]

## 4. Security & Credential Masking Coverage

- [x] CHK016 Are credential storage requirements explicit regarding storing API keys only in local `storage/settings.json`? [Completeness, Spec §FR-006]
- [x] CHK017 Is the prohibition of plaintext API keys in logs, HTTP responses, and frontend state objectively verifiable? [Measurability, Spec §FR-006]
- [x] CHK018 Are requirements defined for masking or displaying the configured status of the API key in the settings GUI? [Clarity, Spec §UserStory3]
- [x] CHK019 Does the specification define what happens when a user submits an empty or malformed API key string? [Edge Case, Gap]

## 5. Non-Functional & Boundary Specification

- [x] CHK020 Are audio preprocessing requirements (16kHz, mono, PCM s16le WAV extraction) specified before sending data to MiniMax? [Completeness, Spec §FR-002]
- [x] CHK021 Are requirements defined for handling audio files exceeding 500 seconds (e.g., segment splitting vs user error prompt)? [Edge Case, Spec §EdgeCases]
- [x] CHK022 Is the single-video total cost ceiling quantified with a measurable financial threshold? [Measurability, Spec §SC-002]
- [x] CHK023 Are memory and CPU usage ceiling requirements specified for local faster-whisper fallback operations? [Non-Functional, Spec §SC-001]
- [x] CHK024 Does the specification establish a clear requirement traceability link from user scenarios to functional acceptance criteria? [Traceability]

## Notes

- Total Items: 24 checklist unit tests
- Traceability: 100% of items linked to specification sections or explicit quality dimensions
- Status: Ready for review and execution