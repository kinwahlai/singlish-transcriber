## Working policy: implement → verify → fix, per milestone

See `SPEC.md` for the full spec and milestone plan, and `VERIFICATION.md` for the per-milestone
acceptance rubric.

Work through the milestones in `SPEC.md` in order (M1, M2, M3, M4, M5 — M0 is already complete).
For each milestone:

1. **Confirm the rubric exists.** Before writing any code for a milestone, check that
   `VERIFICATION.md` has a section for it. If it doesn't, stop and write that section first
   (with the user) — never implement against a milestone with no written rubric.
2. **Implement it fully** before moving on to the next one. Don't start the next milestone with
   this one half-working. Consider delegating pieces of the implementation to a subagent or the
   Workflow tool where it genuinely fits — independent pieces in parallel, an isolated worktree
   for a change that's likely to conflict with other in-flight work — but the milestone isn't
   done until it works end to end, not just in pieces.
3. **Run the cheap checks yourself**: `uv run ruff check .`, `uv sync`, `uv run pytest`. Fix
   anything these catch before going further — don't hand a broken build to the verifier.
4. **Invoke the `verifier` subagent**, telling it which milestone to check against
   `VERIFICATION.md`. This subagent has its own context and actually runs/exercises the project
   rather than reading the code and assuming it works.
5. **If the verifier reports any ✗:** fix the specific issue it described, then invoke it again
   for the same milestone. Repeat up to 3 times total.
6. **If still failing after 3 attempts:** stop. Do not report the milestone as done, and do not
   keep looping. Summarize what's failing and what you tried, and wait for guidance — this is a
   sign the milestone needs a design decision, not another fix attempt.
7. **Only once the verifier reports all ✓** for a milestone: report it as complete, and — for the
   milestones flagged as checkpoints below — **stop for human review even if the verifier passed
   everything**:
   - **M2 — Diarization + merged transcript** — foundational and highest-risk for silent quality
     problems: bad diarization boundaries or ASR-merge logic here poison every milestone after
     it, and transcript quality is inherently subjective in a way the verifier can't fully judge.
   - **M4 — Speaker-labeling web UI** — user-facing and interactive; UX quality isn't something
     an automated verifier can fully judge either.

## Ground rules

- Never mark a milestone done based on "the code looks right" — only the verifier's actual
  run-it-and-see report counts.
- The verifier subagent doesn't have `Edit`/`Write` access on purpose. Don't ask it to fix things;
  it reports, you fix.
- Keep `VERIFICATION_REPORT.md` and `verification-evidence/` in the repo as you go — don't delete
  them between milestones. They're the audit trail for a human reviewing this later without
  having watched every step.
- If a milestone's implementation reveals that a rubric item in `VERIFICATION.md` was wrong or
  missing (e.g. an edge case neither of us thought of), update `VERIFICATION.md` to add it, note
  why in the commit message, and continue — don't silently skip a rubric item that no longer
  seems to make sense.
- This project handles real client meeting recordings. Never push `samples/`, ingested
  recordings, or transcripts to a remote/shared git repo without an explicit, deliberate decision
  to do so — see SPEC.md §6.
