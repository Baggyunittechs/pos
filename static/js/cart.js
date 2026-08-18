class CartLoader {
    constructor() {
        this.cartLeft = document.querySelector('.cart-left');
        this.subtotalEl = document.querySelector('.summary-value');
        this.totalEl = document.querySelector('.summary-total .summary-value');
        this.clearCartBtn = document.querySelector('.clear-cart-btn');
        this.checkoutBtn = document.querySelector('.whatsapp-btn');

        this.items = [];
        this.total = 0;
        this.updating = false;
        this.toaster = document.getElementById('toaster');


        this.video = document.getElementById('camera');
        this.canvas = document.getElementById('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.scanStatus = document.getElementById('scanStatus');
        this.scanStartBtn = document.getElementById('scanStartBtn');
        this.scanStopBtn = document.getElementById('scanStopBtn');
        this.scanInterval = null;
        this.cameraStream = null;
        this.isScanning = false;
        this.scannedBarcodes = [];
    }


    async startCamera() {
        try {
            this.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" }
            });
            this.video.srcObject = this.cameraStream;
            this.video.classList.add('active');
            return true;
        } catch (error) {
            console.error('Camera error:', error);
            this.updateScanStatus('error', 'Camera access denied');
            return false;
        }
    }

    async scanFrame() {
        if (this.video.readyState !== this.video.HAVE_ENOUGH_DATA) return;

        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        this.ctx.drawImage(this.video, 0, 0);

        this.canvas.toBlob(async (blob) => {
            const formData = new FormData();
            formData.append('image', blob);

            try {
                const response = await fetch('/api/barcode/scan', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.status === 'success') {
                    this.updateScanStatus('found', 'Product found');
                    await this.fetchCart();
                    this.showToaster(result.product.name + ' added to cart', 'success');
                } else if (result.status === 'duplicate') {
                    this.updateScanStatus('duplicate', 'Already scanned');
                } else if (result.status === 'not_found') {
                    this.updateScanStatus('not_found', 'barcode detected. Product not in database');

                } else {
                    this.updateScanStatus('scanning', 'Scanning...');
                }
            } catch (error) {
                console.error('Scan error:', error);
            }
        }, 'image/jpeg');
    }

    updateScanStatus(type, message) {
        if (!this.scanStatus) return;
        this.scanStatus.className = 'scanner-status ' + type;
        this.scanStatus.textContent = message;
    }

    async startScanner() {
        if (this.isScanning) return;

        if (!this.cameraStream) {
            const started = await this.startCamera();
            if (!started) return;
        }

        this.isScanning = true;
        this.scanStartBtn.disabled = true;
        this.scanStopBtn.disabled = false;
        this.updateScanStatus('scanning', 'Scanning...');

        await this.scanFrame();
        this.scanInterval = setInterval(() => this.scanFrame(), 1000);
    }

    stopScanner() {
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }

        this.isScanning = false;
        this.scanStartBtn.disabled = false;
        this.scanStopBtn.disabled = true;
        this.updateScanStatus('idle', 'Stopped');

        if (this.cameraStream) {
            this.cameraStream.getTracks().forEach(track => track.stop());
            this.cameraStream = null;
            this.video.classList.remove('active');
        }
    }
    showToaster(message, type = 'success') {
        if (!this.toaster) return;

        this.toaster.innerHTML = '';

        const icon = document.createElement('i');
        icon.className = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
        this.toaster.appendChild(icon);

        const textSpan = document.createElement('span');
        textSpan.textContent = message;
        this.toaster.appendChild(textSpan);

        this.toaster.className = '';
        this.toaster.classList.add(type);
        this.toaster.classList.add('show');

        clearTimeout(this.toaster._timeout);
        this.toaster._timeout = setTimeout(() => {
            this.toaster.classList.remove('show');
        }, 3000);
    }

    injectStyles() {
        if (document.getElementById('cart-spinner-styles')) return;
        const style = document.createElement('style');
        style.id = 'cart-spinner-styles';
        style.textContent = `
            .qty-spinner {
                display: inline-block;
                width: 18px;
                height: 18px;
                border: 2px solid #e0e0e0;
                border-top-color: #0E0E10;
                border-radius: 50%;
                animation: spinQty 0.6s linear infinite;
                vertical-align: middle;
            }
            @keyframes spinQty {
                to { transform: rotate(360deg); }
            }
            .qty-num.updating {
                opacity: 0.4;
                pointer-events: none;
            }
            .qty-btn.disabled {
                opacity: 0.4;
                pointer-events: none;
                cursor: not-allowed;
            }
            .cart-item.updating {
                opacity: 0.6;
                pointer-events: none;
            }
            .empty-cart-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 60px 20px;
                text-align: center;
                background: #f9f9f9;
                border-radius: 12px;
                border: 2px dashed #e0e0e0;
                min-height: 300px;
            }
            .empty-cart-container svg {
                width: 80px;
                height: 80px;
                color: #ccc;
                margin-bottom: 20px;
            }
            .empty-cart-container h3 {
                font-size: 1.2rem;
                color: #333;
                margin: 0 0 8px 0;
            }
            .empty-cart-container p {
                color: #888;
                font-size: 0.95rem;
                margin: 0;
            }
            .empty-cart-container a {
                display: inline-block;
                margin-top: 20px;
                background: #0E0E10;
                color: white;
                padding: 12px 32px;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
    }

    // Fetch cart from API
    async fetchCart() {
        try {
            const response = await fetch('/api/cart');
            const data = await response.json();
            this.items = data.items || [];
            this.total = data.total || 0;
            this.renderCart();

            if (window.updateCartBadge) {
                window.updateCartBadge();
            }
        } catch (error) {
            console.error('Failed to load cart:', error);
            this.showError();
        }
    }

    renderCart() {
        if (!this.cartLeft) return;
        const existingItems = this.cartLeft.querySelectorAll('.cart-item');
        existingItems.forEach(el => el.remove());
        const emptyState = this.cartLeft.querySelector('.empty-cart-container');
        if (emptyState) emptyState.remove();

        if (!this.items || this.items.length === 0) {
            this.showEmpty();
            this.subtotalEl.textContent = 'KES 0';
            this.totalEl.textContent = 'KES 0';
            this.clearCartBtn.style.display = 'none';
            return;
        }

        this.clearCartBtn.style.display = '';
        this.updateTotals();

        this.items.forEach((item, index) => {
            this.renderItem(item, index);
        });

        this.attachEventListeners();
    }

    renderItem(item, index) {
        if (!item || !item.product) return;

        const product = item.product;
        const cardHTML = `
            <div class="cart-item" data-index="${index}" data-id="${product.id || product.barcode}" data-size="${item.size || 'M'}">
                <div class="item-image">
                    <img src="${product.image || product.main_image || 'https://via.placeholder.com/80'}" alt="${product.name}" loading="lazy" onerror="this.style.display='none'">
                </div>
                <div class="item-details">
                    <h2 class="item-name">${product.name}</h2>
                    <p class="item-price">KES ${product.price.toLocaleString()}</p>
                    <p class="item-size" style="font-size:0.85rem;color:#888;margin:0 0 12px 0;">Size: ${item.size || 'M'}</p>
                    <div class="item-actions">
                        <div class="quantity-selector">
                            <button type="button" class="qty-btn decrease" data-id="${product.id || product.barcode}" data-size="${item.size || 'M'}">−</button>
                            <span class="qty-num" data-id="${product.id || product.barcode}" data-size="${item.size || 'M'}">${item.quantity}</span>
                            <button type="button" class="qty-btn increase" data-id="${product.id || product.barcode}" data-size="${item.size || 'M'}">+</button>
                        </div>
                        <button type="button" class="delete-btn" data-id="${product.id || product.barcode}" data-size="${item.size || 'M'}" aria-label="Remove item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="trash-icon">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;

        this.cartLeft.insertAdjacentHTML('beforeend', cardHTML);
    }

    attachEventListeners() {
        if (!this.cartLeft) return;

        this.cartLeft.querySelectorAll('.decrease').forEach(btn => {
            btn.removeEventListener('click', this.handleDecrease);
            btn.addEventListener('click', this.handleDecrease.bind(this));
        });

        this.cartLeft.querySelectorAll('.increase').forEach(btn => {
            btn.removeEventListener('click', this.handleIncrease);
            btn.addEventListener('click', this.handleIncrease.bind(this));
        });

        this.cartLeft.querySelectorAll('.delete-btn').forEach(btn => {
            btn.removeEventListener('click', this.handleDelete);
            btn.addEventListener('click', this.handleDelete.bind(this));
        });
    }

    handleDecrease(e) {
        if (this.updating) return;
        const btn = e.currentTarget;
        const id = btn.dataset.id;
        const size = btn.dataset.size;
        const qtyEl = btn.closest('.quantity-selector').querySelector('.qty-num');
        const currentQty = parseInt(qtyEl.textContent);

        if (currentQty > 1) {
            this.updateQuantity(id, size, currentQty - 1, qtyEl);
        } else {
            this.removeItem(id, size);
        }
    }

    handleIncrease(e) {
        if (this.updating) return;
        const btn = e.currentTarget;
        const id = btn.dataset.id;
        const size = btn.dataset.size;
        const qtyEl = btn.closest('.quantity-selector').querySelector('.qty-num');
        const currentQty = parseInt(qtyEl.textContent);
        this.updateQuantity(id, size, currentQty + 1, qtyEl);
    }

    handleDelete(e) {
        if (this.updating) return;
        const btn = e.currentTarget;
        const id = btn.dataset.id;
        const size = btn.dataset.size;
        this.removeItem(id, size);
    }

    async updateQuantity(productId, size, quantity, qtyEl) {
        this.updating = true;
        this.showSpinner(qtyEl);

        try {
            const response = await fetch('/api/cart/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId, size: size, quantity: quantity })
            });

            const data = await response.json();

            if (data.success) {
                await this.fetchCart();
                if (window.updateCartBadge) {
                    window.updateCartBadge();
                }
                this.showToaster('Cart updated!', 'success');
            }
            this.hideSpinner(qtyEl);
            this.updating = false;
        } catch (err) {
            console.error('Update error:', err);
            this.hideSpinner(qtyEl);
            this.updating = false;
            this.showToaster('Failed to update cart', 'error');
        }
    }

    async removeItem(productId, size) {
        this.updating = true;

        const cartItem = this.cartLeft.querySelector(`.cart-item[data-id="${productId}"][data-size="${size}"]`);
        if (cartItem) {
            cartItem.classList.add('updating');
        }

        try {
            const response = await fetch('/api/cart/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId, size: size })
            });

            const data = await response.json();

            if (data.success) {
                await this.fetchCart();
                if (window.updateCartBadge) {
                    window.updateCartBadge();
                }
                this.showToaster('Item removed from cart', 'success');
            }
            this.updating = false;
        } catch (err) {
            console.error('Remove error:', err);
            if (cartItem) cartItem.classList.remove('updating');
            this.updating = false;
            this.showToaster('Failed to remove item', 'error');
        }
    }

    recalculateTotal() {
        this.total = this.items.reduce((sum, item) => {
            return sum + (item.product.price * item.quantity);
        }, 0);
    }

    updateTotals() {
        this.subtotalEl.textContent = `KES ${this.total.toLocaleString()}`;
        this.totalEl.textContent = `KES ${this.total.toLocaleString()}`;
    }

    showEmpty() {
        if (!this.cartLeft) return;
        this.cartLeft.insertAdjacentHTML('afterbegin', `
            <div class="empty-cart-container">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                    <path d="M3 6h18"/>
                    <path d="M16 10a4 4 0 0 1-8 0"/>
                    <line x1="8" y1="14" x2="16" y2="14"/>
                    <line x1="8" y1="18" x2="12" y2="18"/>
                </svg>
                <h3>Your cart is empty</h3>
                <p>Looks like you haven't added anything yet.</p>
                <a href="/">Start shopping</a>
            </div>
        `);
        this.clearCartBtn.style.display = 'none';
    }

    showError() {
        if (!this.cartLeft) return;
        this.cartLeft.innerHTML = `
            <div class="empty-cart-container" style="border-color:#e23a2a;">
                <svg viewBox="0 0 24 24" fill="none" stroke="#e23a2a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <h3>Failed to load cart</h3>
                <p>Please refresh the page to try again.</p>
                <a href="/" style="background:#e23a2a;">Return to shop</a>
            </div>
        `;
        this.subtotalEl.textContent = 'KES 0';
        this.totalEl.textContent = 'KES 0';
        this.clearCartBtn.style.display = 'none';
    }

    showSpinner(qtyEl) {
        const parent = qtyEl.parentElement;
        const spinner = document.createElement('span');
        spinner.className = 'qty-spinner';
        spinner.id = 'temp-spinner';
        qtyEl.style.display = 'none';
        parent.insertBefore(spinner, qtyEl);

        const decreaseBtn = parent.querySelector('.decrease');
        const increaseBtn = parent.querySelector('.increase');
        if (decreaseBtn) decreaseBtn.classList.add('disabled');
        if (increaseBtn) increaseBtn.classList.add('disabled');
    }

    hideSpinner(qtyEl) {
        const spinner = document.getElementById('temp-spinner');
        if (spinner) spinner.remove();
        qtyEl.style.display = '';

        const parent = qtyEl.parentElement;
        const decreaseBtn = parent.querySelector('.decrease');
        const increaseBtn = parent.querySelector('.increase');
        if (decreaseBtn) decreaseBtn.classList.remove('disabled');
        if (increaseBtn) increaseBtn.classList.remove('disabled');
    }

    setupEventListeners() {
        // Scanner buttons
        if (this.scanStartBtn) {
            this.scanStartBtn.addEventListener('click', () => this.startScanner());
        }
        if (this.scanStopBtn) {
            this.scanStopBtn.addEventListener('click', () => this.stopScanner());
        }

        if (this.clearCartBtn) {
            this.clearCartBtn.addEventListener('click', async () => {
                if (!this.items || this.items.length === 0) return;
                if (confirm('Clear all items from your cart?')) {
                    try {
                        const promises = this.items.map(item => {
                            return fetch('/api/cart/remove', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ product_id: item.product_id, size: item.size })
                            });
                        });

                        await Promise.all(promises);
                        await this.fetchCart();
                        if (window.updateCartBadge) {
                            window.updateCartBadge();
                        }
                        this.showToaster('Cart cleared', 'success');
                    } catch (err) {
                        console.error('Clear cart error:', err);
                        this.showToaster('Failed to clear cart', 'error');
                    }
                }
            });
        }

        if (this.checkoutBtn) {
            this.checkoutBtn.addEventListener("click", async () => {
                if (!this.items || this.items.length === 0) {
                    this.showToaster('Your cart is empty', 'error');
                    return;
                }

                const items = this.items.map(item => ({
                    barcode: item.product.barcode,
                    quantity: item.quantity 
                }));

                const response = await fetch("/api/save/sales", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        items: items
                    })
                });

                const result = await response.json();
                if (result.status === "success") {
                    const salesId = result.sales_id;
                    window.location.href = `/checkout?sales_id=${salesId}`;
                }
            });
        }
    }

    init() {
        this.injectStyles();
        this.setupEventListeners();
        this.fetchCart();
    }
}

const scannersection = document.getElementById("scanner-section")
    scannersection.style.display = 'none'
    function openScanner() {
        if (scannersection.style.display === 'none'){
            scannersection.style.display ='flex'
        } else if (scannersection.style.display === "flex") {
            scannersection.style.display = "none"
        }
        else {
            scannersection.style.display = "none"
        }
    }
    
document.addEventListener('DOMContentLoaded', () => {
    
    if (window.cartLoader) {
        window.cartLoader = null;
    }
    window.cartLoader = new CartLoader();
    window.cartLoader.init();
});