/** The anchor space: before the first life (opening), between lives (death) and mid-life
 * when the player contacts it (the world waits). Renders server rows only; purchases are
 * validated by the simulation. Journal controls live on the Journal page. */
import {$, el} from './dom.js';
import {shopSections} from './hud.js';

/** Words for each way of arriving at the anchor. */
export const ANCHOR_TEXT = Object.freeze({
  opening: {
    eyebrow: 'Before your first life', title: 'The anchor',
    dialogue: '“I am the anchor. When your avatar falls, I pull you back here. Whatever it carries when it falls turns into dimensional ash, and ash buys what lasts: crafts you learn, camp buildings, new skills. Visit at camp, or buy Contact anchor to reach me from anywhere.”',
    hint: 'Skill 1: Contact anchor. Skill 2: Possess. Make campfire appears in nearby choices once bought.',
    begin: 'Begin your first life'},
  death: {
    eyebrow: 'Between lives', title: 'The anchor holds you',
    dialogue: '“What you carried has crossed with you. Each resource has become dimensional ash. Spend it on what should outlast a life.”',
    hint: 'Carried resources became dimensional ash. Keep the crafts you found this life, or they are forgotten.',
    begin: 'Begin next life'},
  contact: {
    eyebrow: 'Mid-life', title: 'You reach the anchor',
    dialogue: '',
    hint: 'The world waits while you are here. Spend ash, then step back into this life exactly where you left it.',
    begin: 'Resume this life'},
});

/** Show or hide the anchor panel for expedition `ex`; rebuilds buttons only when rows change. */
export function renderAnchor(ex) {
  const anchor = ex?.anchor_space, panel = $('anchor-space');
  panel.hidden = !anchor;
  document.body.classList.toggle('anchor-active', !!anchor);
  document.body.classList.toggle('anchor-contact', anchor?.kind === 'contact');
  if (!anchor) return;
  const text = ANCHOR_TEXT[anchor.kind] || ANCHOR_TEXT.death;
  $('anchor-countdown').textContent = anchor.kind === 'contact' ? 'The world holds still.'
    : anchor.waiting ? 'The next life waits for your choice.'
    : `Next life in ${Math.ceil(anchor.remaining_ms / 1000)}s.`;
  $('anchor-ash').textContent = String(ex.meta?.ash ?? 0);
  const signature = JSON.stringify([ex.shop, ex.meta, ex.anchor_offerings, anchor.kind, anchor.at_camp, anchor.first_return]);
  if (panel.dataset.inventory === signature) return;
  panel.dataset.inventory = signature;
  $('anchor-eyebrow').textContent = text.eyebrow;
  $('anchor-title').textContent = text.title;
  const dialogue = anchor.kind === 'opening' || anchor.first_return ? text.dialogue : '';
  $('anchor-dialogue').hidden = !dialogue;
  $('anchor-dialogue').textContent = dialogue;
  $('anchor-hint').textContent = anchor.at_camp
    ? 'You can offer what you carry or have stored here for ash now. Conversion has diminishing returns for each resource across lives.'
    : text.hint;
  const unkept = anchor.kind === 'death' ? (ex.shop || []).filter(row => row.kind === 'keep') : [];
  $('anchor-recipe-note').hidden = !unkept.length;
  $('anchor-recipe-note').textContent = unkept.length
    ? `${unkept.length} craft ${unkept.length === 1 ? 'recipe' : 'recipes'} found this life. Keep them with ash below, or they will be forgotten when the next life begins.` : '';
  $('anchor-begin').textContent = unkept.length ? `Begin next life and forget ${unkept.length} ${unkept.length === 1 ? 'recipe' : 'recipes'}` : text.begin;
  $('anchor-begin').dataset.kind = anchor.kind;
  const offerings = $('anchor-offerings');
  offerings.replaceChildren();
  offerings.hidden = !anchor.at_camp || !ex.anchor_offerings?.length;
  if (!offerings.hidden) {
    offerings.append(el('summary', '', `Offer resources now · ${ex.anchor_offerings.length} stacks`));
    for (const row of ex.anchor_offerings) {
      const line = el('div', 'anchor-offer');
      line.append(el('span', '', `${row.name} ×${row.count} · ${row.ash} ash`));
      for (const [label, count] of [['Offer one', 1], ['Offer all', row.count]]) {
        if (count === 1 && row.count === 1 && label === 'Offer one') continue;
        const button = el('button', '', label);
        button.type = 'button'; button.dataset.offer = `${row.id}:${count}`;
        if (count === 1 && !row.ash_one || label === 'Offer all' && !row.ash) {
          button.disabled = true;
          button.title = 'One would yield no ash. Offer a larger stack.';
        }
        line.append(button);
      }
      offerings.append(line);
    }
  }
  const shop = $('anchor-shop'), sections = shopSections(ex.shop);
  shop.replaceChildren(...sections.flatMap(section => [el('h3', '', section.title), ...section.rows.map(shopButton)]));
  if (!sections.length) shop.append(el('p', 'note', 'Nothing to buy yet. Bring things back: everything carried becomes ash.'));
  if ((ex.meta?.journal || []).some(row => row.mastery >= 2))
    shop.append(el('p', 'note', 'Shape future encounters in Journal › Encounters.'));
}

function shopButton(row) {
  const button = el('button');
  button.type = 'button'; button.dataset.buy = `${row.kind}:${row.id}`; button.disabled = !row.available;
  button.title = row.available ? row.description : row.reasons.join('; ');
  button.append(el('span', 'cost', `${row.cost} ash`), el('b', '', row.name),
    el('small', '', row.available ? row.description : `${row.description} (${row.reasons.join('; ')})`));
  return button;
}

/** The anchor action a click inside the shop/begin controls asks for, or null. */
export function anchorAction(target) {
  const begin = target.closest('#anchor-begin');
  if (begin) return {type: begin.dataset.kind === 'contact' ? 'resume' : 'begin_life'};
  const offer = target.closest('button[data-offer]')?.dataset.offer;
  if (offer) {
    const [id, count] = offer.split(':');
    return {type: 'offer', id, count: Number(count)};
  }
  const value = target.closest('button[data-buy]')?.dataset.buy;
  if (!value) return null;
  const [type, id] = value.split(':');
  return {type, id};
}
