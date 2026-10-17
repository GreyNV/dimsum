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

export function skillSlots(expedition) {
  const slots = expedition?.skill_slots || [];
  return Array.from({length: 3}, (_, index) => {
    const slot = slots[index] || {name: 'Empty', state: 'locked'};
    const state = ['ready', 'active', 'cooldown', 'disabled', 'locked'].includes(slot.state)
      ? slot.state : 'disabled';
    return {name: slot.name || 'Empty', state, usable: state === 'ready'};
  });
}

export function worldMode(expedition) {
  return expedition?.control === 'manual' ? 'active' : 'auto';
}
