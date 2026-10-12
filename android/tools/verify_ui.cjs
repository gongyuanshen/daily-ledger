// Browser component acceptance: real Python API/SQLite via preview_server.py.
// Android SAF/lifecycle signals are controlled boundary fixtures, not device acceptance.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('../.tools/browser-check/node_modules/playwright-core');

async function bridge(context, pending = false) {
  await context.addInitScript(({pending}) => {
    window.__nativeReady = false;
    window.__pending = pending;
    window.AndroidLedger = {
      request(request) {
        if (window.__pending) throw new Error('恢复期间禁止访问账本');
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api', false);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(request);
        if (xhr.status !== 200) throw new Error(`Real API HTTP ${xhr.status}`);
        return xhr.responseText;
      },
      documents() { throw new Error('Android SAF is unavailable in browser verification'); },
      documentsPending() { return window.__pending; },
      ready() {
        window.__nativeReady = true;
        if (window.__pending) setTimeout(() => {
          window.__pending = false;
          window.onDocumentResult({cancelled: true, action: 'restore'});
        }, 0);
      }
    };
  }, {pending});
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const lifecycle = await browser.newContext({viewport: {width: 360, height: 800}, isMobile: true, hasTouch: true});
    await bridge(lifecycle, true);
    const restored = await lifecycle.newPage();
    await restored.goto('http://127.0.0.1:8765/');
    await restored.waitForTimeout(200);
    assert.equal(await restored.evaluate(() => window.__nativeReady), true, 'pending restore must still call ready');
    assert.notEqual(await restored.locator('#month-amount').textContent(), '—', 'cancelled pending restore resumes real reads');
    assert.equal(await restored.locator('#error-panel').isVisible(), false);
    await lifecycle.close();
    console.log('PASS: pending restore cancellation initialization (controlled native boundary)');
    if (process.argv.includes('--pending-only')) return;

    const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    await bridge(context);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.goto('http://127.0.0.1:8765/');
    await page.evaluate(() => {
      const call = (action, payload) => JSON.parse(AndroidLedger.request(JSON.stringify({action, payload}))).data;
      for (const row of call('entries', {start_day:null,end_day:null,category:null,payment:null,keyword:''}).entries) call('delete_entry', {id:row.id});
      for (const row of call('products', {}).products) call('delete_product', {id:row.id});
      call('delete_budget', {month:'2026-10'});
    });
    await page.reload();
    assert.equal(await page.locator('#error-panel').isVisible(), false);
    await page.screenshot({path:'artifacts/ui-empty.png', fullPage:true});

    await page.locator('#add-entry').click();
    await page.locator('#entry-amount').fill('33.662720');
    await page.locator('#entry-day').fill('2026-10-11');
    await page.locator('#entry-category').fill('餐饮');
    await page.locator('#entry-payment').fill('微信');
    await page.locator('#entry-note').fill('<img src=x onerror=alert(1)> 中文消费');
    await page.screenshot({path:'artifacts/ui-entry.png', fullPage:true});
    await page.locator('#save-entry').click();
    await page.locator('#entry-dialog').waitFor({state:'hidden'});
    assert.match(await page.locator('#entries-caption').textContent(), /33.66272/);
    assert.equal(await page.locator('#entries-list img').count(), 0, 'user note stays text');
    await page.reload();
    assert.match(await page.locator('#entries-caption').textContent(), /33.66272/);
    await page.locator('.entry-row').first().click();
    await page.locator('#entry-amount').fill('0');
    await page.locator('#save-entry').click();
    await page.locator('#entry-dialog').waitFor({state:'hidden'});
    await page.locator('[data-page="calendar"]').click();
    await page.locator('#calendar-year').fill('2026');
    await page.locator('#calendar-year').dispatchEvent('change');
    assert.equal(await page.locator('.calendar-month').count(), 12);
    assert.match(await page.locator('#year-amount').textContent(), /0.00/);
    await page.screenshot({path:'artifacts/ui-calendar.png', fullPage:false});
    await page.locator('[data-page="stats"]').click();
    await page.locator('#stats-month').fill('2026-10');
    await page.locator('#stats-month').dispatchEvent('change');
    assert.equal(await page.locator('#error-panel').isVisible(), false, 'all-zero monthly stats valid');
    await page.locator('#edit-budget').click();
    await page.locator('#budget-amount').fill('1000');
    await page.locator('#save-budget').click();
    await page.locator('#budget-dialog').waitFor({state:'hidden'});
    assert.match(await page.locator('#budget-card').textContent(), /1000.00/);

    await page.locator('[data-page="more"]').click();
    await page.locator('#open-products').click();
    await page.locator('#add-product').click();
    await page.locator('#product-name').fill('精确单价商品');
    await page.locator('#product-price').fill('1.000001');
    await page.locator('#save-product').click();
    await page.locator('#product-dialog').waitFor({state:'hidden'});
    assert.match(await page.locator('#products-list').textContent(), /1.000001/);
    await page.locator('[data-page="ledger"]').click();
    await page.locator('#add-entry').click();
    await page.locator('#choose-product').click();
    await page.locator('#picker-quantity').fill('3');
    await page.locator('#apply-product').click();
    await page.locator('#product-picker-dialog').waitFor({state:'hidden'});
    assert.equal(await page.locator('#entry-amount').inputValue(), '3.000003');
    await page.locator('#entry-day').fill('2026-10-11');
    await page.locator('#entry-category').fill('购物');
    await page.locator('#entry-payment').fill('现金');
    await page.locator('#save-entry').click();
    await page.locator('#entry-dialog').waitFor({state:'hidden'});
    assert.match(await page.locator('#entries-caption').textContent(), /3.000003/);
    await page.screenshot({path:'artifacts/ui-ledger.png', fullPage:true});

    await page.locator('#open-filter').click();
    await page.locator('[data-range="month"]').click();
    const expectedMonthEnd = await page.evaluate(() => {
      const today = new Date();
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return `${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,'0')}-${String(end.getDate()).padStart(2,'0')}`;
    });
    assert.equal(await page.locator('#filter-end').inputValue(), expectedMonthEnd, '本月 includes entire calendar month');
    await page.locator('[data-range="all"]').click();
    await page.locator('#filter-keyword').fill('精确单价商品');
    await page.locator('#filter-form button[type="submit"]').click();
    assert.equal(await page.locator('.entry-row').count(), 1);
    await page.locator('.entry-row').click();
    await page.locator('#delete-entry').click();
    await page.locator('#entry-dialog').waitFor({state:'hidden'});
    assert.equal(await page.locator('.entry-row').count(), 0);
    await page.locator('#clear-filter').click();
    assert.equal(await page.locator('.entry-row').count(), 1);

    await page.setViewportSize({width:360,height:800});
    for (const tab of ['ledger','calendar','stats','more']) {
      await page.locator(`[data-page="${tab}"]`).click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${tab} width at360px`);
    }
    assert.deepEqual(errors, []);
    await page.screenshot({path:'artifacts/ui-more.png',fullPage:true});
    await context.close();
    const noBridge = await browser.newPage();
    await noBridge.goto('http://127.0.0.1:8765/');
    assert.match(await noBridge.locator('#error-message').textContent(), /接口未连接/);
    console.log('PASS: real API CRUD/reopen/zero/calendar/budget/products/precision/filter/delete/XSS/360px; missing bridge fails visibly');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
