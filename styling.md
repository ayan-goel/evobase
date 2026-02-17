# Frontend Styling Guide (Tailwind + shadcn)

This guide defines the visual system for the app: typography, spacing, surfaces, borders, buttons, layout, and responsive behavior. The goal is a clean, modern, slightly “frosted/glass” look with strong hierarchy and consistent rhythm.

---

## 1) Foundations

### Typeface
- **Font:** DM Sans (Google Font)
- **Weights:** 400 / 500 / 600 / 700
- Applied globally via CSS variable: `--font-dm-sans`
- Use DM Sans for **all** type (even the serif slot for consistency)
- Enable subpixel antialiasing site-wide

**Next.js setup (recommended)**
- Use `next/font/google` to load DM Sans and assign to `--font-dm-sans`
- Apply `antialiased` on `<html>` and `<body>`

---

## 2) Typography System

### Core rules
- Headlines: **tight leading + tight tracking**
- Body: **relaxed leading**
- Microcopy: **small + medium weight**
- Prefer `text-balance` on headings to avoid orphans
- (Optional) define `text-pretty` utility but it’s not required

### Type scale (Tailwind)
**Hero headline**
- `text-[clamp(2rem,6vw,4.5rem)] leading-[1.05] tracking-tight text-balance font-semibold`

**Section headings**
- `text-2xl sm:text-3xl md:text-4xl leading-tight tracking-tight text-balance font-semibold`

**Subhead / lead text**
- `text-sm sm:text-base leading-relaxed text-white/70`

**Body**
- `text-sm sm:text-base leading-relaxed text-white/75`

**Labels / nav / badges**
- `text-xs font-medium text-white/70`
- Use `font-semibold` for emphasis

**Testimonial quote**
- `text-lg sm:text-xl leading-relaxed text-white/85`

### Do / Don’t
- Do: Use 1–2 font sizes per section (clear hierarchy)
- Don’t: Mix too many weights; reserve 700 for rare emphasis

---

## 3) Layout & Spacing

### Container widths
Use centered layout with consistent max widths:

- Nav: `max-w-2xl`
- Hero/video/testimonials/CTA: `max-w-3xl`
- Features/pricing/FAQ/footer: `max-w-4xl`

**Recommended container wrapper**
- `mx-auto w-full px-4`

### Vertical rhythm
- Default section spacing: `pb-14`
- Larger sections (pricing/FAQ): `pb-16`
- Hero top spacing to clear fixed nav: `pt-28 sm:pt-32`

### Inner spacing
- Cards: `p-4 sm:p-6`
- CTA panel: `p-8 sm:p-12`

### Section alignment
- Most sections: `flex justify-center`
- Use consistent `gap-` spacing (prefer `gap-6`, `gap-8`, `gap-10`)

---

## 4) Radius System

### Base radius
- Base: **10px** (`0.625rem`)
- Cards: `rounded-xl`
- Video container: `rounded-2xl`
- “Phone mockup” container: `rounded-[2rem]`
- Pills (nav + buttons): `rounded-full`

**Rule of thumb**
- Pills for interactive items
- Rounded-xl for surfaces
- Rounded-2xl+ for “hero” media

---

## 5) Surfaces, Borders, and Glass

### Borders
- Subtle, low-opacity white:
  - `border border-white/[0.06]` or `border-white/[0.08]`

### Card surfaces
- Frosted layers using ultra-low opacity fills:
  - `bg-white/[0.02]` to `bg-white/[0.06]`

### Nav bar
- Glassy floating nav:
  - `backdrop-blur-xl bg-white/[0.04] border border-white/[0.08]`

### Shadows (sparingly)
- Use soft glow for hero media / mockups
- Use `shadow-lg` only for feature media highlights
- Avoid harsh shadows and heavy elevation

**Surface recipe (default card)**
- `rounded-xl border border-white/[0.06] bg-white/[0.03]`

---

## 6) Buttons

Two button styles: **Solid** + **Ghost**  
Both are pill-shaped and minimal.

### Solid (Primary CTA)
- `rounded-full bg-white text-black`
- Size: `h-10 sm:h-11 px-6 sm:px-10`
- Text: `text-sm font-semibold`
- Hover: `hover:bg-white/90`
- Transition: `transition-colors`

### Ghost (Secondary CTA)
- `rounded-full bg-transparent border border-white/[0.10] text-white`
- Size: `h-10 sm:h-11 px-6 sm:px-10`
- Text: `text-sm font-medium`
- Hover: `hover:bg-white/[0.06] hover:border-white/[0.16]`
- Transition: `transition-colors`

