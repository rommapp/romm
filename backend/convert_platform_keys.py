#!/usr/bin/env python3
"""
Temporary script to convert platform list string keys to UniversalPlatformSlug enum values
"""

import re

from handler.metadata.base_hander import UniversalPlatformSlug


def string_to_enum_name(slug_string):
    """Convert a slug string to its corresponding enum name"""
    for enum_value in UniversalPlatformSlug:
        if enum_value.value == slug_string:
            return enum_value.name
    return None


def convert_platform_list_keys(file_path):
    """Convert string keys to enum keys in a platform list file"""
    with open(file_path, "r") as f:
        content = f.read()

    # Find all string keys in the format "key": {
    pattern = r'    "([^"]+)": \{'
    matches = re.findall(pattern, content)

    replacements = []
    for match in matches:
        enum_name = string_to_enum_name(match)
        if enum_name:
            old_key = f'    "{match}": {{'
            new_key = f"    UniversalPlatformSlug.{enum_name}: {{"
            replacements.append((old_key, new_key))
            print(f"'{match}' -> 'UniversalPlatformSlug.{enum_name}'")
        else:
            print(f"WARNING: No enum found for '{match}'")

    # Apply replacements
    for old, new in replacements:
        content = content.replace(old, new)

    # Update the type annotation
    if "dict[str, " in content:
        content = content.replace("dict[str, ", "dict[UniversalPlatformSlug, ")

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Updated {len(replacements)} keys in {file_path}")


if __name__ == "__main__":
    files_to_convert = [
        "handler/metadata/igdb_handler.py",
        "handler/metadata/moby_handler.py",
        "handler/metadata/ra_handler.py",
        "handler/metadata/ss_handler.py",
        "handler/metadata/launchbox_handler.py",
        "handler/metadata/hasheous_handler.py",
        "handler/metadata/tgdb_handler.py",
    ]

    for file_path in files_to_convert:
        try:
            print(f"\nProcessing {file_path}...")
            convert_platform_list_keys(file_path)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
