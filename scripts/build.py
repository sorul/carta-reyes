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
PROFILE_YEAR = re.compile(r"^\d{4}$")
PROFILE_PERSON = re.compile(r"^[a-z][a-z0-9-]*$")
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
        for field in ("id", "name", "subtitle", "store", "emoji", "glow", "tag", "description", "note"):
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
        if item["url"] is not None:
            if not isinstance(item["url"], str) or not item["url"].strip():
                raise CatalogError(f"{label}: url debe ser null o una dirección HTTPS completa.")
            parsed = urlparse(item["url"])
            if parsed.scheme != "https" or not parsed.netloc:
                raise CatalogError(f"{label}: url debe ser null o una dirección HTTPS completa.")


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


def profile_paths(year, persona, profile_root=ROOT):
    """Resolve a year/person profile without allowing path traversal."""
    if not isinstance(year, str) or not PROFILE_YEAR.fullmatch(year):
        raise CatalogError("YEAR debe ser un año de cuatro cifras, por ejemplo 2027.")
    if not isinstance(persona, str) or not PROFILE_PERSON.fullmatch(persona):
        raise CatalogError("PERSONA debe ser un identificador en minúsculas, por ejemplo cayetano.")
    profile = Path(profile_root) / "cartas" / year / persona
    catalog = profile / "catalogo.yml"
    template = profile / "index.html"
    if not catalog.is_file() or not template.is_file():
        raise CatalogError(f"No existe el perfil cartas/{year}/{persona} (se requieren catalogo.yml e index.html).")
    return catalog, template


def discover_profiles(profile_root=ROOT):
    """Return sorted (year, persona) pairs for complete profile directories."""
    profiles = []
    cartas = Path(profile_root) / "cartas"
    if not cartas.is_dir():
        return profiles
    for year_dir in cartas.iterdir():
        if not year_dir.is_dir() or not PROFILE_YEAR.fullmatch(year_dir.name):
            continue
        for persona_dir in year_dir.iterdir():
            if (persona_dir.is_dir() and PROFILE_PERSON.fullmatch(persona_dir.name)
                    and (persona_dir / "catalogo.yml").is_file()
                    and (persona_dir / "index.html").is_file()):
                profiles.append((year_dir.name, persona_dir.name))
    return sorted(profiles)


