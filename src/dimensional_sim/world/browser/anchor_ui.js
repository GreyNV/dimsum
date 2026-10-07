/** The anchor space between lives: countdown, offerings, the shop and Journal controls.
 * Renders server rows only; purchases are validated by the simulation. */
import {$, el} from './dom.js';
import {shopSections} from './hud.js';

const JOURNAL_MODES = ['normal', 'favor', 'suppress'];

/** Show or hide the anchor panel for expedition `ex`; rebuilds buttons only when rows change. */
export function renderAnchor(ex) {
  const anchor = ex?.anchor_space, panel = $('anchor-space');
  panel.hidden = !anchor;
  document.body.classList.toggle('anchor-active', !!anchor);
  if (!anchor) return;
  $('anchor-countdown').textContent = anchor.waiting ? 'The next life waits for your choice.'
    : `Next life in ${Math.ceil(anchor.remaining_ms / 1000)}s unless you offer a resource.`;
  $('anchor-dust').textContent = String(ex.meta?.dust ?? ex.dust);
  $('anchor-ash').textContent = String(ex.meta?.ash ?? 0);
  $('anchor-blessing').textContent = String(ex.meta?.blessing ?? 0);
  const signature = JSON.stringify([ex.inventory, ex.shop, ex.meta, anchor.ash_if_burned]);
  if (panel.dataset.inventory === signature) return;
  panel.dataset.inventory = signature;
  $('anchor-hint').textContent = ex.inventory.length
    ? `Offer items for dust (new actions). Keep them and they burn to ${anchor.ash_if_burned} ash (mastery) at rebirth.`
    : `Nothing carried. Rebirth still leaves ${anchor.ash_if_burned} ash from the road you walked.`;
  const offers = $('anchor-offers');
  offers.replaceChildren(...ex.inventory.map(row => {
    const button = el('button', '', `Offer ${row.count} ${row.name.toLowerCase()} (+${anchor.offer?.[row.id] ?? '?'} dust)`);
    button.type = 'button'; button.dataset.trade = row.id;
    return button;
  }));
  if (!ex.inventory.length) offers.textContent = 'Nothing left to offer.';
  const shop = $('anchor-shop');
  shop.replaceChildren(...shopSections(ex.shop).flatMap(section => [el('h3', '', section.title), ...section.rows.map(shopButton)]));
  const journal = ex.meta?.journal || [];
  if (journal.length) {
    shop.append(el('h3', '', 'Journal · shape future encounters'));
    for (const row of journal) {
      const toggle = el('button', '', `${row.name}: ${row.enabled ? 'enabled' : 'disabled'} (mastery ${row.mastery})`);
      toggle.type = 'button'; toggle.dataset.journalToggle = row.id;
      shop.append(toggle);
      if (row.mastery >= 3) {
        const odds = el('button', '', `Appearance odds: ${row.mode} · select to cycle`);
        odds.type = 'button'; odds.dataset.journalFavor = row.id;
        shop.append(odds);
      }
    }
  }
}

function shopButton(row) {
  const button = el('button');
  button.type = 'button'; button.dataset.buy = `${row.kind}:${row.id}`; button.disabled = !row.available;
  button.title = row.available ? row.description : row.reasons.join('; ');
  button.append(el('span', 'cost', `${row.cost} ${row.currency}`), el('b', '', row.name),
    el('small', '', row.available ? row.description : `${row.description} (${row.reasons.join('; ')})`));
  return button;
}

/** The anchor action a click inside the offers/shop/begin controls asks for, or null. */
export function anchorAction(target, expedition) {
  const item = target.closest('button[data-trade]')?.dataset.trade;
  if (item) return {type: 'trade', item};
  if (target.closest('#anchor-begin')) return {type: 'begin_life'};
  const journal = id => expedition?.meta?.journal?.find(entry => entry.id === id);
  const toggle = target.closest('button[data-journal-toggle]')?.dataset.journalToggle;
  if (toggle) {
    const row = journal(toggle);
    return row ? {type: 'journal_toggle', id: toggle, enabled: !row.enabled} : null;
  }
  const favor = target.closest('button[data-journal-favor]')?.dataset.journalFavor;
  if (favor) {
    const row = journal(favor);
    return row ? {type: 'journal_favor', id: favor,
      mode: JOURNAL_MODES[(JOURNAL_MODES.indexOf(row.mode) + 1) % JOURNAL_MODES.length]} : null;
  }
  const value = target.closest('button[data-buy]')?.dataset.buy;
  if (!value) return null;
  const [type, id] = value.split(':');
  return {type, id};
}
