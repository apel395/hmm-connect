import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
globalThis.window={localStorage:{getItem:()=>null}};
async function render(entry, allowed, data={}) {
 const stubs={
  'react-router-dom': 'export const useSearchParams=()=>[new URLSearchParams(),()=>{}];export const useNavigate=()=>()=>{}; export const useParams=()=>({id:"1"}); export const Link=({children})=>children;',
  '@tanstack/react-query': `export const useQuery=()=>({data:${JSON.stringify(data)},isLoading:false}); export const useMutation=()=>({}); export const useQueryClient=()=>({});`,
  '@/hooks/useAuthorization': `export default ()=>({isSuperuser:()=>${allowed},hasPermission:()=>${allowed}});`,
  '@/modules/master/warehouses/hooks/useWarehouses':'export const useWarehouses=()=>({data:[]});',
  '@/modules/admin/organization/api':'export const listBusinessUnits=()=>[];export const listDepartments=()=>[];export const listLocations=()=>[];',
  '../useInventory':'export const useInventory=()=>({data:{items:[],summary:{stock_lines:212,stock_value:38521422,low_stock:0},total_pages:1,total_items:212}});',
  '@/api/client':'export default {};',
  '@/components/workspace/WorkspaceBackButton':'export default ()=>null;',
  '@/components/workspace/DataWorkspace':'import React from "react";const Box=p=>React.createElement("div",null,p.children);export default Box;export const WorkspaceFilters=p=>React.createElement("div",null,React.createElement("button",{type:"button","aria-label":p.label||"Filters"}),p.children);',
  '@/components/common/ModuleSummary':'import React from "react";const Summary=p=>React.createElement("div",null,(p.metrics||[]).map(m=>React.createElement("span",{key:m.label},m.label," ",m.value)));export default Summary;export const ModuleSummary=Summary;',
  '@/components/ui/Loading':'import React from "react";const Load=p=>React.createElement("div",null,p.message);export default Load;export const Loading=Load;',
  '@/components/ui/Empty':'import React from "react";const Blank=p=>React.createElement("div",null,p.title,p.description);export default Blank;export const Empty=Blank;',
  '@/components/ui/Badge':'import React from "react";const Tag=p=>React.createElement("span",null,p.children);export default Tag;export const Badge=Tag;',
  '@/components/form/ProductCombobox':'export default ()=>null;',
  '@/components/form/SearchableSelect':'export default ()=>null;',
  '@/components/print/InventoryPrintButton':'export default ()=>null;',
 };
 const result=await build({entryPoints:[entry],alias:{'@':path.resolve('src')},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'stubs',setup(b){b.onResolve({filter:/.*/},a=>stubs[a.path]?{path:a.path,namespace:'stub'}:null);b.onLoad({filter:/.*/,namespace:'stub'},a=>({contents:stubs[a.path],loader:'jsx'}));}}]});
 const m={exports:{}};new Function('module','exports','require',result.outputFiles[0].text)(m,m.exports,require);
 return renderToStaticMarkup(createElement(m.exports.default));
}
for(const allowed of [true,false]){
 const html=await render('src/modules/warehouse/store-request/StoreRequestPage.tsx',allowed,[]);
 assert.equal(html.includes('Create Store Request'),allowed);
 assert.doesNotMatch(html,/_canCreate|: undefined/);
 assert.match(html,/aria-label="Filters"/);
}
const html=await render('src/modules/warehouse/stock-opname/StockOpnamePrintPage.tsx',false,{opname_number:'SO-1',blind_count:true,items:[{id:1,product_code:'1-1',product_name:'Item A',system_quantity:999,uom:'PCS'}]});
assert.match(html,/PHYSICAL COUNT/);
assert.doesNotMatch(html,/SYSTEM QTY|999|Counted By|Entered By|OFFICER|DOCUMENT AUTHENTICITY/);
const detail = await render('src/modules/warehouse/stock-opname/StockOpnameDetailPage.tsx', true, {id:1,opname_number:'SO-1',count_date:'2026-10-15',status:'DRAFT',blind_count:true,items:[{id:1,product_code:'1-1',product_name:'Item A',uom:'PCS',physical_quantity:null}],allowed_actions:{can_edit:true}});
assert.doesNotMatch(detail,/>System<|>Variance<|>Unit Cost<|>Variance Value<|Use System/);
assert.match(detail,/Physical/);
const stock = await render('src/modules/warehouse/inventory/pages/InventoryPage.tsx',true,[]);
assert.match(stock,/stock lines/);assert.match(stock,/38.521.422/);assert.match(stock,/Account totals/);
assert.doesNotMatch(stock,/Closing Stock Lines|Reorder Required at Closing|Totals by Inventory Account|Movement class/);
console.log('PASS: create action is permission-gated with no JSX text; icon filters; blind count print has no system quantity or officer fields.');
