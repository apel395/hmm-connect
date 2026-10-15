import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
async function render(entry, allowed, data={}) {
 const stubs={
  'react-router-dom': 'export const useNavigate=()=>()=>{}; export const useParams=()=>({id:"1"}); export const Link=({children})=>children;',
  '@tanstack/react-query': `export const useQuery=()=>({data:${JSON.stringify(data)},isLoading:false}); export const useMutation=()=>({}); export const useQueryClient=()=>({});`,
  '@/hooks/useAuthorization': `export default ()=>({isSuperuser:()=>${allowed},hasPermission:()=>${allowed}});`,
  '@/modules/master/warehouses/hooks/useWarehouses':'export const useWarehouses=()=>({data:[]});',
  '@/modules/admin/organization/api':'export const listBusinessUnits=()=>[];export const listDepartments=()=>[];export const listLocations=()=>[];',
  '@/api/client':'export default {};',
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
console.log('PASS: create action is permission-gated with no JSX text; icon filters; blind count print has no system quantity or officer fields.');
