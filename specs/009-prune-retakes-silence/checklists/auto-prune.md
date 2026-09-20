# Auto-Prune & Speech Cadence Checklist: 智能粗剪与口播气口质量

**Purpose**: Validate specification completeness, clarity, and consistency for the smart pruning of silence, retakes, and natural breath gap preservation
**Created**: 2026-09-20
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)

## Requirement Completeness (需求完整性)

- [x] CHK001 - Are the exact start/end boundary calculation formulas for head and tail idle periods explicitly defined? [Completeness, Spec §FR-001, §FR-002, §FR-003]
- [x] CHK002 - Are the minimum pause threshold and text similarity threshold for retake detection explicitly specified with default values? [Completeness, Spec §FR-005, Plan §PruneStrategyConfig]
- [x] CHK003 - Are handling requirements specified for consecutive multi-retake chains where the speaker restarts multiple times? [Completeness, Spec §FR-007]
- [x] CHK004 - Are requirements defined for mid-speech silence compression that preserves human breathing room? [Completeness, Spec §FR-012]
- [x] CHK005 - Are non-destructive persistence requirements defined for storing prune spans in the authoritative SQLite database? [Completeness, Spec §FR-013, Data-Model §2]
- [x] CHK006 - Are requirements specified for updating effective project duration and subtitle timeline indices after pruning? [Completeness, Gap]

## Requirement Clarity & Measurability (清晰度与可量化性)

- [x] CHK007 - Is the "natural breath pause" quantified with concrete timing thresholds rather than subjective descriptors? [Clarity, Spec §FR-004, Plan §Summary]
- [x] CHK008 - Is the "leave latter, discard earlier" retake rule quantified with exact cut boundary padding to prevent clipped audio? [Clarity, Spec §FR-006, Research §决策2]
- [x] CHK009 - Are the distinguishing criteria between rhetorical emphasis (e.g., repeating for emphasis) and accidental retakes quantified? [Clarity, Spec §FR-008]
- [x] CHK010 - Is the client-side virtual skip behavior in the video player quantified with frame-accurate seeking parameters? [Clarity, Contract §3]
- [x] CHK011 - Are audio anti-click fade durations (e.g., afade window) quantified with exact millisecond values? [Clarity, Plan §Technical Context]

## Requirement Consistency (需求一致性)

- [x] CHK012 - Do the safety padding durations in `spec.md` (0.2s~0.25s) strictly align with those in `plan.md` and `data-model.md`? [Consistency, Spec §FR-004 vs Plan §PruneStrategyConfig]
- [x] CHK013 - Are subtitle status definitions (`is_pruned`, `prune_reason`) consistent across API contracts, frontend interfaces, and database schema? [Consistency, Data-Model §1.2 vs Contract §1]
- [x] CHK014 - Do FFmpeg audio cut intervals strictly match video cut intervals to guarantee multi-track A/V sync? [Consistency, Plan §Phase 4]
- [x] CHK015 - Does the B-roll overlay placement rule ensure b-rolls are never scheduled across pruned/skipped intervals? [Consistency, Gap, Plan §Project Structure]

## Scenario & Edge Case Coverage (场景与边界覆盖)

- [x] CHK016 - Does the spec define the system behavior when an input video has zero valid speech or extremely noisy audio? [Edge Cases, Spec §Edge Cases]
- [x] CHK017 - Are requirements specified for handling non-speech microphone friction, rustle, or heavy breathing during head/tail prep? [Edge Cases, Spec §Edge Cases]
- [x] CHK018 - Does the spec define what happens when a user manually drags a prune boundary beyond adjacent subtitle timestamps? [Edge Case, Gap]
- [x] CHK019 - Are recovery and fallback requirements specified if FFmpeg multi-cut complex filter generation encounters an error? [Edge Case, Plan §Constitution Check]
- [x] CHK020 - Does the spec define behavior when an entire subtitle sentence is shorter than the minimum safety padding? [Edge Case, Gap]

## Non-Functional & Performance Requirements (非功能性要求)

- [x] CHK021 - Is the performance target for full-video prune analysis quantified for typical 3-5 minute clips? [Clarity, Plan §Technical Context]
- [x] CHK022 - Are offline capability requirements established ensuring prune algorithms execute with zero external API calls? [Completeness, Plan §Constraints]
- [x] CHK023 - Are audio continuity standards specified ensuring no audible pop, click, or DC offset at splice points? [Acceptance Criteria, SC-005]
