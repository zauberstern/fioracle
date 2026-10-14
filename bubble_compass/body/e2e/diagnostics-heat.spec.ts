import { expect, test } from "@playwright/test";

test("heat labels sit inside the diagnostics chart", async ({ page }) => {
  await page.goto("/#/diagnostics");
  const chart = page.locator(".diag-chart").first();
  const label = chart.getByText("US junk", { exact: true });
  await expect(label).toBeVisible({ timeout: 30_000 });
  const chartBox = await chart.boundingBox();
  const labelBox = await label.boundingBox();
  expect(chartBox).not.toBeNull();
  expect(labelBox).not.toBeNull();
  if (!chartBox || !labelBox) return;
  expect(labelBox.x).toBeGreaterThanOrEqual(chartBox.x - 1);
  expect(labelBox.x + labelBox.width).toBeLessThanOrEqual(
    chartBox.x + chartBox.width + 1
  );
});
