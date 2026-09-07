"""Ensure locale JSON files have their keys sorted alphabetically.

Run without arguments to check (exits non-zero on any unsorted file); pass
``--fix`` to rewrite the offending files in place. Sorting is applied
recursively so nested objects (e.g. settings.json) are checked too.
"""

import argparse
import glob
import json
import os
import sys

locales_dir = os.path.dirname(os.path.abspath(__file__))


def sort_recursive(value):
    """Return a copy with every dict's keys sorted alphabetically."""
    if isinstance(value, dict):
        return {key: sort_recursive(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [sort_recursive(item) for item in value]
    return value


def dump(data):
    # Match Prettier's formatting: 2-space indent, unicode preserved, trailing newline.
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite unsorted files in place instead of failing.",
    )
    args = parser.parse_args()

    json_files = sorted(glob.glob(os.path.join(locales_dir, "*", "*.json")))
    unsorted = []

    for file_path in json_files:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        sorted_dump = dump(sort_recursive(data))

        with open(file_path, encoding="utf-8") as f:
            current = f.read()

        if current != sorted_dump:
            rel = os.path.relpath(file_path, locales_dir)
            unsorted.append(rel)
            if args.fix:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(sorted_dump)

    if not unsorted:
        print("✅ All locale files are sorted alphabetically!")
        return

    if args.fix:
        print(f"🔧 Sorted {len(unsorted)} file(s):")
        for rel in unsorted:
            print(f"  {rel}")
        return

    print("❌ The following locale files are not sorted alphabetically:")
    for rel in unsorted:
        print(f"  {rel}")
    print("\nRun 'python3 frontend/src/locales/check_i18n_sorted.py --fix' to fix.")
    sys.exit(1)


if __name__ == "__main__":
    main()
