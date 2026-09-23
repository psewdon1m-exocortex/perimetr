// Visual coordinates come from Part 01, not from the implementation under test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
module.exports = async function verifyInterface(page, directory) {
  const close = (actual, expected, name) => assert.ok(Math.abs(actual - expected) <= 1, `${name}: ${actual}, expected ${expected}`);
  const box = selector => page.locator(selector).boundingBox();
  const visit = async view => {
    if (page.viewportSize().width <= 720) await page.locator('#toggleSidebar').click();
    await page.locator(`.sidebar button[data-view="${view}"]`).click();
    await page.mouse.move(page.viewportSize().width - 2, 2);
    await page.waitForTimeout(180); // Wait for the normative 160 ms hover transition before capture.
    if (page.viewportSize().width <= 720) await page.waitForFunction(() => document.querySelector('.sidebar').getBoundingClientRect().right <= 1);
  };
  const noOverflow = async label => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('.view.active')].every(node => node.scrollWidth <= node.clientWidth + 1)), label);
  const measurements = {};
  await page.route('**/v1/system/metrics', route => route.fulfill({json:{cpu_percent:50.4,cpu_cores:1,ram_percent:50.3,ram_used_bytes:1073741824,ram_total_bytes:2147483648,disk_percent:50.1,disk_used_bytes:10737418240,disk_total_bytes:21474836480,uptime_seconds:74722}}));
  await page.evaluate(async () => {state.metrics = await api('/v1/system/metrics');renderMetrics();});
  await page.setViewportSize({width: 1920, height: 1080});
  await visit('dashboard');
  await page.evaluate(() => document.fonts.ready);
  close((await box('.sidebar')).width, 250, 'Sidebar width');
  close((await box('.app > .top')).height, 123, 'Header height');
  assert.equal(await page.locator('#viewTitle').evaluate(node => getComputedStyle(node).fontSize), '80px');
  assert.equal(await page.locator('#viewTitle').evaluate(node => getComputedStyle(node).textTransform), 'none');
  for (const [id, x, y] of [['cpu',280,151], ['ram',1100,151], ['disk',280,347], ['uptime',1100,347]]) {
    const rect = await box(`[data-metric-id="${id}"]`); measurements[id] = rect;
    close(rect.x,x,id+' x'); close(rect.y,y,id+' y'); close(rect.width,790,id+' width'); close(rect.height,166,id+' height');
  }
  close((await box('[data-metric-id="correlation"]')).width,1610,'Full card width');
  close((await box('#cpuProgress')).height,9,'Metric progress height');
  await page.screenshot({path:directory+'/reference-dashboard-1920.png'});
  const handle = await box('[data-metric-id="uptime"] .order-handle');
  await page.mouse.move(handle.x+20,handle.y+20);await page.mouse.down();
  await page.mouse.move(380,230,{steps:12});
  assert.equal(await page.locator('.card-placeholder').count(),1);
  await page.mouse.up();
  await page.waitForFunction(() => operatorPreferences.layout.dashboard[0] === 'uptime');
  await page.evaluate(() => savePresentation({layout:{dashboard:['cpu','ram','disk','uptime','correlation']}}));
  await visit('settings');
  measurements.appearance = await box('.appearance-card');
  close(measurements.appearance.x,280,'Appearance x'); close(measurements.appearance.y,153,'Appearance y');
  close(measurements.appearance.height,401,'Appearance height');
  close((await box('#colorAccent')).x,322,'Swatch x'); close((await box('#colorAccent')).y,307,'Swatch y');
  close((await box('#accentHex')).width,326,'Hex field width');
  close((await box('#openPasswordModal')).width,326,'Access Key action width');
  await page.screenshot({path:directory+'/reference-settings-1920.png'});
  // Preview must not survive navigation or accept an unreadable color.
  await page.locator('#accentHex').fill('#FFAA00');
  await visit('dashboard');
  assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim().toLowerCase()), '#00a8ff');
  await visit('settings'); await page.locator('#accentHex').fill('#000000');
  assert.equal(await page.locator('#accentHex').evaluate(node => node.checkValidity()), false);
  await page.locator('#resetTheme').click();
  // Keyboard reorder persists through reload and returns to the canonical order.
  await page.locator('.appearance-card .order-handle').focus();
  await page.keyboard.press('Alt+ArrowDown');
  await page.waitForFunction(() => operatorPreferences.layout.settings[0] === 'security');
  await page.reload(); await page.waitForFunction(() => document.querySelector('#kernelStatus')?.textContent.includes('configured'));
  await visit('settings'); assert.equal(await page.locator('.settings-card').first().getAttribute('data-setting-id'), 'security');
  await page.locator('.appearance-card .order-handle').focus(); await page.keyboard.press('Alt+ArrowUp');
  await page.waitForFunction(() => operatorPreferences.layout.settings[0] === 'appearance');
  await page.locator('.notification-stack button').evaluateAll(buttons => buttons.forEach(button => button.click()));
  // Secret edits survive a backdrop click; explicit dismissal clears them.
  await page.locator('#openPasswordModal').click(); await page.locator('#currentPassword').fill('temporary input');
  await page.locator('#passwordModalBackdrop').click({position:{x:5,y:5}});
  assert.ok(await page.locator('#passwordModalBackdrop').evaluate(node => node.classList.contains('open')));
  await page.keyboard.press('Escape'); assert.equal(await page.locator('#currentPassword').inputValue(),'');
  // Documentation navigation and articles are distinct scroll owners.
  await visit('documentation');
  close((await box('.documentation-nav')).width,220,'Documentation navigation');
  close((await box('.documentation-content')).width,1120,'Article width');
  close((await box('.documentation-page')).height,889,'Documentation workspace');
  await page.screenshot({path:directory+'/reference-documentation-1920.png'});
  await page.locator('.documentation-content').evaluate(node => node.scrollTop=node.scrollHeight);
  await page.waitForFunction(() => document.querySelector('.documentation-nav a[aria-current]')?.hash === '#docs-troubleshooting');
  assert.equal(await page.evaluate(() => window.scrollY),0);
  await page.locator('#documentationSearch').fill('no-matching-topic-123456');
  assert.ok(await page.locator('#documentationEmpty').isVisible());
  assert.equal(await page.locator('.documentation-content').evaluate(node => node.scrollTop),0);
  await page.locator('#documentationSearch').press('Escape');
  assert.equal(await page.locator('#documentationSearch').inputValue(),'');
  assert.ok(await page.locator('.search-clear').last().evaluate(node => node.disabled));
  // Library search/count/create form one sticky command bar, including empty state.
  await visit('properties');
  assert.ok(await page.locator('.collection-command-bar [data-add-library-property]').isVisible());
  assert.equal(await page.locator('#propertiesCount').textContent(),'0 of 0');
  await page.locator('#propertiesPageSearch').fill('nothing'); await page.locator('#propertiesPageSearch').press('Escape');
  assert.equal(await page.locator('#propertiesPageSearch').inputValue(),'');
  await page.screenshot({path:directory+'/reference-collection-1920.png'});
  await visit('settings');
  await page.locator('.logger-card').scrollIntoViewIfNeeded();
  close((await box('.log-table')).height,460,'Bounded log table');
  await page.screenshot({path:directory+'/reference-logs-1920.png'});
  // Real discovery is replaced only inside this UI fixture. No installation is sent.
  await page.route('**/v1/updater/check*',route => route.fulfill({json:{installed_version:route.request().url().includes('component=updater')?'0.5.0':'2.0.0',available_version:route.request().url().includes('component=updater')?'0.5.1':'2.0.1',update_available:true,registry:'Checked',release_url:'https://github.com/psewdon1m-exocortex/perimetr/releases/tag/perimetr-v2.0.1'}}));
  await page.route('**/v1/updater/status',route=>route.fulfill({json:{available:true,compatible:true,version:'0.5.0'}}));
  await page.locator('#checkForUpdates').click(); await page.locator('#installUpdate').waitFor({state:'visible'});
  const dialog = await box('.update-install-modal'), discovery = await box('.update-discovery');
  close(dialog.width,760,'Update width');close(dialog.height,702,'Update height');close(discovery.x-dialog.x,25,'Discovery x');close(discovery.y-dialog.y,191,'Discovery y');close(discovery.height,203,'Discovery height');
  await page.screenshot({path:directory+'/reference-update-available.png'});
  await page.locator('#installUpdate').click();
  close((await box('#updateWarning')).width,620,'Warning width');
  assert.equal(await page.locator('#updateInstallModalBackdrop').evaluate(node=>node.inert),true);
  assert.equal(await page.locator('#confirmInstallUpdate').isDisabled(),true);
  await page.screenshot({path:directory+'/reference-update-warning.png'});
  await page.keyboard.press('Escape'); await page.keyboard.press('Escape');
  await page.locator('#checkHelperUpdates').click(); await page.locator('#installHelperUpdate').waitFor({state:'visible'});
  assert.equal(await page.locator('#updateInstalled').textContent(),'0.5.0');
  assert.equal(await page.locator('#installUpdate').isVisible(),false); await page.keyboard.press('Escape');
  // Additional component states are render fixtures, never calls to a real host job.
  await page.locator('#checkForUpdates').click();
  await page.waitForFunction(() => !updateState.checking);
  await page.evaluate(() => renderUpdateJob({id:'visual-fixture',request_id:'visual-fixture',version:'2.0.1',state:'APPLYING',message:'Applying the verified release.',progress:{mode:'determinate',completed:2,total:4,unit:'steps'}}));
  assert.equal(await page.locator('#updateProgress').getAttribute('aria-valuenow'),'50');
  assert.equal(await page.locator('#updateProgressLabel').textContent(),'2 / 4 steps');
  assert.equal(await page.locator('#checkUpdatesAgain').isDisabled(),true);
  await page.screenshot({path:directory+'/reference-update-running.png'});
  await page.evaluate(() => renderUpdateJob({id:'visual-fixture',request_id:'visual-fixture',version:'2.0.1',state:'COMPLETED',message:'Update completed.',progress:{mode:'complete'}}));
  await page.waitForTimeout(180);
  assert.equal(await page.locator('#updateInstallModalTitle').isVisible(),true);
  assert.equal(await page.locator('.update-discovery').isVisible(),true);
  await page.screenshot({path:directory+'/reference-update-completed.png'});
  await page.evaluate(() => {updateState.job=null;updateState.request=null;localStorage.removeItem('perimetr.updateOperation');document.querySelector('#updateJobPanel').hidden=true;});
  await page.keyboard.press('Escape');
  for(const [width,height] of [[1919,1034],[1000,800],[720,900],[600,900],[420,844],[360,800],[640,360]]) {
    await page.setViewportSize({width,height});
    for(const view of ['dashboard','settings','documentation','properties']) {await visit(view);await noOverflow(`${view} at ${width}x${height}`);}
    await page.screenshot({path:directory+`/responsive-${width}x${height}.png`});
  }
  await page.setViewportSize({width:1920,height:1080});await visit('settings');
  await page.locator('#sidebarAuto').check();await page.waitForFunction(()=>document.body.classList.contains('sidebar-auto'));
  await page.mouse.move(1500,5);await page.locator('#viewTitle').focus();
  await page.locator('#accentHex').focus();
  close((await box('.app')).x,18,'Auto-hide content track');await noOverflow('Hidden sidebar');
  await page.locator('#sidebarAuto').uncheck();await page.waitForFunction(()=>document.body.classList.contains('sidebar-fixed'));
  await page.emulateMedia({reducedMotion:'reduce'});await visit('dashboard');
  await page.locator('[data-metric-id="cpu"]').hover();
  assert.equal(await page.locator('[data-metric-id="cpu"]').evaluate(node=>getComputedStyle(node).transform),'none');
  await page.emulateMedia({reducedMotion:'no-preference'});await page.mouse.move(1900,5);
  fs.writeFileSync(directory+'/reference-measurements.json',JSON.stringify(measurements,null,2));
  await page.setViewportSize({width:1440,height:1000});
};
