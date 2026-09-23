const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const assert = require('node:assert/strict');

(async () => {
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const directory = '.tmp/browser-' + Date.now(); fs.mkdirSync(directory, {recursive:true});
  const key = '  browser $ exact 雪\nsecond line  ';
  const server = spawn(process.env.PYTHON || 'python', ['-m','uvicorn','app.api_service.app:create_app','--factory','--host','127.0.0.1','--port',String(port),'--no-access-log'], {
    env:{...process.env, PERIMETR_ENV:'development', PERIMETR_VERSION:fs.readFileSync('VERSION','utf8').trim(), PERIMETR_ACCESS_KEY:key, PERIMETR_ACCESS_KEY_HASH:'', PERIMETR_DATABASE_URL:`sqlite:///${directory}/state.sqlite`, PERIMETR_STATE_DIR:directory, PERIMETR_LOGS_DIR:`${directory}/logs`, PERIMETR_COOKIE_SECURE:'false', PERIMETR_PUBLIC_URL:`http://127.0.0.1:${port}`, KERNEL_URL:'', KERNEL_SERVICE_TOKEN:''}, stdio:['ignore','ignore','pipe']
  });
  let startupError=''; server.stderr.on('data', chunk=>startupError=(startupError+chunk.toString()).slice(-3000));
  let browser;
  try {
    const base = `http://127.0.0.1:${port}`;
    for(let attempt=0; attempt<100; attempt++) {
      try { if((await fetch(base+'/v1/health')).ok) break; } catch (_) {}
      if(attempt===99) throw Error('Test server did not start: '+startupError);
      await new Promise(resolve=>setTimeout(resolve,200));
    }
    browser = await chromium.launch({headless:true, ...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror', error=>errors.push(error.message));
    const retiredRequests=[];
    page.on('request',request=>{if(/\/(agents|approvals)(\/|\?|$)/.test(new URL(request.url()).pathname)) retiredRequests.push(request.url());});
    await page.goto(base);
    await page.setViewportSize({width:1920,height:1034});
    await page.evaluate(() => document.fonts.ready);
    const login = await page.locator('.login-panel').boundingBox();
    assert.ok(Math.abs(login.width - 560) <= 1 && Math.abs(login.height - 268) <= 1, JSON.stringify({login}));
    await page.screenshot({path:directory+'/reference-login-1920.png'});
    assert.equal(await page.locator('input[name=access_key]').inputValue(), '');
    assert.equal(await page.locator('input[name=username]').count(),0);
    await page.locator('input[name=access_key]').evaluate((input,text)=>{ const clipboardData = new DataTransfer(); clipboardData.setData('text/plain',text); input.dispatchEvent(new ClipboardEvent('paste',{clipboardData,bubbles:true,cancelable:true})); }, key);
    await page.locator('button[type=submit]').click();
    await page.waitForFunction(()=>document.querySelector('#kernelStatus')?.textContent.includes('configured'));
    await require('./interface-contracts.cjs')(page, directory);
    await require('./agent-removal-contracts.cjs')(page, directory);
    const openView = async view=>{if(page.viewportSize().width<=760) await page.locator('#toggleSidebar').click(); const button=page.locator(`button[data-view="${view}"]`); await button.focus(); await button.click(); if(page.viewportSize().width<=760) await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);};
    await openView('settings');
    assert.equal(await page.locator('.settings-card').count(),5);
    const header = await page.locator('.app>.top').boundingBox();assert.equal(header.height,123);assert.equal(header.x,250);
    await page.locator('#openPasswordModal').click();
    await page.locator('#currentPassword').fill('do not retain');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#currentPassword').inputValue(),'');
    assert.equal(await page.locator('#openPasswordModal').evaluate(node=>node===document.activeElement),true);
    await page.screenshot({path:directory+'/settings-desktop.png'});
    await openView('documentation');
    await page.locator('#documentationSearch').fill('  ESCROW  ');
    assert.ok(await page.locator('.documentation-content article:not([hidden])').count()>0);
    assert.ok(await page.locator('.documentation-content article[hidden]').count()>0);
    await page.locator('.documentation-nav .search-clear').click();
    assert.equal(await page.locator('.documentation-content article[hidden]').count(),0);
    assert.equal(await page.locator('.documentation-content').evaluate(node=>node.scrollTop),0);
    await page.locator('.documentation-nav a[href="#docs-backup"]').click();
    assert.equal(await page.evaluate(()=>window.scrollY),0);
    await page.screenshot({path:directory+'/documentation-desktop.png'});
    await page.route('**/v1/updater/check*',route=>route.fulfill({json:{installed_version:'2.0.0',available_version:'2.0.1',update_available:true,registry:'Verified fixture registry',release_url:'https://github.com/psewdon1m-exocortex/perimetr/releases/tag/perimetr-v2.0.1'}}));
    await page.route('**/v1/updater/status',route=>route.fulfill({json:{available:true,compatible:true,version:'0.5.0'}}));
    await openView('settings');await page.locator('#checkForUpdates').click();
    await page.locator('#installUpdate').waitFor({state:'visible'});
    const updateRect = await page.locator('.update-install-modal').boundingBox(); assert.equal(updateRect.width,760); assert.equal(updateRect.height,702);
    await page.locator('#installUpdate').click();
    assert.equal(await page.locator('#confirmInstallUpdate').isDisabled(),true);
    assert.equal(await page.locator('#operatorSaved').isChecked(),false);
    const warningRect = await page.locator('#updateWarning').boundingBox(); assert.equal(warningRect.width,620); assert.ok(Math.abs(warningRect.x-(1440-620)/2)<=1);
    await page.screenshot({path:directory+'/update-warning.png'});
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:390,height:844});
    await openView('settings');
    assert.equal((await page.locator('.app>.top').boundingBox()).height,96);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:directory+'/settings-mobile.png'});
    await openView('documentation');
    await page.screenshot({path:directory+'/documentation-mobile.png'});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);
    assert.deepEqual(retiredRequests,[], 'Removed control-plane endpoints must never be polled');
    console.log(JSON.stringify({result:'PASS',checks:['exact-key login and reference geometry','1920px reference component measurements','persisted keyboard reorder','accent preview cancellation and contrast','modal focus/secret clearing/backdrop protection','documentation full-text/clear/current section/independent scroll','collection search/count/actions','bounded log columns','update dimensions/save gate/helper scope','1919px to 360px responsive layouts and short viewport','hidden sidebar and reduced motion'],screenshots:directory}));
  } finally {
    if(browser) await browser.close();
    server.kill();
  }
})().catch(error=>{console.error(error);process.exitCode=1});
