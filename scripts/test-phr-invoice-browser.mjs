/* global document */
import assert from 'node:assert/strict';
import console from 'node:console';
import {execFileSync} from 'node:child_process';
import process from 'node:process';
import {readFile} from 'node:fs/promises';
import {chromium} from 'playwright-core';
execFileSync(process.execPath,['scripts/test-phr-invoice.mjs','--preview']);
const logo=(await readFile('public/logoprint.jpeg')).toString('base64');
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({viewport:{width:1100,height:1200}});
 for(const name of ['phr-preview','phr-long-preview']) {
  const html=(await readFile(`/tmp/${name}.html`,'utf8')).replaceAll('/logoprint.jpeg',`data:image/jpeg;base64,${logo}`);
  await page.setContent(html,{waitUntil:'load'});
  await page.emulateMedia({media:'print'});
  await page.evaluate(()=>document.fonts.ready);
  const failures=await page.locator('.phr-invoice th,.phr-invoice td').evaluateAll(cells=>cells.filter(c=>c.scrollWidth>c.clientWidth+2).map(c=>c.textContent));
  assert.deepEqual(failures,[],`${name}: table cells overflow`);
  assert.ok(await page.locator('.phr-letterhead img').evaluate(i=>i.complete&&i.naturalWidth>0),'Logo loads');
  assert.ok(await page.locator('.phr-signature').evaluate(e=>e.getBoundingClientRect().height)>80,'Signature space retained');
  const buffer=await page.pdf({preferCSSPageSize:true,printBackground:true});
  const pdf=buffer.toString('latin1');
  const pages=(pdf.match(/\/Type \/Page\b/g)||[]).length;
  assert.ok(pdf.includes('/MediaBox [0 0 612 792]'),'Letter page matches source PDF');
  if(name==='phr-preview')assert.equal(pages,1,'Reference two-line invoice fits one page');
  else assert.ok(pages>=2,'Long invoices paginate');
 }
 console.log('PHR browser print PASS: Letter page, one-page reference, long invoice pagination, no table overflow, logo and signature space.');
} finally {await browser.close();}
