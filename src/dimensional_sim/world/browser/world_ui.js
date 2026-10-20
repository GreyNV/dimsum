/** Presentation only: the server owns opportunities, control and skill effects. */
export const REGION_CUES = Object.freeze({
  old_road: 'Wagon ruts and old camps. Search here for traces of travel.',
  deep_woods: 'Dense timber and wildlife signs. Branches and tracks are worth seeking.',
  bramble_thicket: 'Tangled growth. Berries and branches are common here.',
  still_glade: 'Open ground and quiet water. Springs and animal signs are easier to find.'
});

/** Plain words for catalog.ECOLOGY, for the "picked over" cue. */
const ECOLOGY_WORDS = {wood: 'fallen wood', berries: 'berries', game: 'animal signs', fungi: 'mushrooms', eggs: 'nests', fish: 'fish'};
export function regionCue(region) {
  if (region?.shimmer) return 'The air hums here. Rare things are closer this life.';
  const base = region?.site ? `${region.site}: ${region.condition?.text || 'a landmark with its own encounters and materials.'}`
    : REGION_CUES[region?.id] || '';
  const worked = (region?.worked || []).map(e => ECOLOGY_WORDS[e] || e);
  if (!worked.length) return base;
  const list = worked.length > 1 ? `${worked.slice(0, -1).join(', ')} and ${worked.at(-1)}` : worked[0];
  return `Picked over this life: fewer ${list} around here.`;   // replaces the flavour line (panel height)
}

/** m:ss for a cooldown. */
export const clockText = ms => {
  const s = Math.ceil(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

export function skillSlots(expedition) {
  const slots = expedition?.skill_slots || [];
  return Array.from({length: 3}, (_, index) => {
    const slot = slots[index] || {name: 'Empty', state: 'locked'};
    const state = ['ready', 'active', 'cooldown', 'disabled', 'locked'].includes(slot.state)
      ? slot.state : 'disabled';
    const remaining = Math.max(0, slot.remaining_ms || 0), total = Math.max(0, slot.cooldown_ms || 0);
    const note = slot.note || (state === 'cooldown' ? `Ready in ${clockText(remaining)}` : '');
    const charge = slot.charge_max_ms ? Math.max(0, Math.min(1, slot.charge_ms / slot.charge_max_ms))
      : state === 'cooldown' && total ? 1 - remaining / total : 1;
    return {name: slot.name || 'Empty', state, usable: state === 'ready', note, hint: slot.hint || '',
      charge};
  });
}

export function worldMode(expedition) {
  return expedition?.control === 'manual' ? 'active' : 'auto';
}
