# Design Choices — 2026-05-13 Swarm Pass — **ALL RESOLVED**

> Status as of 2026-05-13 evening: all 12 design choices from the 2026-05-13 god-tier swarm pass have been resolved by Calhoun-side steward (John). Partnership-level confirmation from Mitch (Binary steward) is required for items that affect both stacks; the Mitch/Ishaan brief (`~/bsv/mpc/MITCH-ISHAAN-BRIEF-2026-05-13.md`) lists which.
>
> Format: each item shows the position taken, the rationale (security / UI-UX / cggmp24 fidelity / maintainability), and any spec edits that follow.

---

## 1. Sign-time confirmation rendering (§15.5a / ADR-0031) — **HYBRID**

**Position:** Wallet exposes `confirmationView(intent) → ConfirmationSurface` API that integrators MAY call to obtain a structured rendering. If integrators do NOT call, the wallet renders default UI itself. Either path produces the same field set per §15.5a.

**Rationale:** Integrator-only allows malicious omission of fields; wallet-only forces wallets to own UX even when integrators have better context; hybrid lets the wallet enforce minimum surface while preserving integrator flexibility. Ledger trusted-display + Fireblocks TAP precedent.

**Follow-on edits:**
- §15.5a expanded with the `confirmationView()` API contract + default-render fallback semantics.
- ADR-0031 §3 updated.

---

## 2. Approval channel pluralism (§09.5.1 / ADR-0032 / Q16) — **MessageBox canonical + opt-in push (wakeup-only)**

**Position:** Approval-request payloads MUST travel via the canonical §06 MessageEnvelope (BRC-78/31 encrypted). Wallets MAY ADDITIONALLY register for push notifications (FCM/APNs/Web Push) that carry NO sensitive content — only a wakeup signal. The actual approval payload is fetched from MessageBox after the push wakes the device.

**Rationale:** Push channels add operator key management + cloud-provider trust anchors; restricting them to wakeup-only keeps the security boundary at MessageBox. Mobile sub-300s TTL is served without compromising the §06 envelope guarantees.

**Follow-on edits:**
- §09.5.1 normative text adds: "MAY use push for wakeup; push payload MUST NOT include rendered_text or request_view_hash."
- §06.4 receive-transport list amended to clarify push is wakeup-only.

---

## 3. Fiat oracle (§15.5a / §12.5a / Q17) — **Multi-source median, 300s staleness bound**

**Position:** Wallet MUST query ≥2 of: BSV-overlay-published rate, CoinGecko, CoinMarketCap, BitGo public feed. Display median value across queried sources + confidence interval if sources disagree by >2%. Stale-bound: 300 seconds since last fresh query.

**Rationale:** No single-oracle SPOF; advisory (not security-critical) so confidence-interval display suffices; integrator may choose which sources from a recommended list.

**Follow-on edits:**
- §15.5a `fiat_estimate` field semantics include multi-source contract.
- §12.5a `fee_fiat_estimate` field same.
- Q17 marked RESOLVED in OPEN-QUESTIONS.

---

## 4. Express tier custody disclosure (§15.2.2 / ADR-0036) — **BOTH (b) + (c)**

**Position:** §15.2.2 Express tier MUST display:
- **(b) Tier-comparison table at sign-time** — side-by-side Default vs. Express security posture every time the user signs via Express, until they dismiss-permanently.
- **(c) Mandatory consent flow on first Express use** — user must type "I understand" (or operator-localized equivalent) before activation; consent captured + audit-event-logged.

**Rationale:** Both serve different moments — (c) captures informed initial consent; (b) sustains awareness across signings. Lit Protocol does similar with custody warnings; Coinbase MPC has comparable.

**Follow-on edits:**
- §15.2.2 expanded with normative consent flow + tier-comparison template (template text in ADR-0036 appendix).
- ADR-0036 expanded with the consent flow template.

---

## 5. Argon2id mobile parameters (§18.5 / ADR-0038 / Q29) — **Profile-conditional Argon2id (confirmed)**

**Position:** `profile-server`: m=256MiB, t=3, p=1. `profile-mobile`: m=64MiB, t=4, p=1. Same Argon2id primitive across both profiles; parameters tune to hardware. No algorithm split to scrypt.

**Rationale:** Same primitive = same security model = easier auditor review. Parameter tuning preserves ~equivalent GPU-grind resistance. Already in ADR-0038; this confirms as final.

**Follow-on edits:**
- ADR-0038 status: Q29 marked RESOLVED.
- Q59 (older mobile <2GB RAM fallback) remains OPEN — that's a different question (algorithm fallback chain for resource-starved devices); resolved later if needed.

