/* global document, getComputedStyle, innerWidth */
import assert from 'node:assert/strict';
import { readFile,writeFile,unlink } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright-core';
const root=process.cwd(),name='.roboto-font-qa',port=4197;
let server,browser;
try{
 await writeFile(`${root}/${name}.html`,`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><script type="module" src="/${name}.ts"></script></head><body class="font-sans"><main style="padding:16px"><h1>HMM Connect · Roboto</h1><p>Hotel &amp; Project Catering — Café</p><label>Supplier <input value="Pertamina Hulu Rokan"></label><button>Save Draft</button><select><option>Hotel</option></select><textarea>Billing address</textarea><table><thead><tr><th>Description</th><th>Amount</th></tr></thead><tbody><tr><td>Catering service · 1–15 January</td><td class="tabular-nums">Rp 516.179.829,00</td></tr></tbody></table><section role="dialog"><strong>Invoice preview</strong><p>Finance &amp; Accounting</p></section></main></body></html>`);
 await writeFile(`${root}/${name}.ts`,`import './src/styles/index.css';`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'ignore'});
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const external=[],requests=[];page.on('request',r=>{requests.push(r.url());if(!r.url().startsWith(`http://127.0.0.1:${port}`))external.push(r.url());});
 let ready=false;for(let i=0;i<60;i++){try{await page.goto(`http://127.0.0.1:${port}/${name}.html`);ready=true;break;}catch{await new Promise(r=>setTimeout(r,100));}}
 assert.ok(ready,'font preview server starts');
 await page.evaluate(async()=>{await Promise.all([document.fonts.load('400 13px Roboto'),document.fonts.load('500 13px Roboto'),document.fonts.load('700 20px Roboto'),document.fonts.load('italic 400 13px Roboto')]);await document.fonts.ready;});
 const result=await page.evaluate(()=>({loaded:document.fonts.check('400 13px Roboto'),families:['body','h1','input','button','select','textarea','td','[role="dialog"]'].map(s=>({selector:s,family:getComputedStyle(document.querySelector(s)).fontFamily})),numberVariant:getComputedStyle(document.querySelector('.tabular-nums')).fontVariantNumeric}));
 assert.ok(result.loaded);for(const row of result.families)assert.ok(row.family.includes('Roboto'),`${row.selector} uses Roboto`);
 assert.equal(result.numberVariant,'tabular-nums');assert.ok(requests.some(u=>u.includes('roboto-latin-wght-normal.woff2')));assert.ok(requests.some(u=>u.includes('roboto-latin-wght-italic.woff2')));assert.deepEqual(external,[],'font loads from the app origin');
 await page.emulateMedia({media:'print'});assert.ok((await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily)).includes('Roboto'));
 const pdf=await page.pdf({format:'A4'});assert.ok(pdf.toString('latin1').includes('Roboto'),'browser PDF embeds Roboto');
 await page.emulateMedia({media:'screen'});await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'controls remain within mobile viewport');
 const css=await readFile('src/styles/typography.css','utf8');assert.ok(css.includes('font-display: swap'));
 console.log('Roboto PASS: self-hosted regular/medium/bold/italic, form/table/dialog inheritance, tabular amounts, mobile and embedded browser PDF.');
}finally{await browser?.close();server?.kill();await Promise.all([unlink(`${root}/${name}.html`).catch(()=>{}),unlink(`${root}/${name}.ts`).catch(()=>{})]);}
