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

test('both profiles render gift cards with stable ordinal, store, body, and split actions', async () => {
  for (const profile of profiles) {
    const ui = runProfile(profile);
    const cardsIn = groups => findAll(groups, node => node.tagName === 'ARTICLE');
    const assertCard = (card, index) => {
      const art = find(card, node => node.className === 'art');
      assert.ok(art, `${profile}: card ${index + 1} has an art panel`);
      assert.equal(art.style.properties.get('--glow'), fixtures[index].glow);
      assert.equal(find(art, node => node.className === 'number')?.textContent, `REGALO Nº ${String(index + 1).padStart(2, '0')}`);
      assert.equal(find(art, node => node.className === 'category')?.textContent, fixtures[index].store);
      assert.equal(find(art, node => node.className === 'emoji')?.textContent, fixtures[index].emoji);
      const body = find(card, node => node.className === 'card-body');
      assert.ok(body, `${profile}: card ${index + 1} has a body`);
      assert.equal(find(body, node => node.tagName === 'H4' || node.tagName === 'H3')?.textContent, fixtures[index].name);
      assert.equal(find(body, node => node.className === 'desc')?.textContent, `${fixtures[index].subtitle} · ${fixtures[index].description.split('.')[0]}.`);
      assert.match(find(body, node => node.className === 'price')?.textContent || '', /\d+,\d{2}.*€/u);
      assert.equal(find(body, node => node.className === 'tag')?.textContent, fixtures[index].tag);
      const links = find(body, node => node.className === 'card-links');
      assert.ok(links, `${profile}: card ${index + 1} has split actions`);
      assert.equal(links.children.filter(node => node.tagName === 'BUTTON').length, 1);
      assert.equal(links.children.filter(node => node.tagName === 'A').length, fixtures[index].url ? 1 : 0);
      assert.match(links.children.find(node => node.tagName === 'BUTTON').className, /details-btn/);
      if (fixtures[index].url) {
        const shop = links.children.find(node => node.tagName === 'A');
        assert.match(shop.className, /shop-btn|primary/);
        assert.equal(shop.href, fixtures[index].url);
        assert.equal(shop.target, '_blank');
        assert.equal(shop.rel, 'noopener noreferrer');
      }
      assert.ok(find(body, node => node.className === 'bought'), `${profile}: card ${index + 1} has an obtained control`);
    };

    cardsIn(ui.elements.get('#category-groups')).forEach(assertCard);
    await ui.elements.get('.filters').children[2].fire('click');
    const filteredCards = cardsIn(ui.elements.get('#category-groups'));
    assert.equal(filteredCards.length, 1);
    assertCard(filteredCards[0], 1);
  }
});

