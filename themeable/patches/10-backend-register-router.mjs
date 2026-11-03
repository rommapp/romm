// Registers the Branding API router after RomM's own routers.
export const file = "backend/main.py";
export const description = "Register the themeable router (/api/themeable) in the FastAPI app";
const MARKER = "# romm-themeable: branding router";

export function apply(text) {
  if (text.includes(MARKER)) return text;
  const lines = text.split("\n");
  const last = lines.findLastIndex((l) => /^app\.include_router\(\w+, prefix="\/api"\)\s*$/.test(l));
  if (last < 0) throw new Error('no `app.include_router(<router>, prefix="/api")` line to anchor after');
  lines.splice(
    last + 1,
    0,
    `${MARKER}`,
    "from endpoints.themeable import router as themeable_router  # noqa: E402",
    '',
    'app.include_router(themeable_router, prefix="/api")',
  );
  return lines.join("\n");
}
