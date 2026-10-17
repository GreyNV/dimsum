/** The anchor space between lives: conversion explanation and shop (Journal controls live on the Journal page).
 * Renders server rows only; purchases are validated by the simulation. */
import {$, el} from './dom.js';
import {shopSections} from './hud.js';

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
  if ((ex.meta?.journal || []).some(row => row.mastery >= 2))
    shop.append(el('p', 'note', 'Shape future encounters in Journal › Encounters.'));
}

function shopButton(row) {
  const button = el('button');
  button.type = 'button'; button.dataset.buy = `${row.kind}:${row.id}`; button.disabled = !row.available;
  button.title = row.available ? row.description : row.reasons.join('; ');
  button.append(el('span', 'cost', `${row.cost} ${row.currency}`), el('b', '', row.name),
    el('small', '', row.available ? row.description : `${row.description} (${row.reasons.join('; ')})`));
  return button;
}

/** The anchor action a click inside the shop/begin controls asks for, or null. */
export function anchorAction(target) {
  if (target.closest('#anchor-begin')) return {type: 'begin_life'};
  const value = target.closest('button[data-buy]')?.dataset.buy;
  if (!value) return null;
  const [type, id] = value.split(':');
  return {type, id};
}
