/** Compact, server-owned choices for the current clearing or camp. */
import {$, el} from './dom.js';

export function renderLocationContext(context, open) {
  const toggle = $('context-toggle'), panel = $('context-panel');
  toggle.hidden = !context;
  panel.hidden = !context || !open;
  toggle.setAttribute('aria-expanded', String(!!context && open));
  if (!context) return;
  const count = context.actions.filter(row => !row.reasons.length).length + (context.visit ? 1 : 0);
  toggle.textContent = context.kind === 'wild' ? 'Make camp' : `${context.name} · ${count} ${count === 1 ? 'choice' : 'choices'}`;
  const signature = JSON.stringify(context);
  if (panel.dataset.signature === signature) return;
  panel.dataset.signature = signature;
  $('context-title').textContent = context.name;
  const rows = [];
  if (context.visit) {
    const visit = el('button', 'context-choice');
    visit.type = 'button'; visit.dataset.locationAction = 'visit_anchor';
    visit.append(el('b', '', 'Speak with the anchor'), el('small', '', 'Offer resources for ash or buy lasting upgrades.'));
    rows.push(visit);
  }
  for (const row of context.actions) {
    const button = el('button', 'context-choice');
    button.type = 'button'; button.dataset.locationAction = row.id;
    button.disabled = !!row.reasons.length;
    const cost = row.cost.length ? ` · ${row.cost.map(([name, amount]) => `${amount} ${name}`).join(', ')}` : '';
    const detail = row.reasons.length ? row.reasons.join('; ') : row.description;
    button.title = detail;
    button.append(el('b', '', row.name + cost), el('small', '', detail));
    rows.push(button);
  }
  $('context-actions').replaceChildren(...rows);
}

export function locationAction(target) {
  const id = target.closest('button[data-location-action]')?.dataset.locationAction;
  return id ? {type: 'location', id} : null;
}
