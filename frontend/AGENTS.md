# RomM frontend

## The frontend has two UIs - know which you're in

- **v1 is frozen.** Everything under `frontend/src/views/`, `src/components/`, `src/console/`, `src/layouts/` is legacy and will be deleted wholesale in a final wave. **Do not refactor v1.** Only touch it for a critical bug, and when a v2 fork exists, mark the v1 export `@deprecated`.
- **v2 is the active rewrite** under `frontend/src/v2/`, gated by `user.ui_settings.uiVersion`. It has its own design system (tokens), primitive library (`R*` components in `src/v2/lib/`), universal input (mouse/touch/keyboard/gamepad), and responsive system. New frontend work goes in v2.

v2 has a detailed constitution, split across the `frontend-v2-*` skills in `.claude/skills/`. **Read the relevant skill before editing v2 code.**

## Commands (`cd frontend`)

```bash
npm install                         # install (Node 24)
npm run dev                         # dev server :3000
npm run typecheck                   # vue-tsc
npm run typecheck:scripts           # tsc on the Node/Vite tooling in scripts/
npm run test                        # vitest (+ Storybook play() tests)
npm run test:e2e                    # playwright (needs a running app + seeded e2e users)
npm run build                       # production build
npm run generate                    # regenerate types from backend OpenAPI (backend must be running)
npm run build:tokens                # regenerate v2 tokens.css (auto on predev/prebuild)
npm run storybook                   # component library on :6006
python3 src/locales/check_i18n_locales.py   # i18n parity check
python3 src/locales/check_i18n_sorted.py    # locale keys sorted (--fix to sort)
```
