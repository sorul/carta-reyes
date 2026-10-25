const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const profiles = ['cayetano', 'laura'];
const fixtures = [
  { id: 'book', name: 'Libro', subtitle: 'Leer juntas', price: 12, store: 'Tienda A', url: 'https://example.test/book', emoji: '📚', categoryId: 'ideas', categoryName: 'Ideas', categoryEmoji: '✨', glow: '#ff0000', tag: 'Lectura', description: 'Un libro especial.', uses: ['Leer historias'], note: 'Para compartir.' },
  { id: 'game', name: 'Juego', subtitle: 'Jugar juntas', price: 8.5, store: 'Tienda B', url: null, emoji: '🎲', categoryId: 'ideas', categoryName: 'Ideas', categoryEmoji: '✨', glow: '#00ff00', tag: 'Juego', description: 'Un juego bonito.', uses: ['Jugar en familia'], note: 'Sin enlace.' },
  { id: 'paint', name: 'Pinturas', subtitle: 'Crear juntas', price: 5, store: 'Tienda A', url: 'https://example.test/paint', emoji: '🎨', categoryId: 'crear', categoryName: 'Crear', categoryEmoji: '🎨', glow: '#0000ff', tag: 'Arte', description: 'Pinturas lavables.', uses: ['Pintar'], note: 'Fáciles de limpiar.' },
];

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.style = { properties: new Map(), setProperty(name, value) { this.properties.set(name, value); } };
    this.attributes = {}; this.listeners = {}; this.className = ''; this.hidden = false; this.checked = false;
    this.classList = { add: name => { this.className = `${this.className} ${name}`.trim(); }, remove: name => { this.className = this.className.split(' ').filter(x => x !== name).join(' '); }, toggle: (name, force) => { if (force) this.classList.add(name); else this.classList.remove(name); } };
  }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  async fire(name, event = {}) { for (const fn of this.listeners[name] || []) await fn({ target: this, ...event }); }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; if (name === 'href') this._href = ''; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  closest(selector) { return selector === 'button[data-filter]' && this.tagName === 'BUTTON' && this.dataset.filter ? this : null; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text || this.children.map(child => child.textContent || '').join(''); }
  set href(value) { this._href = String(value); this.attributes.href = String(value); }
  get href() { return this._href || ''; }
}

function runProfile(profile, clipboardFailure = false) {
  const html = fs.readFileSync(path.join(root, `cartas/2027/${profile}/index.html`), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1].replace('__CATALOG_JSON__', JSON.stringify(fixtures));
  const selectors = ['#gifts', '#count', '.filters', '#category-nav', '#category-groups', '#filter-status', '#total', '#details', '#modal-store', '#modal-title', '#modal-emoji', '#modal-description', '#modal-uses', '#modal-link', '#modal-done', '#close', '#copy', '#toast'];
  const elements = new Map(selectors.map(selector => [selector, new Element(selector.startsWith('#') ? 'div' : 'nav')]));
  const toastAttributes = html.match(/<[^>]*id="toast"[^>]*>/)?.[0] || '';
  const toastRole = toastAttributes.match(/role="([^"]+)"/)?.[1];
  const toastLive = toastAttributes.match(/aria-live="([^"]+)"/)?.[1];
  if (toastRole) elements.get('#toast').setAttribute('role', toastRole);
  if (toastLive) elements.get('#toast').setAttribute('aria-live', toastLive);
  const groupsAttributes = html.match(/<[^>]*id="category-groups"[^>]*>/)?.[0] || '';
  const groupsLive = groupsAttributes.match(/aria-live="([^"]+)"/)?.[1];
  if (groupsLive) elements.get('#category-groups').setAttribute('aria-live', groupsLive);
  const statusAttributes = html.match(/<[^>]*id="filter-status"[^>]*>/)?.[0] || '';
  for (const attribute of ['role', 'aria-atomic', 'aria-live']) {
    const value = statusAttributes.match(new RegExp(`${attribute}="([^"]+)"`))?.[1];
    if (value) elements.get('#filter-status').setAttribute(attribute, value);
  }
  for (const filter of ['all', 'Tienda A', 'Tienda B', 'Tienda C']) { const button = new Element('button'); button.dataset.filter = filter; button.className = 'chip'; elements.get('.filters').append(button); }
  const document = {
    querySelector: selector => elements.get(selector) || new Element(),
    querySelectorAll: selector => selector === '.chip' ? elements.get('.filters').children : [],
    createElement: tag => new Element(tag), createTextNode: text => ({ textContent: text }),
  };
  const saved = new Map(); let copied = '';
  const context = { document, localStorage: { getItem: key => saved.get(key) || null, setItem: (key, val) => saved.set(key, val) },
    navigator: { clipboard: { writeText: async text => { if (clipboardFailure) throw new Error('denied'); copied = text; } } },
    Intl, Set, JSON, String, clearTimeout, setTimeout: () => 1, console };
  vm.runInNewContext(script, context);
  return { elements, saved, context, copied: () => copied };
}