def render_landing_page(profiles):
    """Render a welcoming top-level directory of available letters."""
    links = "\n".join(
        f'<li><a class="letter-card" href="./{html.escape(year, quote=True)}/{html.escape(persona, quote=True)}/">'
        f'<span class="letter-icon" aria-hidden="true">🎁</span>'
        f'<span class="letter-copy"><strong>{html.escape(persona.replace("-", " ").title())}</strong>'
        f'<small>Carta de Reyes · {html.escape(year)}</small></span>'
        f'<span class="letter-arrow" aria-hidden="true">↗</span></a></li>'
        for year, persona in profiles
    )
    return f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#182a38">
  <meta name="description" content="Elige una carta de Reyes y descubre sus ideas de regalos.">
  <title>Cartas de Reyes</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #24343d;
      background: #f5f1e8;
      font-synthesis: none;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      min-height: 100vh;
      margin: 0;
      background:
        radial-gradient(ellipse at 14% 8%, rgb(239 199 124 / 32%), transparent 32rem),
        radial-gradient(ellipse at 92% 42%, rgb(162 213 191 / 24%), transparent 28rem),
        #f5f1e8;
    }}
    .page {{ width: min(100% - 2rem, 48rem); margin: 0 auto; padding: 4rem 0 5rem; }}
    .hero {{
      position: relative;
      overflow: hidden;
      padding: clamp(2rem, 7vw, 4rem);
      border: 1px solid rgb(255 255 255 / 14%);
      border-radius: 2rem;
      color: #faf0db;
      background: linear-gradient(135deg, #182a38, #29424b 72%, #36534e);
      box-shadow: 0 1.5rem 3.5rem rgb(24 42 56 / 16%);
    }}
    .hero::after {{
      position: absolute;
      right: -2rem;
      bottom: -5.5rem;
      width: 14rem;
      height: 14rem;
      border: 1px solid rgb(239 199 124 / 32%);
      border-radius: 50%;
      box-shadow: 0 0 0 1.5rem rgb(239 199 124 / 7%), 0 0 0 3rem rgb(239 199 124 / 5%);
      content: "";
    }}
    .eyebrow {{
      margin: 0 0 1rem;
      color: #efc77c;
      font-size: .75rem;
      font-weight: 750;
      letter-spacing: .18em;
      text-transform: uppercase;
    }}
    h1 {{ max-width: 12ch; margin: 0; font-family: Georgia, serif; font-size: clamp(2.6rem, 8vw, 4.6rem); font-weight: 500; line-height: .98; letter-spacing: -.045em; }}
    .intro {{ max-width: 34rem; margin: 1.5rem 0 0; color: #d5dfd9; font-size: 1rem; line-height: 1.7; }}
    .section-heading {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: 2.5rem .25rem 1rem; }}
    .section-heading h2 {{ margin: 0; font-family: Georgia, serif; font-size: 1.65rem; font-weight: 500; }}
    .section-heading span {{ color: #64747b; font-size: .85rem; }}
    .letters {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr)); gap: .9rem; margin: 0; padding: 0; list-style: none; }}
    .letter-card {{
      display: flex;
      min-height: 6.5rem;
      align-items: center;
      gap: 1rem;
      padding: 1.1rem 1.25rem;
      border: 1px solid #e5ddce;
      border-radius: 1.25rem;
      color: inherit;
      background: rgb(255 253 248 / 86%);
      box-shadow: 0 .5rem 1.4rem rgb(24 42 56 / 5%);
      text-decoration: none;
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}
    .letter-card:hover {{ transform: translateY(-3px); border-color: #c8a365; box-shadow: 0 .9rem 1.8rem rgb(24 42 56 / 10%); }}
    .letter-card:focus-visible {{ outline: 3px solid #b78338; outline-offset: 4px; }}
    .letter-icon {{ display: grid; width: 3.25rem; height: 3.25rem; flex: 0 0 auto; place-items: center; border-radius: 1rem; background: #f4e8cb; font-size: 1.5rem; }}
    .letter-copy {{ display: grid; gap: .2rem; }}
    .letter-copy strong {{ font-size: 1.05rem; }}
    .letter-copy small {{ color: #68787d; font-size: .85rem; }}
    .letter-arrow {{ margin-left: auto; color: #9b722f; font-size: 1.25rem; }}
    footer {{ margin-top: 2rem; color: #68787d; font-size: .8rem; text-align: center; }}
    @media (prefers-reduced-motion: reduce) {{ .letter-card {{ transition: none; }} }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <p class="eyebrow">✨ Una tradición, muchas ilusiones</p>
      <h1>Cartas de Reyes</h1>
      <p class="intro">Elige una carta para ver sus ideas de regalos.</p>
    </header>
    <main>
      <div class="section-heading"><h2>Elige tu carta</h2><span>{len(profiles)} disponibles</span></div>
      <ul class="letters">
{links}
      </ul>
    </main>
    <footer>Hecho con ilusión ✦</footer>
  </div>
</body>
</html>
'''


def write_landing_page(profiles, output_root=None):
    output = Path(output_root) if output_root is not None else ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render_landing_page(profiles), encoding="utf-8")


def build_profile(year, persona, output_root=None, profile_root=ROOT, refresh_landing=True):
    catalog_path, template_path = profile_paths(year, persona, profile_root)
    items = load_catalog(catalog_path)
    rendered = render_html(items, template_path.read_text(encoding="utf-8"))
    output = Path(output_root) if output_root is not None else ROOT / "dist"
    output = output / year / persona
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(rendered, encoding="utf-8")
    if refresh_landing:
        generated_profiles = [
            (available_year, available_persona)
            for available_year, available_persona in discover_profiles(profile_root)
            if (Path(output_root) if output_root is not None else ROOT / "dist")
            .joinpath(available_year, available_persona, "index.html").is_file()
        ]
        write_landing_page(generated_profiles, output_root)
    return output


def build_all(profile_root=ROOT, output_root=None):
    """Build every complete source profile and the root landing page."""
    profiles = discover_profiles(profile_root)
    if not profiles:
        raise CatalogError("No se encontraron perfiles completos en cartas/<año>/<persona>/.")
    for year, persona in profiles:
        build_profile(year, persona, output_root, profile_root, refresh_landing=False)
    write_landing_page(profiles, output_root)
    return profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Construir todos los perfiles completos.")
    selection.add_argument("--year", help="Año del perfil, por ejemplo 2027.")
    parser.add_argument("--persona", help="Persona del perfil, por ejemplo cayetano.")
    args = parser.parse_args()
    if not args.all and not args.persona:
        parser.error("--persona es obligatorio al usar --year.")
    try:
        if args.all:
            profiles = build_all()
            for year, persona in profiles:
                items = load_catalog(profile_paths(year, persona)[0])
                print(f"Generado {ROOT / 'dist' / year / persona / 'index.html'} ({len(items)} regalos)")
            print(f"Generada {ROOT / 'dist' / 'index.html'} ({len(profiles)} perfiles)")
            return
        output = build_profile(args.year, args.persona)
        items = load_catalog(profile_paths(args.year, args.persona)[0])
    except (CatalogError, OSError) as exc:
        parser.error(str(exc))
    print(f"Generado {output / 'index.html'} ({len(items)} regalos)")


if __name__ == "__main__":
    main()
