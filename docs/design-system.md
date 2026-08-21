# Loop OS Design System — "Ledger"

Visual identity for Loop OS diagrams and docs. The metaphor is the system itself:
a paper ledger that is written once, sealed, and never quietly edited. Warm paper,
dark umber ink, and one wax-seal red accent — the color of the seal, used only for
what the system marks as focal.

## Color tokens

| Role | Value | Use |
|---|---|---|
| `paper` | `#f7f5f0` | Page background |
| `paper-2` | `#fbfaf7` | Raised container / external-surface fill |
| `ink` | `#2b2925` | Primary text, solid strokes |
| `muted` | `#6b665c` | Secondary text, default arrows |
| `soft` | `#8b857b` | Tertiary labels, rail captions |
| `rule` | `rgba(43,41,37,0.12)` | Hairline dividers |
| `accent` | `#a63d2f` | Wax-seal red — 1–2 focal elements max |
| `accent-tint` | `rgba(166,61,47,0.07)` | Focal band/box fill |
| `link` | `#35618e` | External/API arrows (rarely needed) |

Derived opaque mixes (for seam-free stacked fills): `ink @ 5%` on white ≈ `#f2f1ee`.

## Typography

- **Title** — Instrument Serif 400. Editorial, ledger-headline feel.
- **Names / labels** — Geist 600, 12–16px.
- **Technical content** (paths, instruments, commands) — Geist Mono, 8–9px.

## Rules

- Accent is the seal: at most 1–2 elements per diagram. Everything else ink/muted/soft.
- Borders, never shadows. Radius ≤ 8px.
- What ships in this repo (OS + kernel) sits on solid-stroked white; what lives
  outside (your application repo) sits on dashed-stroked `paper-2`.
