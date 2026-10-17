/* global require, __dirname, global, console, process, URL */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const { build } = require(root + '/node_modules/esbuild');
const axios = require(root + '/node_modules/axios/dist/node/axios.cjs');

(async () => {
  const requests = [];
  let mode = 'normal';
  global.__stockApi = axios.create({ adapter: async config => {
    const url = new URL(axios.getUri(config), 'https://stock.test');
    requests.push(url);
    if (url.pathname === '/inventory') {
      const page = Number(url.searchParams.get('page'));
      const rows = mode === 'empty-stock' ? [] : page === 1
        ? [{ product_id: 1, warehouse_id: 5, quantity: 0 }, { product_id: 2, warehouse_id: 5, quantity: -2 }, { product_id: 3, warehouse_id: 3, quantity: 10 }]
        : [{ product_id: 6021, product_code: '1-800034', product_name: 'AMRIS', uom: 'PCS', warehouse_id: 5, quantity: '40.0000' }];
      return { data: { items: rows, total_pages: mode === 'empty-stock' ? 1 : 2 }, status: 200, statusText: 'OK', headers: {}, config };
    }
    // Model FastAPI's repeated list[int] query parameter contract.
    const ids = url.searchParams.getAll('product_ids').map(Number);
    const warehouse = Number(url.searchParams.get('warehouse_id'));
    if (mode === 'error') throw new Error('Warehouse access denied');
    const data = mode === 'incomplete' ? [] : mode === 'invalid' ? [{ product_id: 6021, available_stock: 'not-a-number' }] : ids.map(id => ({ product_id: id, available_stock: warehouse === 5 && id === 6021 ? '40.0000' : 0 }));
    return { data, status: 200, statusText: 'OK', headers: {}, config };
  }});
  const compiled = await build({ absWorkingDir: root, tsconfig: root + '/tsconfig.app.json',
    entryPoints: ['src/modules/warehouse/store-request/api.ts'], bundle: true, write: false, platform: 'node', format: 'cjs',
    plugins: [{ name: 'api', setup(builder) {
      builder.onResolve({ filter: /^@\/api\/client$/ }, () => ({ path: 'client', namespace: 'mock' }));
      builder.onLoad({ filter: /.*/, namespace: 'mock' }, () => ({ contents: 'export default globalThis.__stockApi;' }));
    }}] });
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled.outputFiles[0].text)(module, module.exports, require);
  const { storeRequestApi } = module.exports;
  const rumin = await storeRequestApi.availability(5, [6021, 4708, 6021]);
  assert.equal(Number(rumin.data.find(row => row.product_id === 6021).available_stock), 40);
  assert.deepEqual(requests[0].searchParams.getAll('product_ids'), ['6021', '4708']);
  assert.equal(requests[0].searchParams.has('product_ids[]'), false);
  assert.equal(requests[0].searchParams.get('warehouse_id'), '5');
  const other = await storeRequestApi.availability(3, [6021]);
  assert.equal(other.data[0].available_stock, 0, 'a real zero in another warehouse remains zero');
  mode = 'incomplete';
  await assert.rejects(storeRequestApi.availability(5, [6021]), /stock could not be read/);
  mode = 'invalid';
  await assert.rejects(storeRequestApi.availability(5, [6021]), /stock could not be read/);
  mode = 'error';
  await assert.rejects(storeRequestApi.availability(5, [6021]), /access denied/);
  mode = 'normal';
  const stocked = await storeRequestApi.stockedItems(5, 'amris');
  assert.deepEqual(stocked, [{ id: 6021, code: '1-800034', name: 'AMRIS', uom: 'PCS' }]);
  assert.equal(requests.at(-1).searchParams.get('search'), 'amris');
  assert.equal(requests.at(-1).searchParams.get('warehouse_id'), '5');
  assert.equal(requests.at(-1).searchParams.get('page'), '2', 'later positive stock is not lost after an empty/negative page');
  mode = 'empty-stock';
  assert.deepEqual(await storeRequestApi.stockedItems(5), [], 'empty stock returns no products, never the global catalog');
  console.log('PASS: AMRIS stock 40, repeated item IDs, warehouse isolation, real zero, incomplete and failed lookup rejection.');
})().catch(error => { console.error(error); process.exitCode = 1; });
