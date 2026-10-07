/** Actor and combat-feedback art, re-exported from its focused modules:
 *   sprites.js     palette roles, outlined cell sprites, shadows, depth helpers
 *   player_art.js  the pixel-art avatar, poses, fists and work marks
 *   combat_art.js  boars, health pips, reach, punch lines, impacts, floating text
 *   place_art.js   encounter spots, anchor camp, ambush site, the old man
 * Presentation only: nothing here decides hits, damage, timing or collision.
 */
export * from './sprites.js';
export * from './player_art.js';
export * from './combat_art.js';
export * from './place_art.js';
