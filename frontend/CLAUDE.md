# Frontend CLAUDE.md

## What this is

BeeWork dashboard -- a single-user control panel for triggering and monitoring the BeeWork multi-agent knowledge base pipeline. Not a public-facing app. Built for demo and personal use.

## Stack

- React + Vite + TypeScript
- Convex (backend, real-time subscriptions)
- Tailwind CSS v4 + shadcn/ui components
- Single light theme, no dark mode

## Design Philosophy

Bee-themed. Warm. Distinct from the typical AI/SaaS dashboard aesthetic.

**DO:**
- Flat and minimal. No drop shadows, no box shadows, no glow effects.
- Sharp corners everywhere. `--radius` is 0. Never add border-radius to elements.
- Use thin borders (1px) with `border-border` (#F0D9A8 warm honey) to define surfaces, not elevation.
- Generous whitespace. Let the layout breathe.
- Use the bee palette: yellows and honey tones for warmth, blue (#27B7D9) sparingly as a focal accent, warm grays for muted text.
- Typography-driven hierarchy. Size, weight, and color do the work -- not cards or containers.
- Honeycomb background pattern on the page body (to be added). Content sits directly on it or on clean white surfaces.
- Status uses color semantically: bee-yellow for active/in-progress, blue for informational, red for errors, green for success.

**DO NOT:**
- No rounded corners. Not even "slightly rounded." Zero.
- No box-shadow or drop-shadow on any element.
- No gradients on buttons or containers.
- No heavy card-based layouts where every piece of content lives in its own bordered, padded, shadowed box.
- No glassmorphism, no blur backdrops, no neon accents.
- No dark mode. One theme.
- No emoji in code, comments, or UI text.

## Color Tokens

Semantic tokens are in `src/index.css`. Use Tailwind classes:

| Class | Hex | Use for |
|---|---|---|
| `bg-background` | #FFFFFF | Page body |
| `text-foreground` | #212121 | Primary text |
| `bg-primary` | #FBB80C | Primary buttons, key actions |
| `text-primary-foreground` | #2E2A26 | Text on primary surfaces |
| `bg-secondary` | #FFF5D9 | Secondary surfaces |
| `bg-muted` | #FCE2AD | Subdued areas, code blocks |
| `text-muted-foreground` | #7A7067 | Secondary text, timestamps |
| `bg-accent` / `text-accent` | #27B7D9 | Blue highlights, links |
| `text-destructive` | #DC2626 | Errors |
| `border-border` | #F0D9A8 | Default borders |
| `bg-honeycomb` | #FCE2AD | Honeycomb pattern dark |
| `bg-honeycomb-light` | #FFF5D9 | Honeycomb pattern light |
| `text-highlight` | #FFBD59 | Yellow highlight text |
| `bg-wing` | #CDDFDF | Soft teal surface |

## Component Conventions

- Import shadcn components from `@/components/ui/*`.
- Use `cn()` from `@/lib/utils` for conditional class merging.
- Keep components in `src/components/`. Page-level layouts in `src/App.tsx` or `src/pages/`.
- Prefer inline Tailwind classes over separate CSS.
- Keep components small. One file per component. No barrel exports.

## Code Style

- Clear over clever. Delete dead code, don't comment it out.
- No excessive error boundary nesting or try/catch wrapping.
- Minimal dependencies. Use what's already installed before adding packages.
