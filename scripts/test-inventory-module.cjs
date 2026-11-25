/* global require, __dirname, console, process, global */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const sourceFile = "src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx";
const source = fs.readFileSync(path.join(root, sourceFile), "utf8");

for (const token of [
  "DataWorkspace",
  "WorkspaceFilters",
  "ModuleSummary",
  "Loading",
  "Empty",
  "FORM_UI",
  "warehouseErrorMessage",
]) {
  assert.ok(source.includes(token), `Stock Movement Summary uses shared ${token}`);
}
assert.ok(source.includes('["inventory-period-report"'), "period report query key is preserved");
assert.ok(source.includes('"/inventory/period-report"'), "period report endpoint is preserved");
assert.ok(source.includes("ExportButton"), "filtered Excel export is preserved");
assert.ok(source.includes("InventoryPrintButton"), "authenticated report print is preserved");
assert.ok(!source.includes("quantity_totals_by_uom.map"), "per-UOM arithmetic strip is removed from the UI");

const fixture = {
  items: [],
  total_items: 0,
  total_pages: 1,
  summary: { opening_value: 1, in_value: 2, out_value: 3, closing_value: 4 },
  quantity_totals_by_uom: [
    { uom: "BALL", opening: 22, in_quantity: 0, out_quantity: 0, closing: 22 },
    { uom: "BKS", opening: 400, in_quantity: 0, out_quantity: 0, closing: 400 },
  ],
};

const componentStub = "import React from 'react';export default p=>React.createElement('div',null,p.children,p.title,p.message,p.label,p.value);";
const stubs = {
  "@tanstack/react-query": `export const useQuery=({queryKey})=>{const warehouses=queryKey[0]==='inventory-period-warehouses';const base={isLoading:false,isError:false,isFetching:false,error:null,refetch:async()=>{}};return warehouses?{...base,data:[{id:1,code:'WH',name:'Warehouse'}]}:{...base,data:${JSON.stringify(fixture)}};};`,
  "react-router-dom": "export const Link=({children})=>(children);",
  sonner: "export const toast={error:()=>{}};",
  "@/api/client": "export default {get:async()=>({data:[]})};",
  "@/modules/master/warehouses/api/warehouseApi": "export const warehouseApi={list:async()=>({data:[]})};",
  "@/utils/inventoryPrint": "export const collectReportPages=async()=>({items:[],summary:{}});export const printMoney=v=>String(v??0);export const printNumber=v=>String(v??0);",
  "@/utils/dateConstraints": "export const todayLocal=()=>'2026-11-25';",
  "@/components/common/ReportActions": "export const ExportButton=()=>null;",
  "@/components/print/InventoryPrintButton": componentStub,
  "@/components/reports/ReportUnitButtons": componentStub,
  "@/components/common/ModuleSummary": componentStub,
  "@/components/workspace/DataWorkspace": `import React from 'react';export default p=>React.createElement('div',null,p.children);export const WorkspaceFilters=p=>React.createElement('div',null,p.context,p.children);`,
  "@/config/formUi": "export const FORM_UI={controlBase:'control',density:{compact:{control:'compact'}}};",
  "@/modules/warehouse/errors": "export const warehouseErrorMessage=e=>String(e);",
  "@/components/ui/Card": componentStub,
  "@/components/ui/Button": componentStub,
  "@/components/ui/Empty": componentStub,
  "@/components/ui/Loading": componentStub,
};

async function render() {
  const result = await req("esbuild").build({
    absWorkingDir: root,
    entryPoints: [sourceFile],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    external: ["react", "react/jsx-runtime"],
    plugins: [{
      name: "inventory-fixtures",
      setup(builder) {
        builder.onResolve({ filter: /^@\/|^react-router-dom$|^sonner$|^@tanstack\/react-query$/ }, (args) => ({ path: args.path, namespace: "fixture" }));
        builder.onLoad({ filter: /.*/, namespace: "fixture" }, (args) => {
          const contents = stubs[args.path] || componentStub;
          return { loader: "js", contents };
        });
      },
    }],
  });
  const module = { exports: {} };
  new Function("require", "module", "exports", result.outputFiles[0].text)(req, module, module.exports);
  const React = req("react");
  const renderer = req("react-test-renderer");
  global.IS_REACT_ACT_ENVIRONMENT = true;
  let tree;
  await renderer.act(async () => {
    tree = renderer.create(React.createElement(module.exports.default));
  });
  const text = JSON.stringify(tree.toJSON());
  assert.ok(!text.includes("BALL:"), "UOM arithmetic totals do not render in the page");
  assert.ok(!text.includes("= 22"), "UOM closing arithmetic does not render in the page");
  assert.ok(text.includes("Stock Movement Summary"), "report heading still renders");
  await renderer.act(async () => tree.unmount());
}

(async () => {
  await render();
  console.log("Inventory module PASS: shared workspace shell, preserved report contract, no per-UOM arithmetic strip.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
