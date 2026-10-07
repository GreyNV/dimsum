/** Small DOM and storage helpers shared by the browser client. */
export const $ = id => document.getElementById(id);

/** A new element with an optional class name and text content. */
export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

/** localStorage that never throws (private mode, blocked storage): UI conveniences only. */
export const readUi = key => { try { return localStorage.getItem(key); } catch { return null; } };
export const writeUi = (key, value) => { try { localStorage.setItem(key, value); } catch { /* optional */ } };