---

## 6. Predictive presig regen (§06.19 / ADR-0041 / Q15) — **Wallet-only optimization, NOT protocol primitive**

**Position:** No `signing_intent` envelope kind added to wire format. Coordinator-side regen reads local wallet hints (sub-RPC or shared memory); operators implement at their discretion. CGGMP'24 protocol untouched.

**Rationale:** Wallet-only keeps wire spec clean. Coordinator-wallet IPC is operator-internal; protocol stays minimal. Maintainability + cggmp24-fidelity wins.

**Follow-on edits:**
- ADR-0041 §5 reframed from "RECOMMENDED protocol addition" to "RECOMMENDED operator implementation pattern."
- Q15 (Headless/agent sign profile — distinct question) remains OPEN.

---

## 7. GDPR Art.17 retention (§16.14 / ADR-0042 §C / Q47) — **Tombstone-with-hash (confirmed)**

**Position:** Per §10.12.1 + §16.14.3 — leaf preimage erased, leaf hash retained, Merkle root preserved. Audit-chain integrity unbroken; user erasure right satisfied. Spec-uniform across jurisdictions; no EU-out-of-scope cop-out.

**Rationale:** Already in spec text. Already in ADR-0042 Part C. Most legally defensible; preserves SOC2-audit usefulness; survives GDPR Art.17 challenge.

**Follow-on edits:**
- Q47 marked RESOLVED.

---

## 8. CISO function ownership (Q42) — **Quarterly rotation + external advisor retained**

**Position:** Operational CISO rotates quarterly between Calhoun (John) and Binary (Mitch). External advisor retained for Sev-1 IR-005 (certifier compromise) + IR-008 (presig-pool poisoning with broadcast). Retainer: ~$2-4k/mo.

**Rationale:** Rotation avoids SPOF and maintains cross-operator visibility. External advisor brings independent expertise during the highest-stakes incidents — both impact partnership-wide trust.

**Follow-on edits:**
- §16.16 added (new): CISO governance.
- Q42 marked RESOLVED.

---

## 9. SOC2 Type II timeline (Q43) — **v2, Schellman**

**Position:** Pursue SOC2 Type II for v2 (target: kickoff control-design prep in v1.5 / late 2026; observation period after Notary MVP launches; report ready mid-2027). Audit firm: Schellman.

**Rationale:** Schellman is fintech-favored, 30-50% cheaper than Big-4 for equivalent scope, recognized in crypto-custody ecosystem (audits Anchorage, others). Budget estimate: $30-50k for the initial audit + $20-30k/yr renewal.

**Follow-on edits:**
- ROADMAP §v2 adds SOC2 pursuit line item.
- Q43 marked RESOLVED.

---

## 10. Pen-test (Q44) — **Joint, Trail of Bits, v1.5 window**

**Position:** Joint pen-test of both stacks (bsv-mpc + rust-mpc + shared specs). Firm: Trail of Bits. Window: v1.5, ~4-6-week engagement. Budget: $150-300k.

**Rationale:** ToB published the TSS-library diff-fuzzing methodology that informed ADR-0037; engaging them is high-value-per-dollar. Joint scope catches cross-impl issues that per-impl misses. Public engagement report is trust-building.

**Follow-on edits:**
- ROADMAP v1.5 line for pen-test.
- Q44 marked RESOLVED.

---

## 11. VDP / bug-bounty (Q46) — **HackerOne managed (v1.5); add Immunefi (v2)**

**Position:** HackerOne managed program at v1.5 launch (broad researcher pool, mainstream security). Add Immunefi at v2 for crypto-specific findings (higher per-finding bounties). Both platforms; per-finding researcher chooses.

**Bounty budget:** HackerOne ~$50k/yr; Immunefi ~$100k/yr starting v2.

**Rationale:** HackerOne brings mainstream security researchers (web2 backgrounds, broad coverage). Immunefi attracts crypto specialists with bigger bounties. Together: maximum coverage.

**Follow-on edits:**
- §17 / new §17.15 VDP + bug-bounty obligations.
- ROADMAP v1.5 line for VDP setup; v2 line for Immunefi.
- Q46 marked RESOLVED.

---

## 12. PQ migration triggers (ADR-0043 / Q32) — **Concrete + falsifiable**

**Position:**

**Phase 1 (cert-chain layer — non-consensus):**
Triggers on (whichever first):
- (a) Production-ready Rust ML-DSA threshold implementation released (defined: at least one library at v1.0+ with CVE-disclosure pipeline AND one production deployment); OR
- (b) NIST FIPS 204 (ML-DSA) AND 2 independent published security audits of the Rust implementation.

