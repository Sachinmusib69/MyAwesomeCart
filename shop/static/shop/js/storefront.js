(function () {
  const cartKey = 'cart';
  const cartBadge = document.getElementById('cart');

  function readCart() {
    try {
      const value = JSON.parse(localStorage.getItem(cartKey) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (error) {
      return {};
    }
  }

  function updateBadge() {
    if (!cartBadge) return;
    const cart = readCart();
    const count = Object.values(cart).reduce(function (total, entry) {
      const quantity = Array.isArray(entry) ? Number(entry[0]) : Number(entry);
      return total + (Number.isFinite(quantity) && quantity > 0 ? quantity : 0);
    }, 0);
    cartBadge.textContent = String(count);
  }

  const menuButton = document.querySelector('.nav-toggle');
  const menu = document.getElementById('site-menu');
  if (menuButton && menu) {
    menuButton.addEventListener('click', function () {
      const isOpen = menu.classList.toggle('is-open');
      menuButton.setAttribute('aria-expanded', String(isOpen));
    });
  }

  window.addEventListener('cart:updated', updateBadge);
  window.addEventListener('storage', updateBadge);

  document.addEventListener('click', function (event) {
    const button = event.target.closest('.js-add-cart');
    if (!button) return;

    const id = 'pr' + button.dataset.productId;
    const cart = readCart();
    const existing = cart[id];
    const quantity = Array.isArray(existing) ? Number(existing[0]) || 0 : Number(existing) || 0;
    cart[id] = [quantity + 1, button.dataset.productName, Number(button.dataset.productPrice) || 0];
    localStorage.setItem(cartKey, JSON.stringify(cart));
    updateBadge();

    const previousText = button.textContent;
    button.textContent = 'Added';
    window.setTimeout(function () { button.textContent = previousText; }, 1000);
  });

  updateBadge();
}());
