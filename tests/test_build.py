import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAYETANO = ROOT / "cartas" / "2027" / "cayetano"
CATALOG = CAYETANO / "catalogo.yml"
TEMPLATE = CAYETANO / "index.html"
SPEC = importlib.util.spec_from_file_location("catalog_build", ROOT / "scripts" / "build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class CatalogBuildTests(unittest.TestCase):
    def test_budget_summary_uses_only_dynamic_catalog_total(self):
        items = build.load_catalog(CATALOG)
        rendered = build.render_html(items, TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn('class="stat-label">Total sin envío</span>', rendered)
        self.assertNotIn("Total con envíos aprox.", rendered)
        self.assertNotIn("110–130 €", rendered)
        self.assertNotIn('id="total">73 €', rendered)
        self.assertIn("items.reduce((sum, i) => sum + i.price, 0)", rendered)
        self.assertNotIn("visible.reduce((sum, i) => sum + i.price", rendered)

    def test_added_and_removed_items_drive_filters_and_totals(self):
        items = build.load_catalog(CATALOG)
        items = [items[0], dict(items[0], id="extra", name="Nuevo", store="Nueva tienda", price=1.25)]
        html = build.render_html(items, TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn('data-filter="Nueva tienda"', html)
        self.assertIn("Nuevo", html)
        self.assertIn("items.length", html)
        self.assertNotIn('data-filter="Tiendatec"', html)

    def test_invalid_catalog_has_actionable_error(self):
        with self.assertRaisesRegex(build.CatalogError, "id.*reservado"):
            build.validate_catalog([dict(build.load_catalog(CATALOG)[0], id="__proto__")])

    def test_duplicate_ids_and_nonfinite_prices_are_rejected(self):
        item = build.load_catalog(CATALOG)[0]
        with self.assertRaisesRegex(build.CatalogError, "duplicado"):
            build.validate_catalog([item, dict(item)])
        with self.assertRaisesRegex(build.CatalogError, "finito"):
            build.validate_catalog([dict(item, price=float("nan"))])

    def test_invalid_url_and_color_are_rejected(self):
        item = build.load_catalog(CATALOG)[0]
        with self.assertRaisesRegex(build.CatalogError, "HTTPS"):
            build.validate_catalog([dict(item, url="javascript:alert(1)")])
        with self.assertRaisesRegex(build.CatalogError, "url"):
            build.validate_catalog([dict(item, url="")])
        with self.assertRaisesRegex(build.CatalogError, "url"):
            build.validate_catalog([dict(item, url=42)])
        with self.assertRaisesRegex(build.CatalogError, "color hexadecimal"):
            build.validate_catalog([dict(item, glow="red")])

    def test_null_url_is_valid_and_shop_navigation_is_conditional_in_both_profiles(self):
        item = dict(build.load_catalog(CATALOG)[0], url=None)
        build.validate_catalog([item])

        for template_path in (TEMPLATE, ROOT / "cartas" / "2027" / "laura" / "index.html"):
            with self.subTest(profile=template_path.parent.name):
                rendered = build.render_html([item], template_path.read_text(encoding="utf-8"))
                self.assertIn("if (item.url)", rendered)
                self.assertIn('href = item.url', rendered)

        cayetano = build.render_html([item], TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("modalLink.hidden = !item.url", cayetano)
        self.assertIn("if (item.url) modalLink.href = item.url", cayetano)
        self.assertRegex(cayetano, r"#modal-link\[hidden\]\s*\{\s*display:\s*none")
        self.assertIn("i.url || 'Sin enlace de tienda'", cayetano)

    def test_yaml_text_is_not_interpreted_as_html_or_script(self):
        item = dict(build.load_catalog(CATALOG)[0],
                    name="</script><script>alert(1)</script>")
        html = build.render_html([item], TEMPLATE.read_text(encoding="utf-8"))
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("\\u003c/script\\u003e", html)

    def test_catalog_values_matching_template_markers_are_preserved(self):
        item = dict(build.load_catalog(CATALOG)[0],
                    store="__CATALOG_JSON__", name="<!-- STORE_FILTERS -->")
        rendered = build.render_html([item], TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn('data-filter="__CATALOG_JSON__">__CATALOG_JSON__</button>', rendered)
        self.assertIn('"name":"\\u003c!-- STORE_FILTERS --\\u003e"', rendered)

    def test_categories_flatten_for_existing_gift_operations_and_render_navigation(self):
        gifts = build.load_catalog(CATALOG)
        catalog = {
            "categories": [
                {"id": "inventions", "name": "Inventos", "emoji": "🧪", "items": gifts[:2]},
                {"id": "reading", "name": "Lecturas", "emoji": "📚", "items": [dict(gifts[2], id="book")]},
            ]
        }
        items = build.load_catalog_data(catalog)
        self.assertEqual([item["id"] for item in items], ["xiao", "expansion", "book"])
        self.assertEqual([item["categoryId"] for item in items], ["inventions", "inventions", "reading"])
        rendered = build.render_html(items, TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn('"categoryId":"inventions"', rendered)
        self.assertIn('"categoryId":"reading"', rendered)
        self.assertIn("Inventos", rendered)
        self.assertIn("Lecturas", rendered)
        self.assertIn("section.dataset.category = category.id", rendered)
        self.assertIn("dataset.categoryCount", rendered)

    def test_malformed_categories_and_global_duplicate_ids_are_rejected(self):
        item = build.load_catalog(CATALOG)[0]
        with self.assertRaisesRegex(build.CatalogError, "categories"):
            build.load_catalog_data({"categories": [{"id": "bad id", "name": "", "emoji": "🧪", "items": [item]}]})
        with self.assertRaisesRegex(build.CatalogError, "duplicado"):
            build.load_catalog_data({"categories": [
                {"id": "one", "name": "Uno", "emoji": "1️⃣", "items": [item]},
                {"id": "two", "name": "Dos", "emoji": "2️⃣", "items": [dict(item)]},
            ]})

    def test_category_store_filter_keeps_only_nonempty_groups(self):
        gifts = build.load_catalog(CATALOG)
        items = build.load_catalog_data({"categories": [
            {"id": "first", "name": "Primero", "emoji": "🧪", "items": [gifts[0]]},
            {"id": "second", "name": "Segundo", "emoji": "📚", "items": [gifts[1]]},
        ]})
        rendered = build.render_html(items, TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("filter === 'all'", rendered)
        self.assertIn("(filter === 'all' || item.store === filter)", rendered)
        self.assertIn("if (!categoryItems.length) return", rendered)

    def test_profile_selection_rejects_missing_or_invalid_selectors(self):
        with self.assertRaisesRegex(build.CatalogError, "YEAR"):
            build.profile_paths(None, "cayetano")
        with self.assertRaisesRegex(build.CatalogError, "PERSONA"):
            build.profile_paths("2027", None)
        with self.assertRaisesRegex(build.CatalogError, "YEAR"):
            build.profile_paths("../2027", "cayetano")
        with self.assertRaisesRegex(build.CatalogError, "PERSONA"):
            build.profile_paths("2027", "../cayetano")

    def test_build_profiles_use_distinct_routes_and_scoped_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            cayetano_output = build.build_profile("2027", "cayetano", output_root)
            laura_output = build.build_profile("2027", "laura", output_root)
            self.assertEqual(cayetano_output, output_root / "2027" / "cayetano")
            self.assertEqual(laura_output, output_root / "2027" / "laura")
            self.assertTrue((cayetano_output / "index.html").is_file())
            self.assertTrue((laura_output / "index.html").is_file())
            self.assertIn("carta-reyes:2027:cayetano", (cayetano_output / "index.html").read_text())
            self.assertIn("carta-reyes:2027:laura", (laura_output / "index.html").read_text())
            self.assertNotEqual(cayetano_output, laura_output)

    def test_discovery_includes_only_complete_profiles_in_sorted_order(self):
        with tempfile.TemporaryDirectory() as directory:
            profile_root = Path(directory)
            for year, persona, complete in (
                ("2028", "zoe", True),
                ("2027", "ana", True),
                ("2027", "partial", False),
            ):
                folder = profile_root / "cartas" / year / persona
                folder.mkdir(parents=True)
                (folder / "catalogo.yml").write_text("categories: []", encoding="utf-8")
                if complete:
                    (folder / "index.html").write_text("template", encoding="utf-8")

            self.assertEqual(
                build.discover_profiles(profile_root),
                [("2027", "ana"), ("2028", "zoe")],
            )

    def test_build_all_generates_each_profile_and_relative_root_links(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "dist"
            profiles = build.build_all(output_root=output_root)
            landing_page = (output_root / "index.html").read_text(encoding="utf-8")

            self.assertEqual(profiles, [("2027", "cayetano"), ("2027", "laura")])
            self.assertTrue((output_root / "2027" / "cayetano" / "index.html").is_file())
            self.assertTrue((output_root / "2027" / "laura" / "index.html").is_file())
            self.assertIn('href="./2027/cayetano/"', landing_page)
            self.assertIn('href="./2027/laura/"', landing_page)

    def test_selected_profile_build_refreshes_root_landing_page(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "dist"
            build.build_profile("2027", "laura", output_root)
            landing_page = (output_root / "index.html").read_text(encoding="utf-8")

            self.assertIn('href="./2027/laura/"', landing_page)
            self.assertNotIn('href="./2027/cayetano/"', landing_page)

            build.build_profile("2027", "cayetano", output_root)
            landing_page = (output_root / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="./2027/cayetano/"', landing_page)
            self.assertIn('href="./2027/laura/"', landing_page)

    def test_laura_profile_is_reduced_and_visibly_distinct(self):
        laura = ROOT / "cartas" / "2027" / "laura"
        items = build.load_catalog(laura / "catalogo.yml")
        cayetano_items = build.load_catalog(CATALOG)
        template = (laura / "index.html").read_text(encoding="utf-8")
        self.assertLess(len(items), len(cayetano_items))
        self.assertIn('aria-label="Tres Reyes Magos"', template)
        self.assertIn('#4D2E4D', template)
        self.assertNotIn("Para Cayetano", template)


if __name__ == "__main__":
    unittest.main()