test('Laura card grid keeps the reference 3/2/1 responsive breakpoints', () => {
  const html = fs.readFileSync(path.join(root, 'cartas/2027/laura/index.html'), 'utf8');
  assert.match(html, /\.cards\s*\{[^}]*grid-template-columns:\s*repeat\(3,/s);
  assert.match(html, /@media\s*\(max-width:\s*850px\)[\s\S]*?\.cards\s*\{[^}]*grid-template-columns:\s*repeat\(2,/);
  assert.match(html, /@media\s*\(max-width:\s*580px\)[\s\S]*?\.cards\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(html, /@media\s*\(max-width:\s*580px\)(?:(?!@media)[\s\S])*?\.art\s*\{\s*height:\s*180px;\s*\}/);
});

test('Laura topbar and hero match the reference with three accessible kings', () => {
  const html = fs.readFileSync(path.join(root, 'cartas/2027/laura/index.html'), 'utf8');
  assert.match(html, /<header class="topbar">[\s\S]*?Carta de Reyes[\s\S]*?Edición\s*2027[\s\S]*?Ver regalos ↓/);
  assert.match(html, /✦ Queridos Reyes Magos \(y Laura\) ✦/);
  assert.match(html, /<h1 id="hero-title">Este año quiero <em>crear magia\.<\/em><\/h1>/);
  const description = html.match(/<section class="hero"[^>]*>[\s\S]*?<p>([\s\S]*?)<\/p>/)?.[1] || '';
  const normalizedDescription = description.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  assert.equal(normalizedDescription, 'O, para ser más exactos, construir una cámara que reconozca objetos y un pequeño asistente con inteligencia artificial. Esta es mi lista de piezas para convertir la idea en realidad. 🎄 También he pedido libros y juegos: no todo en la vida es crear; también hay espacio para jugar. 🎲');
  assert.doesNotMatch(html, /#proyectos|¿Qué voy a construir\?|🤖|Robot simpático|🎅🏻|🧔🏽‍♂️/);
  assert.equal((html.match(/<span class="king-group" role="img" aria-label="Tres Reyes Magos">/g) || []).length, 1);
  const kings = html.match(/<span class="king (?:melchior|gaspar|balthazar)" aria-hidden="true">/g) || [];
  assert.equal(kings.length, 3, 'exactly three decorative portrait wrappers');
  const portrait = name => html.match(new RegExp(`<span class="king ${name}" aria-hidden="true">([\\s\\S]*?)<\\/span><\\/span>`))?.[1] || '';
  assert.match(portrait('melchior'), /class="king-face" aria-hidden="true">🧔🏼‍♂️<\/span>[\s\S]*class="king-crown" aria-hidden="true">👑$/);
  assert.match(portrait('gaspar'), /class="king-face" aria-hidden="true">🧔‍♂️<\/span>[\s\S]*class="king-crown" aria-hidden="true">👑$/);
  assert.match(portrait('balthazar'), /class="king-face" aria-hidden="true">👳🏿‍♂️$/);
  assert.doesNotMatch(portrait('balthazar'), /king-crown/);
  assert.equal((html.match(/class="king-crown"/g) || []).length, 2, 'Melchior and Gaspar retain their crowns');
  const marks = html.match(/<span class="(?:king-face|king-crown)" aria-hidden="true">[^<]+<\/span>/g) || [];
  assert.equal(marks.length, 5, 'all five visual emoji marks are hidden from assistive technology');
  assert.doesNotMatch(html, /melchior-face|clip-path:\s*inset\(24%/);
  assert.match(html, /\.king\s*\{[^}]*display:\s*grid[^}]*grid-template-rows:\s*\.42em \.88em[^}]*height:\s*1\.3em/s);
  assert.doesNotMatch(html, /\.king-crown\s*\{[^}]*position:\s*absolute/);
  assert.match(html, /\.king-face\s*\{[^}]*grid-row:\s*2/);
  assert.match(html, /\.king-crown\s*\{[^}]*grid-row:\s*1[^}]*font-size:\s*\.6em[^}]*align-self:\s*end[^}]*z-index:\s*1/);
  assert.match(html, /\.king-crown\s*\{[^}]*transform:\s*translateY\(\.12em\)/);
  assert.ok(.12 < .18, 'crown overlap remains below the upper-face limit');
  assert.match(html, /\.king-group\s*\{[^}]*transform:\s*translateY\(16px\)/);
  assert.match(html, /\.king-face\s*\{[^}]*display:\s*block[^}]*width:\s*100%[^}]*font-size:\s*\.88em[^}]*text-align:\s*center/s);
  assert.ok(.6 / .88 >= .6 && .6 / .88 <= .7, 'crown is 60–70% of portrait face size');
  assert.equal((html.match(/href="#regalos"/g) || []).length, 2);
  assert.equal((html.match(/<main\b[^>]*id="regalos"/g) || []).length, 1);
  assert.match(html, /@media\s*\(max-width:\s*850px\)[\s\S]*?\.hero\s*\{[^}]*grid-template-columns:\s*1fr/);
  assert.match(html, /@media\s*\(max-width:\s*580px\)[\s\S]*?\.king-group\s*\{[^}]*font-size:\s*clamp\(50px, 16vw, 88px\)/);
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
