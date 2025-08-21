import glob
import json
import os
import sys

locales_dir = os.path.dirname(os.path.abspath(__file__))

# Base directory with English files (reference)
en_dir = os.path.join(locales_dir, "en_US")

# Get all language directories (excluding the English one)
lang_dirs = [
    os.path.join(locales_dir, d)
    for d in os.listdir(locales_dir)
    if os.path.isdir(os.path.join(locales_dir, d)) and d != "en_US"
]

# Get all JSON files in English directory
en_files = glob.glob(os.path.join(en_dir, "*.json"))
en_filenames = [os.path.basename(f) for f in en_files]

print(f"Comparing {len(lang_dirs)} language directories against {en_dir}...")

has_errors = False

for lang_dir in lang_dirs:
    print(f"\nChecking {os.path.basename(lang_dir)}...")

    # Check for missing files
    lang_files = glob.glob(os.path.join(lang_dir, "*.json"))
    lang_filenames = [os.path.basename(f) for f in lang_files]

    missing_files = set(en_filenames) - set(lang_filenames)
    if missing_files:
        print(f"  Missing files in {lang_dir}: {', '.join(missing_files)}")

    # Check for missing keys in existing files
    for filename in set(en_filenames).intersection(set(lang_filenames)):
        en_file_path = os.path.join(en_dir, filename)
        lang_file_path = os.path.join(lang_dir, filename)

        with open(en_file_path, encoding="utf-8") as f:
            en_data = json.load(f)

        with open(lang_file_path, encoding="utf-8") as f:
            lang_data = json.load(f)

        missing_keys = []
        for key in en_data:
            if key not in lang_data:
                missing_keys.append(key)

        if missing_keys:
            print(f"  In {filename}, missing keys: {', '.join(missing_keys)}")
            has_errors = True

        extra_keys = []
        for key in lang_data:
            if key not in en_data:
                extra_keys.append(key)

        if extra_keys:
            print(f"  In {filename}, extra keys: {', '.join(extra_keys)}")
            has_errors = True

if has_errors:
    print("\n❌ Translation check failed!")
    sys.exit(1)
else:
    print("\n✅ All translations are complete!")
