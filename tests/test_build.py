import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("catalog_build", ROOT / "scripts" / "build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class CatalogBuildTests(unittest.TestCase):
    def test_existing_catalog_has_all_original_gifts(self):
        items = build.load_catalog(ROOT / "catalogo.yaml")
        self.assertEqual(
            [item["id"] for item in items],
            ["xiao", "expansion", "solder", "pins", "amp", "grove", "speaker",
             "breadboard", "jumpers", "components", "usb"],
        )
        self.assertEqual(len(items), 11)
        self.assertTrue(all(item["categoryName"] == "Inventos" for item in items))

    def test_added_and_removed_items_drive_filters_and_totals(self):
        items = build.load_catalog(ROOT / "catalogo.yaml")
        items = [items[0], dict(items[0], id="extra", name="Nuevo", store="Nueva tienda", price=1.25)]
        html = build.render_html(items, (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('data-filter="Nueva tienda"', html)
        self.assertIn("Nuevo", html)
        self.assertIn("items.length", html)
        self.assertNotIn('data-filter="Tiendatec"', html)

    def test_invalid_catalog_has_actionable_error(self):
        with self.assertRaisesRegex(build.CatalogError, "id.*reservado"):
            build.validate_catalog([dict(build.load_catalog(ROOT / "catalogo.yaml")[0], id="__proto__")])

    def test_duplicate_ids_and_nonfinite_prices_are_rejected(self):
        item = build.load_catalog(ROOT / "catalogo.yaml")[0]
        with self.assertRaisesRegex(build.CatalogError, "duplicado"):
            build.validate_catalog([item, dict(item)])
        with self.assertRaisesRegex(build.CatalogError, "finito"):
            build.validate_catalog([dict(item, price=float("nan"))])

    def test_invalid_url_and_color_are_rejected(self):
        item = build.load_catalog(ROOT / "catalogo.yaml")[0]
        with self.assertRaisesRegex(build.CatalogError, "HTTPS"):
            build.validate_catalog([dict(item, url="javascript:alert(1)")])
        with self.assertRaisesRegex(build.CatalogError, "color hexadecimal"):
            build.validate_catalog([dict(item, glow="red")])

    def test_yaml_text_is_not_interpreted_as_html_or_script(self):
        item = dict(build.load_catalog(ROOT / "catalogo.yaml")[0],
                    name="</script><script>alert(1)</script>")
        html = build.render_html([item], (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("\\u003c/script\\u003e", html)

    def test_catalog_values_matching_template_markers_are_preserved(self):
        item = dict(build.load_catalog(ROOT / "catalogo.yaml")[0],
                    store="__CATALOG_JSON__", name="<!-- STORE_FILTERS -->")
        rendered = build.render_html([item], (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('data-filter="__CATALOG_JSON__">__CATALOG_JSON__</button>', rendered)
        self.assertIn('"name":"\\u003c!-- STORE_FILTERS --\\u003e"', rendered)

    def test_categories_flatten_for_existing_gift_operations_and_render_navigation(self):
        gifts = build.load_catalog(ROOT / "catalogo.yaml")
        catalog = {
            "categories": [
                {"id": "inventions", "name": "Inventos", "emoji": "🧪", "items": gifts[:2]},
                {"id": "reading", "name": "Lecturas", "emoji": "📚", "items": [dict(gifts[2], id="book")]},
            ]
        }
        items = build.load_catalog_data(catalog)
        self.assertEqual([item["id"] for item in items], ["xiao", "expansion", "book"])
        self.assertEqual([item["categoryId"] for item in items], ["inventions", "inventions", "reading"])
        rendered = build.render_html(items, (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('"categoryId":"inventions"', rendered)
        self.assertIn('"categoryId":"reading"', rendered)
        self.assertIn("Inventos", rendered)
        self.assertIn("Lecturas", rendered)
        self.assertIn("section.dataset.category = category.id", rendered)
        self.assertIn("dataset.categoryCount", rendered)

    def test_malformed_categories_and_global_duplicate_ids_are_rejected(self):
        item = build.load_catalog(ROOT / "catalogo.yaml")[0]
        with self.assertRaisesRegex(build.CatalogError, "categories"):
            build.load_catalog_data({"categories": [{"id": "bad id", "name": "", "emoji": "🧪", "items": [item]}]})
        with self.assertRaisesRegex(build.CatalogError, "duplicado"):
            build.load_catalog_data({"categories": [
                {"id": "one", "name": "Uno", "emoji": "1️⃣", "items": [item]},
                {"id": "two", "name": "Dos", "emoji": "2️⃣", "items": [dict(item)]},
            ]})

    def test_category_store_filter_keeps_only_nonempty_groups(self):
        gifts = build.load_catalog(ROOT / "catalogo.yaml")
        items = build.load_catalog_data({"categories": [
            {"id": "first", "name": "Primero", "emoji": "🧪", "items": [gifts[0]]},
            {"id": "second", "name": "Segundo", "emoji": "📚", "items": [gifts[1]]},
        ]})
        rendered = build.render_html(items, (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn("filter === 'all'", rendered)
        self.assertIn("(filter === 'all' || item.store === filter)", rendered)
        self.assertIn("if (!categoryItems.length) return", rendered)


if __name__ == "__main__":
    unittest.main()
