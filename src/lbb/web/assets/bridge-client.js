// Thin async wrapper over window.pywebview.api. When pywebview is absent
// (plain browser dev), falls back to a tiny in-memory mock so the UI still
// renders. The mock is dev-only and never ships behaviour the backend lacks.
const API = (() => {
  const real = () => window.pywebview && window.pywebview.api;
  const wrap = (name) => (...args) => {
    const api = real();
    if (api && api[name]) return api[name](...args);
    return Promise.resolve(MOCK[name] ? MOCK[name](...args) : null);
  };
  const MOCK = {
    list_orders: () => ({ orders: [], error: null }),
    get_order: () => null,
    engrave_side: () => ({ ok: true, status: "not_done_yet", progress: { done: 1, total: 1 } }),
    set_status: (_o, s) => ({ ok: true, status: s }),
    ship_order: () => ({ ok: true }),
    flag_revision: () => ({ ok: true }),
    open_amazon: () => ({ ok: true }),
    open_label: () => ({ ok: true }),
    print_label: () => ({ ok: true }),
    lightburn_status: () => ({ running: false }),
    product_image: () => ({ ok: false }),
  };
  return {
    listOrders: wrap("list_orders"),
    getOrder: wrap("get_order"),
    engraveSide: wrap("engrave_side"),
    setStatus: wrap("set_status"),
    shipOrder: wrap("ship_order"),
    flagRevision: wrap("flag_revision"),
    openAmazon: wrap("open_amazon"),
    openLabel: wrap("open_label"),
    printLabel: wrap("print_label"),
    lightburnStatus: wrap("lightburn_status"),
    productImage: wrap("product_image"),
  };
})();
