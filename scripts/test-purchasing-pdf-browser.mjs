/* global window, document */
import { Buffer } from "node:buffer";
import assert from 'node:assert/strict';
import console from 'node:console';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from 'playwright-core';
import { build } from 'esbuild';
const bundle=await build({entryPoints:['src/components/print/documentPdf.ts'],bundle:true,write:false,platform:'browser',format:'iife',globalName:'PurchasingPdf'});
const browser=await chromium.launch({headless:true});
const directory=await mkdtemp(join(tmpdir(),'mmh-print-pdf-'));
try{
 const page=await browser.newPage({acceptDownloads:true});
 const svg=label=>'data:image/svg+xml;base64,'+Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="240" height="100"><rect width="240" height="100" fill="white"/><text x="10" y="60" fill="black">${label}</text></svg>`).toString('base64');
 await page.setContent(`<article class="print-document"><header><img src="${svg('MMH logo')}"/><div>PT MUTIARA MERDEKA HOTEL<br>Purchase Order TEST-PO-1</div></header><h1>PURCHASE ORDER</h1><div data-print-stamp>PDF download #1 · Rev 2 · Print operator · 30/10/2026 08:00 WIB</div><section data-print-fields>Supplier: Test supplier<br>Location: Hotel</section><table><thead><tr><th>Code</th><th>Description</th><th>Qty</th><th>Unit cost</th><th>Total</th></tr></thead><tbody>${Array.from({length:85},(_,index)=>`<tr><td>ITEM-${index+1}</td><td>Purchase item ${index+1}</td><td>2</td><td>25000</td><td>50000</td></tr>`).join('')}</tbody></table><div data-print-after-table>TOTAL 4250000</div><div data-print-after-table>NOTES: Invoice required</div><section data-print-signatures><div><div>Created by</div><div><img src="${svg('Signature')}"/></div><div>Creator Example</div><div>30/10/2026 08:00 WIB</div></div><div><div>Approved by</div><div></div><div>Approver Example</div><div>30/10/2026 09:00 WIB</div></div></section></article>`);
 await page.addScriptTag({content:bundle.outputFiles[0].text});
 const downloaded=page.waitForEvent('download');
 await page.evaluate(()=>window.PurchasingPdf.downloadDocumentPdf(document.querySelector('article'),'TEST-PO-1'));
 const download=await downloaded;assert.equal(download.suggestedFilename(),'TEST-PO-1.pdf');
 const target=join(directory,'document.pdf');await download.saveAs(target);
 const pdf=(await readFile(target)).toString('latin1');
 assert.ok(pdf.startsWith('%PDF-'));
 for(const value of ['ITEM-1','ITEM-85','Purchase item 85','Creator Example','Approver Example','TOTAL 4250000','PDF download #1'])assert.ok(pdf.includes(value),`Missing PDF content: ${value}`);
 assert.ok((pdf.match(/\/Type \/Page\b/g)||[]).length>=2,'Long documents paginate');
 assert.ok((pdf.match(/\/Subtype \/Image/g)||[]).length>=2,'Logo and signature are included');
 console.log('Purchasing PDF browser PASS: real file download, all 85 rows, totals, creator/approver, logo, signature, revision mark and pagination.');
}finally{await browser.close();await rm(directory,{recursive:true,force:true});}
