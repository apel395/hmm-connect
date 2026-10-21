import assert from "node:assert/strict";
import console from "node:console";
import path from "node:path";
import { createRequire } from "node:module";
import { build } from "esbuild";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
async function compile(entry) {
  const result = await build({
    entryPoints: [entry], alias: { "@": path.resolve("src") }, bundle: true,
    write: false, platform: "node", format: "cjs", jsx: "automatic",
    external: ["react", "react/jsx-runtime", "react-dom"],
    plugins: [{ name: "print-fixtures", setup(b) {
      b.onResolve({ filter: /^(@\/api\/client|@\/store\/auth|@tanstack\/react-query|react-router-dom)$/ }, args => ({ path: args.path, namespace: "fixture" }));
      b.onLoad({ filter: /.*/, namespace: "fixture" }, args => ({ loader: "js", contents:
        args.path === "@tanstack/react-query" ? "export const useQuery=()=>({data:globalThis.printFixture,isLoading:false,isError:false});" :
        args.path === "react-router-dom" ? "export const useParams=()=>({id:'1'});" :
        args.path === "@/store/auth" ? "export default select=>select({user:{full_name:'Print operator'}});" :
        "export default {get:async()=>({data:globalThis.printFixture})};",
      }));
    }}],
  });
  const mod = { exports: {} };
  new Function("module", "exports", "require", result.outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}

const { approvalPrintSignatures } = await compile("src/components/print/approvalSignatures.ts");
const when = "2026-10-21T01:30:00Z";
const actual = {level:1,name:"Store approval",status:"APPROVED",approver_name:"Actual approver",decided_at:when};
const wrongAsset = {...actual,signature_name:"Different signature owner",signature_image:"data:image/png;base64,WRONG"};
assert.equal(approvalPrintSignatures([wrongAsset])[0].name,"Actual approver");
assert.equal(approvalPrintSignatures([wrongAsset])[0].imageSrc,undefined);
assert.equal(approvalPrintSignatures([{...actual,signature_name:"  ACTUAL  APPROVER ",signature_image:"data:image/png;base64,VALID"}])[0].imageSrc,"data:image/png;base64,VALID");
for (const status of ["PENDING","WAITING","REJECTED"]) assert.deepEqual(approvalPrintSignatures([{...wrongAsset,status}]),[]);
for (const missing of [{approver_name:null},{decided_at:null}]) assert.equal(approvalPrintSignatures([{...actual,...missing,signature_name:"Actual approver",signature_image:"image"}])[0].imageSrc,undefined);
assert.equal(approvalPrintSignatures([{...actual,approver_name:null,signature_name:"Different signature owner"}])[0].name,"—");

globalThis.printFixture = {
  document_type:"Purchase order",po_number:"PO-1",sr_number:"SR-1",opname_number:"SO-1",
  request_date:"2026-10-21",order_date:"2026-10-21",count_date:"2026-10-21",status:"APPROVED",
  created_by_name:"Original inputter",created_at:when,printed_by:"Print operator",generated_at:when,
  items:[],approval_history:[wrongAsset,{...actual,level:2,status:"PENDING",approver_name:"Pending person"}],blind_count:true,
};
for (const [entry,props] of [
  ["src/modules/purchasing/print/PrintDocumentPage.tsx",{kind:"purchase-orders"}],
  ["src/modules/warehouse/store-request/StoreRequestPrintPage.tsx",{}],
  ["src/modules/warehouse/stock-opname/StockOpnamePrintPage.tsx",{}],
]) {
  const Page=(await compile(entry)).default;
  const html=renderToStaticMarkup(createElement(Page,props));
  assert.match(html,/Actual approver/);
  assert.match(html,/08[.:]30/);
  assert.match(html,/WIB/);
  assert.doesNotMatch(html,/Different signature owner|WRONG|Pending person/);
  assert.match(html,/Signature space/);
  if (!entry.includes("StockOpname")) assert.match(html,/Original inputter/);
}
delete globalThis.printFixture;
console.log("Approval prints: actual identity, owner matching, pending/rejected exclusion, creator, signature space and Jakarta date/time passed.");
