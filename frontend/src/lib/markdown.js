/**
 * Lightweight helper — turns lightly-formatted AI markdown into clean plain text.
 * Removes:
 *   - **bold** and __bold__ wrappers  →  bold
 *   - *italic* wrappers               →  italic
 *   - `inline code` backticks         →  code
 *   - ```code fences```               →  code
 *   - # / ## / ### heading markers    →  removed
 *   - > blockquote markers            →  removed
 * Preserves:
 *   - line breaks
 *   - dashes / bullets (we display them as-is)
 */
export function stripMarkdown(input = "") {
  if (input == null) return "";
  let s = String(input);
  // triple-backtick code fences
  s = s.replace(/```[a-zA-Z]*\n?/g, "").replace(/```/g, "");
  // bold / italic wrappers
  s = s.replace(/\*\*(.*?)\*\*/g, "$1");
  s = s.replace(/__(.*?)__/g, "$1");
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1$2");
  // inline code
  s = s.replace(/`([^`]+)`/g, "$1");
  // headings
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, "");
  // blockquotes
  s = s.replace(/^\s{0,3}>\s?/gm, "");
  return s.trim();
}
