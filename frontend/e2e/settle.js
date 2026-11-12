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
  // Wait for the webfont to be resolved. Before Phase 37 the page asked for Inter and shipped
  // nothing, so each machine painted a different fallback and the gate compared two different
  // typographic systems; even with the font bundled, a capture taken mid-swap would photograph
  // whichever face had loaded by then. `fonts.ready` is the state, not a guess.
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

/**
 * Screenshot one element at integer page coordinates.
 *
 * `locator.screenshot()` rounds a fractional CSS box at capture time using the element's resting
 * scroll offset, so a panel whose measured height is 626.61 px produced a 627-pixel image on one run
 * and a 628-pixel image on the next. The visual gate compares canvas sizes exactly - correctly, since
 * a size change normally means something moved - so a sub-pixel layout must not be allowed to
 * masquerade as a regression. Rounding the clip here makes the capture a function of the layout and
 * nothing else; the gate keeps its exact-size rule and its 2 % pixel budget.
 */
export async function captureElement(page, locator, path) {
  await settleForCapture(page);
  const box = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      x: rect.x + window.scrollX,
      y: rect.y + window.scrollY,
      width: rect.width,
      height: rect.height,
    };
  });
  await page.screenshot({
    path,
    fullPage: true,
    clip: {
      x: Math.round(box.x),
      y: Math.round(box.y),
      width: Math.round(box.width),
      height: Math.round(box.height),
    },
  });
}