### Button rules
- Keep CTAs short (1–3 words)
- Max 2 buttons side-by-side in a row
- Use primary only once per section (avoid CTA spam)

---

## 7) Grids & Patterns

### Default grid behavior
- Mobile-first stacking
- 2 columns at `sm:` or `md:` depending on density

**Common grids**
- Problem cards: `grid gap-4 sm:grid-cols-2`
- Feature bento: `grid gap-4 md:grid-cols-2`
- Pricing: `grid gap-6 md:grid-cols-2`
- Footer link columns: `flex flex-col gap-12 sm:flex-row sm:gap-16`

### FAQ layout
- `lg:flex lg:flex-row`
- Left column sticky on desktop:
  - `lg:sticky lg:top-24`
- Right column is the accordion/list

---

## 8) Responsive Rules

### Breakpoints
- Mobile-first
- Layout shifts at `sm:` and `md:` primarily
- Use `lg:` only for FAQ sticky layout and wide footers

### Navigation responsiveness
- Links hidden on mobile:
  - `hidden sm:flex`
- Keep nav compact and fixed

### “How It Works” layout
- Stack vertically on mobile
- Side-by-side on `md:`

---

## 9) shadcn Component Conventions

### Use shadcn for:
- `Button`, `Card`, `Badge`, `Accordion`, `Tabs`, `Dialog`, `Input`, `DropdownMenu`

### Styling strategy
- Prefer **class overrides** in usage sites for layout/spacing
- Keep component-level customization minimal and consistent
- Use `cn()` utility and variant patterns

**Card**
- Base:
  - `rounded-xl border border-white/[0.06] bg-white/[0.03]`

**Badge**
- For subtle labels:
  - `bg-white/[0.06] text-white/80 border border-white/[0.10] text-xs font-medium rounded-full`

**Accordion**
- Subtle separators:
  - borders at `border-white/[0.06]`
- Keep content `text-white/70 leading-relaxed`

---

## 10) Color & Contrast Guidance

### Text colors (dark background assumed)
- Primary text: `text-white`
- Secondary text: `text-white/70`
- Tertiary text: `text-white/55`
- Borders: `border-white/[0.06]` to `[0.10]`
- Surfaces: `bg-white/[0.02]` to `[0.06]`

### Contrast rules
- Ensure CTA buttons always have clear contrast
- Avoid mid-opacity text on mid-opacity surfaces without bumping one up

---

## 11) Recommended Utility “Recipes”

### Page background
- Dark base with subtle gradient (optional):
  - `bg-black text-white`
  - add `bg-gradient-to-b from-black via-black to-black` only if needed

### Section wrapper
- `w-full flex justify-center pb-14`
- `pb-16` for heavier sections

### Container
- `mx-auto w-full max-w-4xl px-4`

### Default card
- `rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-6`

### Glass nav
- `fixed top-4 left-1/2 -translate-x-1/2 z-50`
- `w-[calc(100%-2rem)] max-w-2xl`
- `rounded-full border border-white/[0.08] bg-white/[0.04] backdrop-blur-xl`
- `px-4 py-2`

### Hero title
- `text-[clamp(2rem,6vw,4.5rem)] leading-[1.05] tracking-tight text-balance font-semibold`

### CTA panel
- `rounded-xl border border-white/[0.08] bg-white/[0.04] p-8 sm:p-12`

---

## 12) Consistency Rules (Non-Negotiables)

- DM Sans is the only typeface.
- Use tight tracking + tight leading for headings.
- Use low-opacity white borders for separation.
- Use frosted, ultra-low-opacity surfaces for cards.
- Prefer pill shapes for nav/buttons.
- Keep shadows minimal and soft.
- Always center sections and constrain width with max-w containers.
- Maintain consistent vertical rhythm (`pb-14` / `pb-16`).
- Default to mobile-first; introduce grids at `sm:` / `md:`.

---

## 13) Implementation Notes (Tailwind Config)

- Define CSS variable for DM Sans:
  - `--font-dm-sans`
- Set Tailwind `fontFamily`:
  - `sans`, `serif` both map to DM Sans stack
- Consider adding utilities:
  - `text-balance` (Tailwind supports `text-balance`)
  - `text-pretty` (optional custom utility)

---

## 14) Quick Visual Checklist

If the page looks “off,” check:
- Are borders too strong (opacity too high)?
- Are cards too filled (opacity too high)?
- Are headings too loose (leading/tracking not tight)?
- Are buttons not pill-shaped?
- Is spacing inconsistent between sections?
- Are containers exceeding max widths?

The design should feel: clean, calm, frosted, and centered.
