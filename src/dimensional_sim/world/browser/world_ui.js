/** Presentation only: the server owns opportunities, control and skill effects. */
export const REGION_CUES = Object.freeze({
  old_road: 'Wagon ruts and old camps. Search here for traces of travel.',
  deep_woods: 'Dense timber and wildlife signs. Branches and tracks are worth seeking.',
  bramble_thicket: 'Tangled growth. Berries and branches are common here.',
  still_glade: 'Open ground and quiet water. Springs and animal signs are easier to find.'
});

export function regionCue(region) {
  return REGION_CUES[region?.id] || '';
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
