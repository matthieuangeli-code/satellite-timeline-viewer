import { chromium } from "playwright";

const origin = "https://matthieuangeli-code.github.io/satellite-timeline-viewer";
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1360, height: 920 } });
const errors = [];
page.on("pageerror", (e) => errors.push("JS: " + e.message));
page.on("console", (m) => { if(m.type() === "error") errors.push("Console: " + m.text().slice(0, 250)); });
try {
  const response = await page.goto(origin + "/demo.html", { waitUntil: "domcontentloaded", timeout: 35000 });
  if (response.status() !== 200) throw new Error("Demo returned HTTP " + response.status());
  await page.waitForFunction(() => !!document.querySelector(".leaflet-map-pane"), { timeout: 25000 });
  console.log("Map initialized with Leaflet.");
  await page.waitForFunction(() => {
    const text = document.getElementById("found-address")?.textContent || "";
    return text !== "En attente de recherche" && text !== "Recherche en cours";
  }, { timeout: 35000 });
  const address = await page.locator("#found-address").innerText();
  const status = await page.locator("#status").innerText();
  console.log("Geocoder result:", address, "| status:", status);
  if (/Non trouvé|indisponible|introuvable/i.test(address)) throw new Error("Geocoding failed: " + status);
  await page.locator("#compare").fill("75");
  const divider = await page.locator("#divider").evaluate(el => el.style.left);
  if(divider !== "75%") throw new Error("Slider update failed: " + divider);
  await page.waitForFunction(() => document.querySelectorAll(".leaflet-tile-loaded").length > 0, { timeout: 35000 });
  const tileStatus = await page.evaluate(() => ({
    tileCount:document.querySelectorAll(".leaflet-tile-loaded").length,
    parcel:document.querySelector("#parcel")?.textContent,
    status:document.querySelector("#status")?.textContent
  }));
  console.log("Imagery and parcel:",JSON.stringify(tileStatus));
  if(tileStatus.tileCount < 1) throw new Error("No IGN imagery tile loaded.");
  const h = await page.goto(origin + "/", {waitUntil:"domcontentloaded",timeout:35000});
  if (h.status() !== 200) throw new Error("Home HTTP "+h.status());
  await page.locator('a[href="./demo.html"]').first().waitFor({timeout:8000});
  console.log("Homepage CTA to demo confirmed.");
  console.log("Browser smoke test PASSED.");
} catch(e) {
  console.error("Browser smoke test FAILED:",e.message);
  console.error(errors.slice(-10).join("\n"));
  process.exitCode = 1;
} finally { await browser.close(); }
