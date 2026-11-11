/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const root = require("node:path").resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const React = req("react");
const renderer = req("react-test-renderer");
global.IS_REACT_ACT_ENVIRONMENT = true;

global.__receipt = {
  id: 10, receipt_number: "GR-POSTED", status: "POSTED", source_type: "HISTORICAL_ENTRY",
  source_mode: "DIRECT", received_at: "2026-11-03T03:00:00Z", destination_type: "DIRECT_USE",
  supplier_name: "Supplier test", total_amount: 93000,
  items: [{ id: 1, product_name: "ALPUKAT", product_code: "1-600085", quantity: 3, uom: "Kg", unit_cost: 31000, line_total: 93000 }],
  supplier_invoice_id: 650, supplier_invoice_status: "DRAFT",
  allowed_actions: {
    can_edit: false, can_depost: true, can_post: false, can_return: false,
    can_correct_cost: true, can_print: true, can_manage_attachments: false, can_view_history: false,
  },
};
global.__allowBusinessAction = false;

async function run() {
  const bundle = await req("esbuild").build({
    absWorkingDir: root, tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/modules/purchasing/goods-receipts/pages/ReceivingDetailPage.tsx"],
    bundle: true, write: false, platform: "node", format: "cjs",
    external: ["react", "react/jsx-runtime"],
    plugins: [{ name: "mocks", setup(build) {
      build.onResolve({ filter: /^(?:@\/components\/|@\/modules\/|@\/hooks\/|@tanstack\/react-query|@radix-ui\/react-dropdown-menu|sonner|lucide-react|react-router-dom|\.\.\/hooks\/useGoodsReceipts|\.\.\/components\/EditReceivingDialog|\.\.\/\.\.\/components\/DocumentActivity)/ },
        args => ({ path: args.path, namespace: "mock" }));
      build.onLoad({ filter: /.*/, namespace: "mock" }, args => {
        let contents;
        if (args.path === "sonner") {
          contents = "export const toast={error:()=>{},success:()=>{}};";
        } else if (args.path === "lucide-react") {
          contents = "export const AlertTriangle=()=>null, RotateCcw=()=>null, Ellipsis=()=>null, FileCheck2=()=>null, FilePlus2=()=>null, Pencil=()=>null, PencilLine=()=>null, XCircle=()=>null, Search=()=>null;";
        } else if (args.path === "@radix-ui/react-dropdown-menu") {
          contents = "import React from 'react';const Wrap=p=>React.createElement('div',null,p.children);export const Root=Wrap,Trigger=Wrap,Portal=Wrap,Content=Wrap;export const Item=p=>React.createElement('button',{onClick:p.onSelect},p.children);";
        } else if (args.path.includes("useGoodsReceipts")) {
          contents = "export const useGoodsReceipt=()=>({data:globalThis.__receipt,isLoading:false});const action=()=>({isPending:false,mutate(){}});export const useDepostGoodsReceipt=()=>({isPending:false,mutate:p=>{globalThis.__depost=p;}});export const useReturnGoodsReceipt=()=>({isPending:false,mutate:id=>{globalThis.__returned=id;}});export const useApproveGoodsReceipt=action,useCorrectGoodsReceiptCosts=action,useCorrectHistoricalReceipt=action,usePostGoodsReceipt=action,useRejectGoodsReceipt=action,useSubmitGoodsReceipt=action;";
        } else if (args.path.includes("useAuthorization")) {
          contents = "export default ()=>({hasPermission:()=>true,isSuperuser:()=>true,canPerform:()=>globalThis.__allowBusinessAction});";
        } else if (args.path === "@tanstack/react-query") {
          contents = "export const useQueryClient=()=>({invalidateQueries:()=>{}});export const useMutation=()=>({isPending:false});";
        } else if (args.path.includes("supplier-invoices/api")) {
          contents = "export const prepareInvoiceFromReceipt=async()=>({});";
        } else if (args.path === "react-router-dom") {
          contents = "import React from 'react';export const useParams=()=>({id:'10'});export const useNavigate=()=>()=>{};export const Link=p=>React.createElement('a',{href:p.to},p.children);";
        } else if (args.path.endsWith("/Dialog")) {
          contents = "import React from 'react';export const DialogBody=p=>React.createElement('div',null,p.children);export const DialogContent=DialogBody,DialogFooter=DialogBody,DialogHeader=DialogBody,DialogTitle=DialogBody;export default p=>p.open?React.createElement('div',null,p.children):null;";
        } else if (args.path.endsWith("/Button")) {
          contents = "import React from 'react';export default p=>React.createElement('button',p,p.children);";
        } else {
          contents = "import React from 'react';export default p=>React.createElement('div',null,p.children);";
        }
        return { contents, loader: "js" };
      });
    } }],
  });

  const module = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(
    module, module.exports, name => req(name));
  let view;
  const mount = async () => renderer.act(async () => {
    view = renderer.create(React.createElement(module.exports.default));
  });
  const text = node => (node.children ?? []).map(child => typeof child === "string" ? child : text(child)).join("");
  const buttons = () => view.root.findAllByType("button");
  const button = label => buttons().find(node => text(node).trim() === label);

  await mount();
  assert.ok(button("Review Supplier Invoice"), "posted invoice draft is the next primary action");
  assert.equal(button("Edit Receiving"), undefined, "posted documents do not advertise blocked editing");
  assert.ok(button("Depost for Edit"), "authorized depost is discoverable under More");
  assert.ok(button("Correct Cost"), "cost correction remains accessible");
  assert.ok(view.root.findAllByProps({ role: "tab" }).some(node => text(node).includes("Received Items")));

  await renderer.act(async () => button("Depost for Edit").props.onClick());
  assert.ok(button("Depost and Edit").props.disabled, "depost still requires a reason");
  await renderer.act(async () => view.root.findByProps({ "aria-label": "Receiving depost reason" })
    .props.onChange({ target: { value: "Fix wrong item" } }));
  await renderer.act(async () => button("Depost and Edit").props.onClick());
  assert.deepEqual(global.__depost, { id: 10, reason: "Fix wrong item" });

  await renderer.act(async () => {
    view.root.findAllByProps({ role: "tab" }).find(node => text(node) === "Supplier Billing").props.onClick();
  });
  assert.ok(text(view.root).includes("Supplier Billing"), "billing tab remains available");
  await renderer.act(async () => {
    view.root.findAllByProps({ role: "tab" }).find(node => text(node).startsWith("Received Items")).props.onClick();
  });
  await renderer.act(async () => view.root.findByType("input").props.onChange({ target: { value: "BLENDER" } }));
  assert.ok(text(view.root).includes("No items match your search."), "item search filters the current document");
  await renderer.act(async () => view.unmount());

  global.__receipt.status = "DRAFT";
  global.__receipt.allowed_actions.can_depost = false;
  global.__receipt.allowed_actions.can_edit = true;
  global.__receipt.supplier_invoice_id = null;
  global.__receipt.supplier_invoice_status = null;
  await mount();
  assert.ok(button("Edit Receiving"), "draft edit is available when backend allows it");
  assert.equal(button("Depost for Edit"), undefined, "depost is absent for drafts");
  await renderer.act(async () => view.unmount());

  global.__receipt.status = "POSTED";
  global.__receipt.allowed_actions.can_edit = false;
  global.__receipt.allowed_actions.can_return = true;
  global.__receipt.allowed_actions.can_correct_cost = false;
  global.__allowBusinessAction = true;
  await mount();
  await renderer.act(async () => button("Return Goods").props.onClick());
  assert.ok(text(view.root).includes("Return Received Goods?"), "destructive return requires confirmation");
  await renderer.act(async () => buttons().filter(node => text(node).trim() === "Return Goods").at(-1).props.onClick());
  assert.equal(global.__returned, 10, "return reaches the existing backend action only after confirmation");
  await renderer.act(async () => view.unmount());

  console.log("Receiving UI PASS: contextual actions, hidden blocked Edit, depost reason, billing tabs, item search and return confirmation.");
}
run().catch(error => { console.error(error); process.exitCode = 1; });
