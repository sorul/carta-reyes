# Cartas de Reyes

Sitio estático para mantener cartas de Reyes por año y persona. Cada perfil vive en `cartas/<año>/<persona>/` y contiene su propio `catalogo.yml` e `index.html`.

## Editar un perfil

Edita el catálogo del perfil elegido, agrupando los regalos bajo `categories`. Cada categoría declara `id`, `name`, `emoji` e `items`; cada artículo conserva sus campos (`id`, `name`, `subtitle`, `store`, `price`, `emoji`, `glow`, `tag`, `url`, `description`, `uses` y `note`). Para crear otra sección, agrega una categoría con un identificador único y mueve o agrega sus artículos en `items`:

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
3. Ejecuta `python3 -m unittest discover -s tests -v`.
4. Genera todos los perfiles completos y la portada con `make build-all`, o selecciona uno con `make build YEAR=2027 PERSONA=cayetano`.
5. Abre `dist/index.html` para elegir una carta. Cada perfil queda aislado en su ruta, por ejemplo `dist/2027/cayetano/index.html` o `dist/2027/laura/index.html`.

`make build-all` descubre las carpetas completas en `cartas/<año>/<persona>/` (con `catalogo.yml` e `index.html`), construye todas y las publica bajo sus rutas independientes. Un build seleccionado actualiza la portada con los perfiles que tienen fuentes completas y ya están generados; así no aparecen enlaces rotos, y builds seleccionados sucesivos van agregando perfiles. GitHub Pages usa `make build-all`, así que los perfiles nuevos no requieren cambios en el workflow.

El HTML generado es autónomo; el navegador no necesita cargar YAML ni ejecutar un backend.

## Sitio publicado

[https://sorul.github.io/carta-reyes/](https://sorul.github.io/carta-reyes/)

## Funcionalidades

- Diseño adaptable a móvil y escritorio.
- Categorías de regalos con navegación, conteos y filtros por tienda.
- Explicaciones interactivas y enlaces de compra.
- Marcar regalos como conseguidos, con persistencia local por navegador.
- Copiar la lista completa.
- Sin framework, backend ni dependencias en tiempo de ejecución; PyYAML solo se usa al generar el sitio.

## Nota

Los precios son orientativos y no incluyen envíos, impuestos ni eventuales cambios de divisas. Las marcas de «conseguido» se guardan únicamente en el navegador local, no se comparten entre dispositivos.
