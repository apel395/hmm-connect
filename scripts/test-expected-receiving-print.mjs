import assert from "node:assert/strict";
import console from "node:console";
import path from "node:path";
import { createRequire } from "node:module";
import { build } from "esbuild";
const require = createRequire(import.meta.url);

async function compile(entry) {
  const output=await build({entryPoints:[entry],alias:{"@":path.resolve("src")},bundle:true,write:false,platform:"node",format:"cjs",
    plugins:[{name:"expected-api",setup(b){
      b.onResolve({filter:/^@\/api\/client$/},()=>({path:"api",namespace:"fixture"}));
      b.onLoad({filter:/.*/,namespace:"fixture"},()=>({contents:"export default {get:(...args)=>globalThis.expectedApi(...args)}",loader:"js"}));
    }}]});
  const mod={exports:{}};
  new Function("module","exports","require",output.outputFiles[0].text)(mod,mod.exports,require);
  return mod.exports;
}
const {expectedReceivingReport}=await compile("src/modules/purchasing/goods-receipts/expectedReceivingPrint.ts");
const {renderInventoryPrint}=await compile("src/utils/inventoryPrint.ts");
const item={product_code:"1-500001",product_name:"Tomato <script>",uom:"KG",ordered_quantity:"10",received_quantity:"4",remaining_quantity:"6"};
const orders=[{id:1,po_number:"PO-1",supplier_name:"Supplier <test>",location_name:"Hotel",department_name:"F&B",expected_date:"2026-10-21",items:[item,{...item,product_code:"3-400001",uom:"PCS",remaining_quantity:2}]},
 {id:2,po_number:"PO-2",expected_date:"2026-10-22",items:[item]},
 {id:3,po_number:"PO-UNSCHEDULED",expected_date:null,items:[item]},
 {id:4,po_number:"PO-FULLY-RECEIVED",expected_date:"2026-10-21",items:[{...item,remaining_quantity:0}]}];
const filters={date_from:"2026-10-21",date_to:"2026-10-21"};
const report=expectedReceivingReport(orders,filters);
assert.equal(report.groups.length,1);
assert.equal(report.rowCount,2);
assert.equal(report.columns[0].label,"Item code");
assert.deepEqual(report.groups[0].rows[0],["1-500001","Tomato <script>","10","4","6","KG"]);
assert.equal(report.footer,undefined); // No misleading sum of KG and PCS.
assert.match(report.context,/2026-10-21/);
assert.equal(expectedReceivingReport(orders).groups.length,3);
assert.equal(expectedReceivingReport(orders,{},2).groups[0].title,"PO-2 · —");
assert.throws(()=>expectedReceivingReport(orders,filters,2),/no longer/);
assert.throws(()=>expectedReceivingReport(orders,filters,4),/no longer/);
assert.throws(()=>expectedReceivingReport(orders,{date_from:"2026-10-22",date_to:"2026-10-21"}),/From date/);
const html=renderInventoryPrint(report,"Receiving staff",new Date("2026-10-21T01:00:00Z"));
assert.match(html,/Expected Receiving/);assert.match(html,/Remaining/);assert.match(html,/WIB/);
assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
assert.match(html,/table-header-group/);assert.match(html,/Records: 2/);
const requests=[];
globalThis.expectedApi=(...args)=>{requests.push(args);return Promise.resolve({data:orders});};
const {goodsReceiptApi}=await compile("src/modules/purchasing/goods-receipts/api/goodsReceiptApi.ts");
await goodsReceiptApi.receivablePurchaseOrders(filters);
assert.deepEqual(requests[0],["/goods-receipts/receivable-purchase-orders",{params:filters}]);
delete globalThis.expectedApi;
console.log("Expected Receiving print: filtered complete list, single PO, fresh API dates, outstanding quantities, separate item codes, mixed units and escaped print metadata passed.");
