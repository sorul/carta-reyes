# Carta de Reyes 2027

Web estática para compartir una carta de Reyes de electrónica con Laura.

## Editar el catálogo

Los regalos se mantienen en `catalogo.yaml`, agrupados bajo `categories`. Cada categoría declara `id`, `name`, `emoji` e `items`; cada artículo conserva sus campos (`id`, `name`, `subtitle`, `store`, `price`, `emoji`, `glow`, `tag`, `url`, `description`, `uses` y `note`). Para crear otra sección, agrega una categoría con un identificador único y mueve o agrega sus artículos en `items`:

```yaml
categories:
  - id: inventos
    name: Inventos
    emoji: 🧪
    items:
      - id: placa
        name: Placa de ejemplo
        # Completa aquí los demás campos requeridos del artículo.
```

Los IDs de regalos deben ser únicos en todo el catálogo, incluso entre categorías. Los IDs de categoría también deben ser únicos; el precio debe ser un número no negativo. El filtro por tienda se genera a partir de los artículos. La página agrupa las tarjetas y ajusta los conteos al filtrar; las marcas de «conseguido» siguen asociadas al ID de cada regalo.

## Construir y previsualizar

1. Instala Python 3.12 o posterior.
2. Instala la dependencia fijada: `python3 -m pip install -r requirements.txt`.
3. Ejecuta `python3 -m unittest discover -s tests -v` y `python3 scripts/build.py`.
4. Abre `dist/index.html` en un navegador para revisar el sitio generado.

El HTML generado es autónomo y puede publicarse bajo una ruta de repositorio de GitHub Pages. El navegador no necesita cargar YAML ni ejecutar un backend.

## Publicar en GitHub Pages

1. Crea un repositorio público llamado `carta-reyes-2027`.
2. Sube los archivos fuente (`index.html`, `catalogo.yaml`, `scripts/`, `tests/`, `requirements.txt` y `.github/workflows/pages.yml`) a la rama actual `master` o a `main`.
3. En GitHub abre **Settings > Pages**.
4. En **Build and deployment**, selecciona **GitHub Actions** como origen.
5. El workflow ejecuta las pruebas, genera `dist/` y publica ese artefacto al hacer push a `master` o `main`.
6. La URL tendrá el formato `https://USUARIO.github.io/carta-reyes-2027/`.

## Funcionalidades

- Diseño adaptable a móvil y escritorio.
- Categorías de regalos con navegación, conteos y filtros por tienda.
- Explicaciones interactivas y enlaces de compra.
- Marcar regalos como conseguidos, con persistencia local por navegador.
- Copiar la lista completa.
- Sin framework, backend ni dependencias en tiempo de ejecución; PyYAML solo se usa al generar el sitio.

## Nota

Los precios son orientativos y no incluyen envíos, impuestos ni eventuales cambios de divisas. Las marcas de «conseguido» se guardan únicamente en el navegador local, no se comparten entre dispositivos.
