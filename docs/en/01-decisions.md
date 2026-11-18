[中文版](../zh-CN/01-decisions.md)

# Architecture Decision Register

Status: approved in conversation; not implemented or committed to GitHub.

| ID | Choice | Decision |
|---|---|---|
| Q1 | A | Skill Bundle; no independent runtime/UI |
| Q2 | A | Fully independent of Awesome QA Skills |
| Q3 | B | Hybrid: guided/assisted/bounded autonomous |
| Q4 | B | API-first + Browser Basic |
| Q5 | B | Central pattern catalog + references |
| Q6 | B | Rule filter + agent semantic rerank |
| Q7 | B | Evidence levels and validation gates |
| Q8 | B | Structured Finding + Markdown + Evidence Bundle |
| Q9 | A | Regression recommendations only; no test code edits |
| Q10 | B | Executable evidence-driven benchmark |
| Q11 | B | Risk-based quality lifecycle and release gates |
| Q12 | B | Portable core; Codex first, Claude Code verified |
| Q13 | B | Versioned session, journal and safe resume |
| Q14 | A | Complete MVP in one release; vertical slice is an internal integration checkpoint, not scope reduction |

ADR-014: single-scope complete MVP. Do not reinterpret the vertical slice as a phased MVP release. Missing independent host enforcement prevents bounded autonomy, rather than lowering safety requirements.


## Q16 — Release Authorization

**B: Two-person release authorization** (RI initiates; a different authenticated IRR verifies and approves exact source commit, manifest digest, artifact provenance and acceptance evidence before protected publication). Q14=A full MVP scope remains unchanged. See ADR-016.

## Q17 — Implementation location

**A — GitHub-first**, subject to repository availability. The full v0.1 MVP remains a single release; locally prepared engineering assets are not GitHub commits or validated features.
