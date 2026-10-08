/** The anchor space between lives: conversion explanation, shop and Journal controls.
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
    : `Next life in ${Math.ceil(anchor.remaining_ms / 1000)}s.`;
  $('anchor-ash').textContent = String(ex.meta?.ash ?? 0);
  $('anchor-blessing').textContent = String(ex.meta?.blessing ?? 0);
  const signature = JSON.stringify([ex.shop, ex.meta, anchor.first_return]);
  if (panel.dataset.inventory === signature) return;
  panel.dataset.inventory = signature;
  $('anchor-dialogue').hidden = !anchor.first_return;
  $('anchor-hint').textContent = anchor.first_return
    ? 'All resources carried through a life become dimensional ash here. Repeated copies of the same resource across lives yield less ash. Spend ash to grasp possibilities in coming lives and unlock follow-up actions.'
    : 'Carried resources became dimensional ash. Repeated copies of the same resource across lives yield less ash.';
  const shop = $('anchor-shop');
  shop.replaceChildren(...shopSections(ex.shop).flatMap(section => [el('h3', '', section.title), ...section.rows.map(shopButton)]));
  const journal = ex.meta?.journal || [];
  if (journal.length) {
    shop.append(el('h3', '', 'Journal · shape future encounters'));
    for (const row of journal) {
      shop.append(el('p', 'note', `${row.name}: mastery ${row.mastery}`));
      if (row.mastery >= 2) {
        const odds = el('button', '', `Appearance odds: ${row.mode} · select to cycle`);
        odds.type = 'button'; odds.dataset.journalFavor = row.id;
        shop.append(odds);
      }
      if (row.mastery >= 3) {
        for (const region of row.regions || []) {
          const chosen = ex.meta?.journal_guarantee === row.id &&
            ex.meta?.journal_guarantee_region === region.id;
          const guarantee = el('button', '', chosen
            ? `Guaranteed ${row.name} in ${region.name} - select to clear`
            : `Guarantee ${row.name} once in ${region.name}`);
          guarantee.type = 'button'; guarantee.dataset.journalGuarantee = row.id;
          guarantee.dataset.region = region.id;
          shop.append(guarantee);
        }
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
  if (target.closest('#anchor-begin')) return {type: 'begin_life'};
  const journal = id => expedition?.meta?.journal?.find(entry => entry.id === id);
  const favor = target.closest('button[data-journal-favor]')?.dataset.journalFavor;
  if (favor) {
    const row = journal(favor);
    return row ? {type: 'journal_favor', id: favor,
      mode: JOURNAL_MODES[(JOURNAL_MODES.indexOf(row.mode) + 1) % JOURNAL_MODES.length]} : null;
  }
  const guaranteed = target.closest('button[data-journal-guarantee]')?.dataset.journalGuarantee;
  if (guaranteed) {
    const region = target.closest('button[data-journal-guarantee]').dataset.region;
    const chosen = expedition?.meta?.journal_guarantee === guaranteed &&
      expedition?.meta?.journal_guarantee_region === region;
    return {type: 'journal_guarantee', id: chosen ? null : guaranteed, region: chosen ? null : region};
  }
  const value = target.closest('button[data-buy]')?.dataset.buy;
  if (!value) return null;
  const [type, id] = value.split(':');
  return {type, id};
}