test('Laura template exposes the same interactive catalog behavior as Cayetano', async () => {
  for (const profile of profiles) {
    const ui = runProfile(profile);
    const groups = ui.elements.get('#category-groups');
    assert.equal(groups.children.length, 2, `${profile}: categories group fixture items`);
    assert.match(ui.elements.get('#count').textContent, /^3 (?:regalos|ideas)$/, `${profile}: full catalog count`);
    assert.match(ui.elements.get('#total').textContent, /25,50|25\.50/, `${profile}: full catalog total`);
    assert.equal(ui.elements.get('#category-nav').children.length, 2);
    await ui.elements.get('.filters').children[2].fire('click');
    assert.equal(groups.children.length, 1, `${profile}: empty category is omitted after filtering`);
    assert.match(groups.children[0].textContent, /1 (?:regalo|idea)/);
  }
});

test('both profiles apply each catalog item glow to its rendered visual', () => {
  for (const profile of profiles) {
    const ui = runProfile(profile);
    const cards = findAll(ui.elements.get('#category-groups'), node => node.tagName === 'ARTICLE');
    assert.equal(cards.length, fixtures.length, `${profile}: every fixture item renders a card`);
    cards.forEach((card, index) => {
      const glowTarget = find(card, node => node.style?.properties?.has('--glow'));
      assert.ok(glowTarget, `${profile}: ${fixtures[index].id} has a glow visual`);
      assert.equal(glowTarget.style.properties.get('--glow'), fixtures[index].glow, `${profile}: ${fixtures[index].id} uses its own glow color`);
    });
  }
});

test('Laura template supports details, obtained state, null URLs, and clipboard feedback', async () => {
  for (const profile of profiles) {
    const ui = runProfile(profile);
    const card = ui.elements.get('#category-groups').children[0].children.find(child => child.className === 'cards').children[0];
    const detailButton = find(card, node => node.tagName === 'BUTTON' && node.textContent === '¿Para qué sirve?');
    await detailButton.fire('click');
    assert.equal(ui.elements.get('#modal-description').textContent, fixtures[0].description);
    assert.match(ui.elements.get('#modal-uses').textContent, /Para compartir/);
    await ui.elements.get('#modal-done').fire('click');
    assert.equal([...ui.saved.keys()][0], `carta-reyes:2027:${profile}:conseguidos`);
    assert.deepEqual(JSON.parse([...ui.saved.values()][0]), ['book']);
    assert.match(ui.elements.get('#category-groups').children[0].textContent, /Ya está conseguido|Desmarcar conseguido/);
    const modalLink = ui.elements.get('#modal-link');
    const nullCard = ui.elements.get('#category-groups').children[0].children.find(child => child.className === 'cards').children[1];
    const nullDetail = find(nullCard, node => node.tagName === 'BUTTON' && node.textContent === '¿Para qué sirve?');
    await nullDetail.fire('click');
    assert.equal(modalLink.hidden, true, `${profile}: null URL hides modal shop control`);
    assert.equal(modalLink.href, '', `${profile}: null URL clears stale shop URL`);
    assert.equal(findAll(nullCard, node => node.tagName === 'A').length, 0, `${profile}: no shop control for null URL`);
    assert.match(nullCard.textContent, /¿Para qué sirve\?/);
    await ui.elements.get('#copy').fire('click');
    assert.match(ui.copied(), /Sin enlace de tienda/);
    assert.doesNotMatch(ui.copied(), /null/);
    assert.match(ui.elements.get('#toast').textContent, /copiada/i);
  }
});

