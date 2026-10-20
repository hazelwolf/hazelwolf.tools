---
name: marketing-video-script
description: >-
  Write a production-ready marketing, brand, product, or explainer video script
  in the three-column format (Voice-over | On-screen text | Visual) with
  production notes and sources. Use when the user asks for a video script,
  storyboard script, launch/promo/explainer/customer-story video, or voice-over
  copy for a campaign, and wants it to follow marketing best practices.
---

# Marketing video script

Writes a script that follows proven marketing-video practice, in the fixed
three-column template (Voice-over | On-screen text | Visual). Output is a
frame-by-frame script a voice artist, motion designer and editor can all work from.

Read before drafting:

- `references/script-template.md` — the exact output structure. Always follow it.
- `references/best-practices.md` — the rules to apply and the pre-delivery checklist.

## Workflow

1. **Collect the brief.** Ask only for what is missing, in one short message:
   - Brand / client, and the audience (who watches, what they do next)
   - The single message to leave them with, and the call to action
   - Video type and length (default: 90-120 s, ~150-170 words/min of voice-over)
   - Tone (default: confident, warm, lightly witty), voice (brand "we" by default)
   - Proof available: real numbers, customers, footage, and their sources
   - Anything that must not be claimed (legal, unconfirmed engagements)
   If the user supplied a brief, a deck or source docs, use them and skip the questions.
2. **Pick the arc.** Default to this: *Hook (familiar world / big number) →
   Shift (why now) → Problem (made tangible) → Pain quantified → Solution reveal →
   Capabilities (max 3) → Outcome (hero number) → Expand (what's next) → Brand sign-off.*
   Shorter videos drop beats, they do not compress them.
3. **Draft the beats** as table rows: one idea per row, voice-over written to be
   heard, on-screen text as a reinforcing headline (never a transcript), visual as a
   direction an editor can shoot or animate.
4. **Do the maths once.** Any computed figure must show its working in the Production
   Notes and be consistent everywhere it appears. Label assumptions as illustrative.
5. **Add Production Notes and Sources** (see template). Flag every claim that rests on an
   assumption or an unconfirmed fact.
6. **Run the checklist** in `references/best-practices.md` and fix failures before delivering.
7. **Deliver** as Markdown with the three-column table, saved to the path the user
   names (default: `./<brand>-<topic>-video-script.md`). Offer a `.docx`/PDF export or a
   voice-over-only read-through (feeds the `voicestudio` skill) as a follow-up.

## Hard rules

- Never invent statistics, customer names, quotes, or engagements. If a number is
  needed and not provided, use a clearly marked placeholder `[STAT: needs source]`.
- Every real figure gets a source in the Sources section; every modelled figure is
  labelled "illustrative" on screen and in the notes.
- Voice-over is spoken language: short sentences, contractions, no jargon the
  audience wouldn't say aloud, no sentence that can't be said in one breath.
- Do not name or imply third-party brand endorsement beyond what the user confirms.
- Keep the header block: title, status line (draft / review copy + date), one-line
  description of the column layout.
