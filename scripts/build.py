#!/usr/bin/env python3
"""Validate the editable YAML catalog and render a standalone Pages site."""

import argparse
import html
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESERVED_IDS = {"__proto__", "prototype", "constructor"}
FIELDS = ("id", "name", "subtitle", "store", "price", "emoji", "glow", "tag",
          "url", "description", "uses", "note")
PLACEHOLDERS = ("<!-- STORE_FILTERS -->", "__CATALOG_JSON__")


class CatalogError(ValueError):
    """An invalid catalog entry or template configuration."""


def load_catalog(path):
    try:
        catalog = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"No se pudo leer el catálogo {path}: {exc}") from exc
    return load_catalog_data(catalog)


def load_catalog_data(catalog):
    if not isinstance(catalog, dict) or set(catalog) != {"categories"}:
        raise CatalogError("El catálogo debe contener únicamente una lista categories.")
    categories = catalog["categories"]
    if not isinstance(categories, list) or not categories:
        raise CatalogError("categories debe ser una lista no vacía.")
    items = []
    category_ids = set()
    for index, category in enumerate(categories, 1):
        label = f"categories, categoría {index}"
        if not isinstance(category, dict) or set(category) != {"id", "name", "emoji", "items"}:
            raise CatalogError(f"{label}: se requieren únicamente id, name, emoji e items.")
        for field in ("id", "name", "emoji"):
            value = category[field]
            if not isinstance(value, str) or not value.strip():
                raise CatalogError(f"{label}: {field} debe ser texto no vacío.")
        category_id = category["id"]
        if not category_id.replace("-", "").replace("_", "").isalnum() or category_id in RESERVED_IDS:
            raise CatalogError(f"{label}: id '{category_id}' no válido o reservado.")
        if category_id in category_ids:
            raise CatalogError(f"{label}: id '{category_id}' duplicado.")
        category_ids.add(category_id)
        if not isinstance(category["items"], list) or not category["items"]:
            raise CatalogError(f"{label}: items debe ser una lista no vacía.")
        validate_catalog(category["items"], seen={item["id"] for item in items})
        items.extend(dict(item, categoryId=category_id, categoryName=category["name"],
                          categoryEmoji=category["emoji"]) for item in category["items"])
    return items


def validate_catalog(items, seen=None):
    if not isinstance(items, list) or not items:
        raise CatalogError("El catálogo debe ser una lista YAML con al menos un regalo.")
    seen = set() if seen is None else seen
    for index, item in enumerate(items, 1):
        label = f"Regalo {index}"
        if not isinstance(item, dict):
            raise CatalogError(f"{label}: cada elemento debe ser un mapa YAML.")
        missing = [field for field in FIELDS if field not in item]
        extra = [field for field in item if field not in FIELDS and field not in
                 ("categoryId", "categoryName", "categoryEmoji")]
        if missing or extra:
            raise CatalogError(f"{label}: campos requeridos faltantes: {missing}; no reconocidos: {extra}.")
        for field in ("id", "name", "subtitle", "store", "emoji", "glow", "tag", "url", "description", "note"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise CatalogError(f"{label}: {field} debe ser texto no vacío.")
        item_id = item["id"]
        if not item_id.replace("-", "").replace("_", "").isalnum() or item_id in RESERVED_IDS:
            raise CatalogError(f"{label}: id '{item_id}' no válido o reservado.")
        if item_id in seen:
            raise CatalogError(f"{label}: id '{item_id}' duplicado.")
        seen.add(item_id)
        if isinstance(item["price"], bool) or not isinstance(item["price"], (int, float)) or not math.isfinite(item["price"]) or item["price"] < 0:
            raise CatalogError(f"{label}: price debe ser un número finito no negativo.")
        if not isinstance(item["uses"], list) or not item["uses"] or any(not isinstance(use, str) or not use.strip() for use in item["uses"]):
            raise CatalogError(f"{label}: uses debe ser una lista no vacía de textos.")
        if not item["glow"].startswith("#") or len(item["glow"]) not in (4, 7) or any(c not in "0123456789abcdefABCDEF" for c in item["glow"][1:]):
            raise CatalogError(f"{label}: glow debe ser un color hexadecimal (#RGB o #RRGGBB).")
        parsed = urlparse(item["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise CatalogError(f"{label}: url debe ser una dirección HTTPS completa.")


def render_html(items, template):
    for placeholder in PLACEHOLDERS:
        if template.count(placeholder) != 1:
            raise CatalogError(f"La plantilla index.html debe contener exactamente una marca {placeholder}.")
    stores = list(dict.fromkeys(item["store"] for item in items))
    filters = ['<button class="chip active" data-filter="all">Todos</button>']
    filters.extend(
        f'<button class="chip" data-filter="{html.escape(store, quote=True)}">{html.escape(store)}</button>'
        for store in stores
    )
    # Escape HTML-significant characters so YAML cannot terminate the inline script.
    catalog_json = json.dumps(items, ensure_ascii=True, separators=(",", ":"))
    catalog_json = catalog_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    replacements = {
        PLACEHOLDERS[0]: "".join(filters),
        PLACEHOLDERS[1]: catalog_json,
    }
    marker_pattern = re.compile("|".join(re.escape(marker) for marker in PLACEHOLDERS))
    return marker_pattern.sub(lambda match: replacements[match.group(0)], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "catalogo.yaml")
    parser.add_argument("--template", type=Path, default=ROOT / "index.html")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        items = load_catalog(args.catalog)
        rendered = render_html(items, args.template.read_text(encoding="utf-8"))
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "index.html").write_text(rendered, encoding="utf-8")
    except (CatalogError, OSError) as exc:
        parser.error(str(exc))
    print(f"Generado {args.output / 'index.html'} ({len(items)} regalos)")


if __name__ == "__main__":
    main()
