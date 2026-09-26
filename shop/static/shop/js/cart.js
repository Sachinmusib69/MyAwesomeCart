(function () {
  const cartKey = 'cart';
  const catalogNode = document.getElementById('product-catalog');
  const catalog = catalogNode ? JSON.parse(catalogNode.textContent) : {};
  const lines = document.getElementById('cart-items');
  const emptyState = document.getElementById('cart-empty');
  const summary = document.getElementById('cart-summary');
  const checkoutLink = document.getElementById('checkout-link');
  const countNode = document.getElementById('summary-count');
  const subtotalNode = document.getElementById('summary-subtotal');
  const totalNode = document.getElementById('summary-total');
  const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

  function readCart() {
    try {
      const cart = JSON.parse(localStorage.getItem(cartKey) || '{}');
      return cart && typeof cart === 'object' && !Array.isArray(cart) ? cart : {};
    } catch (error) {
      return {};
    }
  }

  function saveCart(cart) {
    localStorage.setItem(cartKey, JSON.stringify(cart));
    window.dispatchEvent(new Event('cart:updated'));
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function render() {
    const saved = readCart();
    const cart = {};
    let itemCount = 0;
    let subtotal = 0;
    lines.replaceChildren();

    Object.entries(saved).forEach(function ([key, value]) {
      const product = catalog[key];
      if (!product) return;
      const rawQuantity = Array.isArray(value) ? Number(value[0]) : Number(value);
      const quantity = Math.min(99, Math.max(0, Math.floor(rawQuantity || 0)));
      if (!quantity) return;

      const price = Number(product.price) || 0;
      cart[key] = [quantity, product.name, price];
      itemCount += quantity;
      subtotal += quantity * price;

      const row = makeElement('article', 'cart-line');
      row.dataset.productId = key;
      const imageBox = makeElement('div', 'cart-line-image');
      if (product.image) {
        const image = document.createElement('img');
        image.src = product.image;
        image.alt = product.name;
        image.loading = 'lazy';
        imageBox.appendChild(image);
      } else {
        imageBox.appendChild(makeElement('span', 'product-placeholder', '✦'));
      }

      const details = makeElement('div', 'cart-line-details');
      details.appendChild(makeElement('h3', 'cart-line-name', product.name));
      details.appendChild(makeElement('p', 'cart-line-unit', currency.format(price) + ' each'));
      const controls = makeElement('div', 'cart-line-controls');
      const quantityControl = makeElement('div', 'quantity-control');
      quantityControl.setAttribute('aria-label', 'Quantity for ' + product.name);
      const decrease = makeElement('button', '', '−');
      decrease.type = 'button';
      decrease.dataset.cartAction = 'decrease';
      decrease.setAttribute('aria-label', 'Decrease quantity');
      const quantityValue = makeElement('span', 'quantity-value', String(quantity));
      const increase = makeElement('button', '', '+');
      increase.type = 'button';
      increase.dataset.cartAction = 'increase';
      increase.setAttribute('aria-label', 'Increase quantity');
      quantityControl.append(decrease, quantityValue, increase);
      const remove = makeElement('button', 'cart-remove', 'Remove');
      remove.type = 'button';
      remove.dataset.cartAction = 'remove';
      controls.append(quantityControl, remove);
      details.appendChild(controls);

      const lineTotal = makeElement('div', 'cart-line-total', currency.format(quantity * price));
      row.append(imageBox, details, lineTotal);
      lines.appendChild(row);
    });

    const hasItems = Object.keys(cart).length > 0;
    if (JSON.stringify(cart) !== JSON.stringify(saved)) saveCart(cart);
    emptyState.hidden = hasItems;
    summary.hidden = !hasItems;
    checkoutLink.setAttribute('aria-disabled', String(!hasItems));
    countNode.textContent = String(itemCount);
    subtotalNode.textContent = currency.format(subtotal);
    totalNode.textContent = currency.format(subtotal);
  }

  lines.addEventListener('click', function (event) {
    const button = event.target.closest('[data-cart-action]');
    if (!button) return;
    const row = button.closest('[data-product-id]');
    const key = row && row.dataset.productId;
    const cart = readCart();
    if (!key || !cart[key]) return;

    if (button.dataset.cartAction === 'remove') {
      delete cart[key];
    } else {
      const current = Array.isArray(cart[key]) ? Number(cart[key][0]) : Number(cart[key]);
      const delta = button.dataset.cartAction === 'increase' ? 1 : -1;
      const quantity = Math.min(99, Math.max(1, Math.floor(current || 1) + delta));
      cart[key] = [quantity, catalog[key].name, Number(catalog[key].price) || 0];
    }
    saveCart(cart);
    render();
  });

  document.getElementById('clear-cart').addEventListener('click', function () {
    saveCart({});
    render();
  });

  window.addEventListener('storage', render);
  render();
}());
