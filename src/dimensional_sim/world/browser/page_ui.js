/** DOM rendering for the page overlay (tabs and page sections). Page content comes
 * from pages.js models; this module only turns a model into elements. */
import {$, el} from './dom.js';

/** One button per page, labelled with its icon, name and number key. */
export function buildTabs(pages) {
  $('tabs').replaceChildren(...pages.map((p, i) => {
    const button = el('button');
    button.type = 'button'; button.dataset.page = p.id; button.title = `${p.label} (${i + 1})`;
    const icon = el('span', 'tab-icon', p.icon); icon.setAttribute('aria-hidden', 'true');
    button.append(icon, el('span', 'tab-label', p.label));
    return button;
  }));
}

/** The page's subtab bar (hidden when the page has none); `sub` is the active one. */
export function renderSubtabs(target, subtabs, sub) {
  target.hidden = !subtabs.length;
  target.replaceChildren(...subtabs.map(t => {
    const button = el('button', '', t.label);
    button.type = 'button'; button.dataset.subpage = t.id;
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', String(t.id === sub));
    return button;
  }));
}

/** The Journal action a click on a control button asks for, or null. */
export function journalAction(target) {
  const raw = target.closest('button[data-journal]')?.dataset.journal;
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

/** A collapsible <details> for one page section. `closed` remembers sections the
 * player folded (by page and title); `armed` is the action awaiting confirmation. */
export function renderSection(section, {page, closed, armed}) {
  const key = `${page}:${section.title.replace(/ ·.*$/, '')}`;
  const box = el('details', 'page-section'); box.open = !closed.has(key);
  box.addEventListener('toggle', () => { box.open ? closed.delete(key) : closed.add(key); });
  box.append(el('summary', '', section.title));
  const body = SECTION_KINDS[section.kind]?.(section, armed);
  if (body) box.append(body);
  if (section.note) box.append(el('p', 'note', section.note));
  return box;
}

const SECTION_KINDS = {rows, table, progress, actions, controls};

function rows(section) {
  const list = el('dl', 'rows');
  for (const [name, value, note] of section.rows) {
    const dd = el('dd', '', value);
    if (note) dd.append(el('small', '', note));
    list.append(el('dt', '', name), dd);
  }
  return list;
}

function table(section) {
  if (!section.rows.length) return el('p', 'note', section.empty || 'Nothing yet.');
  const result = el('table'), head = el('tr'), body = el('tbody');
  for (const name of section.head) head.append(el('th', '', name));
  for (const row of section.rows) { const tr = el('tr'); for (const cell of row) tr.append(el('td', '', cell)); body.append(tr); }
  const thead = el('thead'); thead.append(head); result.append(thead, body);
  return result;
}

function progressBar(target, item) {
  const top = el('div', 'p-head'); top.append(el('span', '', item.label), el('b', '', item.text));
  const track = el('i'), fill = el('s');
  fill.style.width = `${Math.round(100 * Math.min(1, item.value / Math.max(1, item.max)))}%`;
  track.append(fill);
  target.append(top, track);
}

function progress(section) {
  const list = el('ul', 'progress');
  for (const item of section.items) {
    const li = el('li', [item.done ? 'done' : '', item.dim ? 'dim' : '', item.bars ? 'group' : ''].join(' ').trim());
    if (item.bars) {   // one attribute: regular bar with its dimensional bar right below
      li.append(el('div', 'p-group', item.label));
      for (const sub of item.bars) { const row = el('div', sub.dim ? 'p-bar dim' : 'p-bar'); progressBar(row, sub); li.append(row); }
    } else progressBar(li, item);
    if (item.note) li.append(el('small', '', item.note));
    list.append(li);
  }
  return list;
}

function actions(section, armed) {
  const list = el('div', 'page-actions');
  for (const b of section.buttons) {
    const row = el('div');
    const button = el('button', [b.danger ? 'danger' : '', armed === b.id ? 'armed' : ''].join(' ').trim(),
      armed === b.id ? 'Select again to confirm' : b.label);
    button.type = 'button'; button.dataset.act = b.id;
    row.append(button, el('small', '', b.note));
    list.append(row);
  }
  return list;
}

/** Journal controls: one row per encounter with its toggle buttons (each carries its action). */
function controls(section) {
  if (!section.items.length) return el('p', 'note', section.empty || 'Nothing yet.');
  const list = el('div', 'page-controls');
  for (const item of section.items) {
    const row = el('div', 'control-row');
    row.append(el('span', 'control-label', item.label));
    const buttons = el('div', 'control-buttons');
    for (const b of item.buttons) {
      const button = el('button', b.on ? 'on' : '', b.label);
      button.type = 'button'; button.dataset.journal = JSON.stringify(b.action); button.title = b.note || '';
      button.setAttribute('aria-pressed', String(!!b.on));
      buttons.append(button);
    }
    row.append(buttons);
    list.append(row);
  }
  return list;
}
