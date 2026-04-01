#!/usr/bin/env python3
"""
OpenLoopholes.com — IRC Title 26 Parser

Downloads and parses the Internal Revenue Code (Title 26) from
uscode.house.gov XML into individual section files for AI consumption.

Usage:
    python parse_tax_code.py              # Parse existing XML
    python parse_tax_code.py --download   # Download fresh XML first
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://xml.house.gov/schemas/uslm/1.0}"
TAX_CODE_DIR = Path(__file__).resolve().parent / "tax_code"
RAW_DIR = TAX_CODE_DIR / "raw"
SECTIONS_DIR = TAX_CODE_DIR / "sections"
INDEX_PATH = TAX_CODE_DIR / "index.json"
XML_PATH = RAW_DIR / "usc26.xml"


def extract_text(elem) -> str:
    """Extract all text content from an XML element, stripping tags."""
    return ET.tostring(elem, encoding="unicode", method="text").strip()


def parse_sections():
    """Parse the Title 26 XML into individual section text files."""
    print(f"Parsing {XML_PATH}...")
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    main = root.find(f"{NS}main")

    sections = main.findall(f".//{NS}section")
    print(f"Found {len(sections)} <section> elements")

    index = {}
    written = 0

    for section in sections:
        identifier = section.attrib.get("identifier", "")
        if not identifier or not identifier.startswith("/us/usc/t26/s"):
            continue

        # Extract section number from identifier (e.g., /us/usc/t26/s401 -> 401)
        section_num = identifier.replace("/us/usc/t26/s", "")

        # Get heading
        heading_elem = section.find(f"{NS}heading")
        heading = heading_elem.text.strip() if heading_elem is not None and heading_elem.text else ""

        # Get full text
        full_text = extract_text(section)

        if not full_text.strip():
            continue

        # Write section file
        filename = f"section_{section_num}.txt"
        filepath = SECTIONS_DIR / filename
        with open(filepath, "w") as f:
            f.write(full_text)

        # Add to index
        index[section_num] = {
            "title": heading,
            "file": filename,
            "identifier": identifier,
            "chars": len(full_text),
            "words": len(full_text.split()),
        }
        written += 1

    # Write index
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Written {written} section files to {SECTIONS_DIR}/")
    print(f"Index saved to {INDEX_PATH}")

    # Stats
    total_chars = sum(s["chars"] for s in index.values())
    total_words = sum(s["words"] for s in index.values())
    print(f"Total: {total_chars:,} characters, {total_words:,} words")


def download_xml():
    """Download Title 26 XML from House.gov."""
    import urllib.request
    import zipfile

    url = "https://uscode.house.gov/download/releasepoints/us/pl/119/73/xml_usc26@119-73.zip"
    zip_path = RAW_DIR / "title26.zip"

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Title 26 from {url}...")
    urllib.request.urlretrieve(url, zip_path)
    print(f"Extracting...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(RAW_DIR)
    print(f"Done. XML at {XML_PATH}")


if __name__ == "__main__":
    import sys

    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    if "--download" in sys.argv:
        download_xml()

    if not XML_PATH.exists():
        print(f"ERROR: {XML_PATH} not found. Run with --download first.")
        sys.exit(1)

    parse_sections()
