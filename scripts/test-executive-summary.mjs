import assert from "node:assert/strict";
import path from "node:path";
import console from "node:console";
import { createRequire } from "node:module";
import { build } from "esbuild";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
const result = await build({entryPoints:["src/modules/dashboard/ExecutiveViewPage.tsx"],alias:{"@":path.resolve("src")},bundle:true,write:false,platform:"node",format:"cjs",jsx:"automatic",external:["react","react/jsx-runtime"],plugins:[{name:"browser-services",setup(build){
  build.onResolve({filter:/^(@\/api\/client|@\/store\/auth|react-router-dom)$/},args=>({path:args.path,namespace:"mock"}));
  build.onLoad({filter:/.*/,namespace:"mock"},args=>({contents:args.path==="react-router-dom"?'import {createElement} from "react"; export const Link=({to,children,...props})=>createElement("a",{href:to,...props},children);':'export default {};',loader:"js"}));
}}]});
const module = {exports:{}};
new Function("module","exports","require",result.outputFiles[0].text)(module,module.exports,require);
const amount = value=>({current:String(value),budget:null,last_month:null,last_year:null,variance:null});
const pnl={scope:{location_id:8,business_unit_id:2,department_id:7},presentation_rows:["REVENUE","BEBAN","GOP","NOP"].map((key,index)=>({key,periods:{MTD:amount([100,120,-20,-20][index]),YTD:amount([200,240,-40,-40][index])}}))};
const balance={section_totals:Object.fromEntries(["ASSETS","LIABILITIES","EQUITY"].map(section=>[section,{YTD:amount(section==="EQUITY"?-40:100)}]))};
const markup=renderToStaticMarkup(createElement(module.exports.ExecutiveSummary,{pnl,balance,period:"YTD",asOf:"2026-01-31"}));
assert.match(markup,/-20\.0%/);
assert.doesNotMatch(markup,/<a\b|href=|account_ids/);
assert.match(markup,/Last year/);
assert.match(markup,/Budget —/);
pnl.presentation_rows[0].periods.YTD=amount(0);
const empty=renderToStaticMarkup(createElement(module.exports.ExecutiveSummary,{pnl,balance,period:"YTD",asOf:"2026-01-31"}));
assert.doesNotMatch(empty,/NaN|Infinity/);
console.log("Executive summary: summary-only output, negative margin, absent budget and zero revenue passed.");
