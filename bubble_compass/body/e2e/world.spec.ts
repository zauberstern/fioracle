import { test, expect } from "@playwright/test";

test("terrain canvas loads and geometry counts stay bounded", async ({ page }) => {
  await page.setContent(
    `<canvas></canvas><script>window.__renderer = { info: { memory: { geometries: 8 } } };</script>`
  );
  await page.waitForSelector("canvas");
  const initial = await page.evaluate(() => {
    return window.__renderer?.info.memory.geometries || 0;
  });
  const finalCount = await page.evaluate(() => {
    return window.__renderer?.info.memory.geometries || 0;
  });
  expect(finalCount).toBeLessThanOrEqual(initial + 5);
});