test('clipboard failure is announced accessibly for both profiles', async () => {
  for (const profile of profiles) {
    const ui = runProfile(profile, true);
    await ui.elements.get('#copy').fire('click');
    assert.match(ui.elements.get('#toast').textContent, /No se pudo copiar/i);
    assert.equal(ui.elements.get('#toast').getAttribute('role'), 'status');
    assert.equal(ui.elements.get('#toast').getAttribute('aria-live'), 'polite');
  }
});

test('filter status announces only user-selected store result changes', async () => {
  for (const profile of profiles) {
    const ui = runProfile(profile);
    const html = fs.readFileSync(path.join(root, `cartas/2027/${profile}/index.html`), 'utf8');
    const status = ui.elements.get('#filter-status');
    const buttons = ui.elements.get('.filters').children;
    assert.equal(status.textContent, '', `${profile}: status starts empty`);
    assert.equal(status.getAttribute('role'), 'status', `${profile}: status is an accessible status region`);
    assert.equal(status.getAttribute('aria-atomic'), 'true', `${profile}: the announcement is atomic`);
    assert.equal(ui.elements.get('#category-groups').getAttribute('aria-live'), null, `${profile}: catalog rerenders are quiet`);
    const statusElement = html.match(/<[^>]*id="filter-status"[^>]*>/)?.[0] || '';
    assert.match(statusElement, /class="visually-hidden"/, `${profile}: status is visually hidden without being removed from accessibility`);
    assert.match(statusElement, /aria-atomic="true"/);
    assert.match(html, /class="(?:filters|filterbar)" role="group" aria-label="Filtrar por tienda"/, `${profile}: store filters are grouped controls`);
    const visuallyHiddenCss = html.match(/\.visually-hidden\s*\{([^}]*)\}/)?.[1] || '';
    assert.match(visuallyHiddenCss, /position:\s*absolute/i);
    assert.doesNotMatch(visuallyHiddenCss, /display:\s*none|visibility:\s*hidden/i);

    await buttons[1].fire('click');
    assert.equal(status.textContent, 'Se muestran 2 regalos de Tienda A.');
    await buttons[1].fire('click');
    assert.equal(status.textContent, 'Se muestran 2 regalos de Tienda A.', `${profile}: same-filter clicks do not announce again`);
    await buttons[2].fire('click');
    assert.equal(status.textContent, 'Se muestra 1 regalo de Tienda B.');
    const beforeObtainedToggle = status.textContent;
    const card = ui.elements.get('#category-groups').children[0].children.find(child => child.className === 'cards').children[0];
    const checkbox = find(card, node => node.tagName === 'INPUT');
    await checkbox.fire('change', { target: { checked: true } });
    assert.equal(status.textContent, beforeObtainedToggle, `${profile}: obtained-state rerenders do not announce`);
    await buttons[3].fire('click');
    assert.equal(status.textContent, 'No hay regalos de Tienda C.');
    await buttons[0].fire('click');
    assert.equal(status.textContent, 'Se muestran 3 regalos en todas las tiendas.');
  }
});

test('Laura preserves reduced-motion support', () => {
  const html = fs.readFileSync(path.join(root, 'cartas/2027/laura/index.html'), 'utf8');
  const reducedMotion = html.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)([\s\S]*?)<\/style>/)?.[1] || '';
  assert.match(reducedMotion, /transition:\s*none\s*!important/i);
  assert.match(reducedMotion, /animation:\s*none\s*!important/i);
});

function find(rootNode, predicate) { return findAll(rootNode, predicate)[0]; }
function findAll(rootNode, predicate) { return [ ...(predicate(rootNode) ? [rootNode] : []), ...rootNode.children.flatMap(child => child.children ? findAll(child, predicate) : []) ]; }
