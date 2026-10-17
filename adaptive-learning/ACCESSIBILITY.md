# Accessibility review

## Reviewed UI affordances

- The page uses a single main landmark, a skip link, hierarchical headings, and semantic lesson articles.
- Quiz choices are generated as native radio inputs grouped in a `fieldset` with a `legend`; each choice is wrapped in its visible label.
- Starting a quiz moves keyboard focus to its heading; answer feedback is announced through a polite live region, and keyboard focus has a visible outline.
- Text is 16 px by default and layouts reflow on narrow screens. Reduced-motion preferences disable smooth scrolling.
- Source attribution links have visible text, and lesson content remains available as ordinary HTML text.
- The principal color pairs were calculated against the shipped CSS: body text on white 15.36:1; paragraph text on white 6.27:1; white button text on blue 6.04:1; blue tag text on page background 5.48:1; dark-blue focus outline on the page background 9.77:1. Text ratios exceed WCAG AA for normal text, and the focus indicator contrast exceeds 3:1.

Automated markup checks in `tests/test_portfolio_projects.py` confirm unique IDs, a working skip-link target, one main heading, named buttons, the generated radio/fieldset pattern, polite feedback announcement, and minimum text/focus contrast ratios against the rendered CSS colors. GitHub Actions also launches Chromium and runs axe-core, checks keyboard-only access through a quiz answer, verifies focus movement and answer feedback, and checks for horizontal overflow at narrow viewport widths.

## Limits and manual release check

This is a code and contrast review, not a certification. The page was opened in Android Chrome and its progress and recommendation APIs responded, but this Termux session cannot capture the Android display or accessibility tree. Before a public release, manually test keyboard-only operation, zoom/reflow at 200%, and at least one screen reader/browser pairing (for example, TalkBack with Chrome). Lesson authors remain responsible for meaningful headings, plain language, and accessible source documents.
