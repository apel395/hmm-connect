/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
async function run(){
 const b=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/components/navigation/navigationConfig.ts'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime']});
 const m={exports:{}};new Function('module','exports','require',b.outputFiles[0].text)(m,m.exports,n=>req(n));const visible=m.exports.visibleNavigation;
 const user=(name,codes=[])=>({roles:[{name,permissions:codes.map(code=>({code}))}]});
 const paths=u=>visible(u).flatMap(g=>g.children??[g]).map(c=>c.url);
 assert.ok(paths(user('SYSTEM_ADMINISTRATOR')).includes('/settings/pos'));
 const finance=paths(user('OTHER_ADMIN',['pos.view','finance.manage']));assert.ok(finance.includes('/pos'));assert.ok(finance.includes('/settings/pos'));assert.ok(!finance.includes('/users'));
 const cashier=paths(user('CASHIER',['pos.view','pos.sell']));assert.ok(cashier.includes('/pos'));assert.ok(!cashier.includes('/settings/pos'));
 const config=paths(user('CUSTOM_ADMIN',['pos.view','admin.settings.manage']));assert.ok(config.includes('/settings/pos'));
 const noPos=paths(user('CUSTOM_ADMIN',['finance.manage']));assert.ok(!noPos.includes('/pos'));assert.ok(!noPos.includes('/settings/pos'));
 assert.ok(!paths(user('ADMIN',['products.view'])).includes('/pos'),'a display role name never grants POS access');
 console.log('POS navigation PASS: canonical Admin, custom permission profiles and combined POS/configuration permission gates.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
