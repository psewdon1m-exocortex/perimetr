const assert = require('node:assert/strict');

module.exports = async function verifyAgentRemoval(page, directory) {
  await page.setViewportSize({width:1920,height:1080});
  assert.equal(await page.locator('[data-view="agents"], #agents, [id^="agent"]').count(),0);
  assert.deepEqual(await page.locator('.nav small').allTextContents(),['01','02','03','04','05','06']);
  await page.locator('[data-view="overview"]').click();
  for (const block of ['laboratory_block','perimetr_block']) {
    await page.locator(`[data-overview-block="${block}"]`).click();
    assert.ok(await page.locator('#humanProperties').isVisible());
    assert.ok(!(await page.locator('#fullscreenBody').textContent()).includes('Agent'));
    await page.locator('#closeFullscreen').click();
    assert.ok(!(await page.locator('#fullscreenPanel').evaluate(node=>node.classList.contains('open'))));
  }
  // Exercise retained entity detail, in-place Subject conversion and Pod workspace.
  const object = await page.evaluate(async () => {
    const created = await api('/v1/objects',{method:'POST',body:JSON.stringify({name:'Retained project',kind:'workspace'})});
    await refresh();return created;
  });
  await page.locator(`[data-project-id="${object.id}"]`).click();
  await page.locator(`[data-object-subject="${object.id}"]`).click();
  await page.locator('.subject-pod-workspace').waitFor();
  await page.waitForFunction(()=>subjectPodState.config !== null);
  assert.equal(await page.locator('#fullscreenTitle').getAttribute('data-rename-id'),object.id);
  assert.equal(await page.locator('[data-open-create-pod]').count(),1);
  await page.locator('#fullscreenTitle').fill('Retained Subject');
  await page.locator('#fullscreenTitle').press('Enter');
  await page.waitForFunction(id=>state.subjects.some(item=>item.id===id&&item.name==='Retained Subject'),object.id);
  await page.screenshot({path:directory+'/subject-without-server-agents.png'});
  await page.locator('#closeFullscreen').click();
  await page.locator('[data-view="pods"]').click();
  assert.ok(await page.locator('#podsPageList').isVisible());
  assert.equal(await page.locator('#podsCount').textContent(),'0 of 0');
  await page.locator('[data-view="documentation"]').click();
  await page.locator('#documentationSearch').fill('Agent Nodes');
  assert.ok(await page.locator('#documentationEmpty').isVisible());
  await page.locator('#documentationSearch').press('Escape');
  await page.evaluate(async id=>{await api(`/v1/subjects/${id}`,{method:'DELETE'});await refresh();},object.id);
  // Leave time for the live-log timer: there must be no retired approval polling.
  await page.waitForTimeout(3200);
  await page.setViewportSize({width:1440,height:1000});
};