**Phase 2 (MPC signing layer — consensus-dependent):**
Triggers on (BOTH must hold):
- (c) BSV consensus has an active proposal AND testnet activation for a PQ-compatible signature opcode; AND
- (d) Threshold-PQ scheme reaches CGGMP'24-equivalent maturity (defined: 2 production implementations with shared CVE-disclosure pipeline, ≥18-month deployment history).

**Rationale:** Concrete falsifiable triggers prevent indefinite procrastination AND prevent premature commitment to immature crypto. Phase 1 (cert layer) can move ~2-3 years out; Phase 2 (MPC layer) is BSV-consensus-dependent (open-ended).

**Follow-on edits:**
- ADR-0043 §"Phase 1" / "Phase 2" trigger sections updated with concrete (a)/(b) and (c)/(d) text.
- Q32 marked RESOLVED.

---

## Resolved → ADR sign-off status

After this resolution doc, the 13 new ADRs from the 2026-05-13 swarm pass have these positions baked in. ADR sign-off (Proposed → Accepted) still requires Mitch (Binary steward) on items affecting both stacks. The Mitch/Ishaan brief at `~/bsv/mpc/MITCH-ISHAAN-BRIEF-2026-05-13.md` lists which.

| ADR | Affected by resolution | Mitch sign-off required? |
|---|---|---|
| 0031 | #1 hybrid rendering | Yes |
| 0032 | #2 push channel; #3 fiat | Yes (wire-compat) |
| 0033 | #3 fiat | Yes |
| 0034 | #1 hybrid; #6 wallet-only regen | Yes |
| 0035 | (no resolution-driven changes) | Yes |
| 0036 | #4 Express disclosure | Yes |
| 0037 | (already locked; resolution unaffected) | Yes (M1-critical) |
| 0038 | #5 Argon2id mobile params (confirmed) | Yes |
| 0039 | (no resolution-driven changes) | Yes |
| 0040 | (no resolution-driven changes) | Yes |
| 0041 | #6 wallet-only regen | Yes |
| 0042 | #7 GDPR tombstone (confirmed); #8 CISO; #9 SOC2; #10 pen-test; #11 VDP | Yes |
| 0043 | #12 PQ triggers | Yes |
| 0044 | (already standalone, no resolution-driven changes) | Yes (M1-critical) |
| 0045 | (correctness fix for ADR-0040) | Yes |
| 0046 | (correctness fix for ADR-0040) | Yes |
| 0047 | (operational; no resolution-driven changes) | Yes |
| 0048 | (Pro tier; v2 — no resolution-driven changes) | Yes |
| 0049 | (operational; no resolution-driven changes) | Yes |

## What's now FULLY OPEN (after resolution)

Q14 AuthSocket extraction (loop-1, deferred), Q15 headless agent profile, Q18 audit-trail privacy for `listSignedActions`, Q19 denial UX symmetry (operator-configurable), Q20 Notary incident transparency, Q21 Express x402 routing overhead, Q22 fully_loaded_cost_estimate in discovery, Q23 multi-region Notary cost, Q24 CHIP token mint amortization, Q25 STH decommission cost, Q26 parser-diff fuzz corpus ownership (loop-3 partial resolution), Q27 request_view_hash for non-payment intents (ADR-0044 partial resolution), Q28 re-Rekor cadence vs latency (ADR-0046 partial), Q30 multi-source STH lookup trust, Q31 cosigner-side malicious-dep policy, Q33 operator credential rotation overlap (ADR-0049 partial), Q34 witness-cosign DoS (ADR-0047 partial), Q35 AI-agent wallet threat model, Q36 auxinfo compute measurement, Q37 Pro tier subset pool, Q38 DKG split for mobile, Q39 STH publish for TOFU, Q40 iroh activation, Q41 pool-depth drift alarm, Q45 vendor-risk register maintenance, Q48 insurance posture, Q49 regulatory perimeter, Q50-Q60 (loop-2 Qs), Q59 mobile-resource KDF fallback chain.

Open Qs total: ~26 (down from ~46). The majority of "operational follow-up" Qs remain as tracking items for v1.5 / v2 milestones.

## See also

- ADRs 0031-0049 in `decisions/`
- Convergence: `~/bsv/mpc/swarm-2026-05-13/CONVERGENCE.md` (loop-1) + loop-2 reports
- Mitch/Ishaan brief: `~/bsv/mpc/MITCH-ISHAAN-BRIEF-2026-05-13.md`
- ROADMAP: `ROADMAP.md`
