"""Check that every translation key used in the frontend exists in en_US.

vue-i18n renders an unknown key as the key itself, so a typo or a rename
that misses a call site ships as `settings.scan-settings` on screen instead
of "Scan settings". Nothing else catches that: `t()` accepts any string by
design, so TypeScript can't reject one.

Only literal keys are checked. Dynamic ones (`t(labelKey)`,
`t(f"scan.{source}")`) are invisible here, as are `te()` calls, which exist
to ask whether a key is missing.
"""

import glob
import json
import os
import re
import sys

locales_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(locales_dir)
en_dir = os.path.join(locales_dir, "en_US")

# `t("x.y")`, `$t('x.y')`, `i18n.global.t("x.y")`, `tm("x")`. The lookbehind
# keeps `get(`, `format(` and friends from passing as `t(`.
CALL = re.compile(r"""(?<![\w.$])(?:\$t|t|tm)\(\s*["']([\w.-]+)["']""")

# Reference docs in a comment shouldn't fail the build.
COMMENT = re.compile(r"^\s*(//|/?\*)")


def load_reference():
    messages = {}
    for path in glob.glob(os.path.join(en_dir, "*.json")):
        namespace = os.path.basename(path)[: -len(".json")]
        with open(path, encoding="utf-8") as f:
            messages[namespace] = json.load(f)
    return messages


def source_files():
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in ("__generated__", "locales")]
        for name in files:
            if name.endswith((".ts", ".vue")):
                yield os.path.join(root, name)


def used_keys(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    code = "".join("\n" if COMMENT.match(line) else line for line in lines)
    for match in CALL.finditer(code):
        yield match.group(1), code.count("\n", 0, match.start()) + 1


def resolve(key, messages):
    namespace, _, rest = key.partition(".")
    if namespace not in messages:
        return False
    # `tm("common")` addresses the namespace itself.
    return rest in messages[namespace] if rest else True


def main():
    messages = load_reference()
    print(f"Checking translation keys against {en_dir}...")

    missing = []
    for path in sorted(source_files()):
        for key, line in used_keys(path):
            if not resolve(key, messages):
                missing.append((os.path.relpath(path, src_dir), line, key))

    if missing:
        print(f"\n{len(missing)} key(s) not found in en_US:\n")
        for path, line, key in missing:
            print(f"  src/{path}:{line}: {key}")
        print("\nAdd the key to every locale, or fix the call site.")
        sys.exit(1)

    print("\n✅ All translation keys exist!")


if __name__ == "__main__":
    main()
