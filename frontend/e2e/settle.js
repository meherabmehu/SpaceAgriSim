/**
 * Make a capture a property of the page rather than of where the last click landed.
 *
 * A screenshot taken while a control still has focus or a pointer is resting on it records the
 * hover/focus ring, and one taken in the same frame as the blur records a mid-transition tint.
 * Both make two captures of the same page differ by a percent of the canvas for no design reason,
 * which turns a visual gate into a coin flip. Blur, park the pointer, wait for the transition.
 */
export async function settleForCapture(page) {
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.mouse.move(0, 0);
  await page.waitForTimeout(300);
}
