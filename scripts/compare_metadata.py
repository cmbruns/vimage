#!/usr/bin/env python3
import json
import sys

import exiftool


def load_metadata(path):
    with exiftool.ExifTool() as et:
        raw = et.execute("-j", path)
        return json.loads(raw)[0]


def compare_metadata(meta1, meta2):
    keys = set(meta1.keys()) | set(meta2.keys())
    diffs = []

    for key in sorted(keys):
        v1 = meta1.get(key)
        v2 = meta2.get(key)
        if v1 != v2:
            diffs.append((key, v1, v2))

    return diffs


def main(file1, file2):
    meta1 = load_metadata(file1)
    meta2 = load_metadata(file2)

    diffs = compare_metadata(meta1, meta2)

    print(f"Comparing metadata:\n  {file1}\n  {file2}\n")
    if not diffs:
        print("No differences found.")
        return

    print("Differences:")
    for key, v1, v2 in diffs:
        print(f"- {key}")
        print(f"    {file1}: {v1}")
        print(f"    {file2}: {v2}")


def cmd_main():
    if len(sys.argv) != 3:
        print("Usage: compare_meta.py file1 file2")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main(
        r"C:\Users\cmbruns\Pictures\360CameraSamples\XiaomiMisphere\IMG_20260705_133914.JPG",
        r"C:\Users\cmbruns\Pictures\360CameraSamples\XiaomiMisphere\IMG_20260705_133958.JPG",
    )
