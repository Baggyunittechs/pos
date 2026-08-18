document.addEventListener('DOMContentLoaded', function() {
    const shopItemsContainer = document.getElementById('shop-items');
    async function loadProducts() {
        try {
            const response = await fetch('/api/products');
            
            if (!response.ok) {
                throw new Error('Failed to load products');
            }
            
            const products = await response.json();
            renderProducts(products);
            
        } catch (error) {
            console.error('Error loading products:', error);
            showError();
        }
    }
    function renderProducts(products) {
        if (!shopItemsContainer) return;
        shopItemsContainer.innerHTML = '';
        
        if (!products || products.length === 0) {
            showEmptyState();
            return;
        }
        products.forEach(product => {
            const productHTML = createProductCard(product);
            shopItemsContainer.insertAdjacentHTML('beforeend', productHTML);
        });
        attachAddToCartListeners();
    }
    function createProductCard(product) {
        const imageUrl = product.image || '/static/images/placeholder.png';
        const price = product.price || 0;
        const barcode = product.barcode || '';
        const name = product.name || 'Unnamed Product';
        
        return `
            <div class="item" data-barcode="${barcode}" data-product-id="${barcode}">
                <div class="item-image">
                    <img src="${imageUrl}" alt="${name}" loading="lazy" onerror="this.src='/static/images/placeholder.png'">
                </div>
                <div class="item-info">
                    <div class="name">${name}</div>
                    <div class="barcode">${barcode}</div>
                    <div class="price">KES ${price.toFixed(2)}</div>
                    <button class="add-to-cart" data-product-id="${barcode}">
                        <svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24"
                            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                            stroke-linejoin="round">
                            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                            <path d="M3 6h18" />
                            <path d="M16 10a4 4 0 0 1-8 0" />
                        </svg>
                        Add to cart
                    </button>
                </div>
            </div>
        `;
    }
    function attachAddToCartListeners() {
        const addButtons = document.querySelectorAll('.add-to-cart');
        
        addButtons.forEach(button => {
            button.removeEventListener('click', handleAddToCart);
            button.addEventListener('click', handleAddToCart);
        });
    }
    
    async function handleAddToCart(event) {
        const button = event.currentTarget;
        const productId = button.dataset.productId;
        
        button.disabled = true;
        button.textContent = 'Adding...';
        
        try {
            const productItem = button.closest('.item');
            const productName = productItem?.querySelector('.name')?.textContent || 'Product';
            const response = await fetch('/api/cart/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: 1
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (window.updateCartBadge) {
                    await window.updateCartBadge();
                }
                showToast(`${productName} added to cart!`, 'success');
                
                // Reset button
                button.textContent = '✓ Added';
                setTimeout(() => {
                    button.innerHTML = `
                        <svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24"
                            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                            stroke-linejoin="round">
                            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                            <path d="M3 6h18" />
                            <path d="M16 10a4 4 0 0 1-8 0" />
                        </svg>
                        Add to cart
                    `;
                    button.disabled = false;
                }, 1500);
                
            } else {
                throw new Error(result.message || 'Failed to add to cart');
            }
            
        } catch (error) {
            console.error('Add to cart error:', error);
            showToast(error.message || 'Failed to add to cart', 'error');
            
            button.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                    stroke-linejoin="round">
                    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                    <path d="M3 6h18" />
                    <path d="M16 10a4 4 0 0 1-8 0" />
                </svg>
                Add to cart
            `;
            button.disabled = false;
        }
    }
    function showToast(message, type = 'success') {
        if (window.cartLoader && window.cartLoader.showToaster) {
            window.cartLoader.showToaster(message, type);
            return;
        }
        
        const existingToast = document.getElementById('custom-toast');
        if (existingToast) existingToast.remove();
        
        const toast = document.createElement('div');
        toast.id = 'custom-toast';
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 9999;
            background: ${type === 'success' ? '#28a745' : '#dc3545'};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideDown 0.3s ease;
            font-family: 'Inter', sans-serif;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    function showEmptyState() {
        shopItemsContainer.innerHTML = `
            <div class="empty-state-container" style="grid-column: 1 / -1;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                    <path d="M3 6h18"/>
                    <path d="M16 10a4 4 0 0 1-8 0"/>
                    <line x1="8" y1="14" x2="16" y2="14"/>
                    <line x1="8" y1="18" x2="12" y2="18"/>
                </svg>
                <h3>No products available</h3>
                <p>Check back later for new items.</p>
            </div>
        `;
    }
    function showError() {
        shopItemsContainer.innerHTML = `
            <div class="empty-state-container error" style="grid-column: 1 / -1; border-color: #E23A2A;">
                <svg viewBox="0 0 24 24" fill="none" stroke="#E23A2A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <h3>Failed to load products</h3>
                <p>Please refresh the page to try again.</p>
            </div>
        `;
    }
    loadProducts();
});

document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('uploadOverlay');
  const closeBtn = document.getElementById('uploadClose');
  const form = document.getElementById('uploadForm');
  const uploadBtn = document.getElementById('uploadBtn');
  const imageInput = document.getElementById('productImage');
  const imagePreview = document.getElementById('imagePreview');
  const successMsg = document.getElementById('uploadSuccess');
  const errorMsg = document.getElementById('uploadError');

  const trigger = document.getElementById('uploadTrigger');
  if (trigger) {
    trigger.addEventListener('click', () => overlay.classList.add('active'));
    
  }

  closeBtn.addEventListener('click', () => overlay.classList.remove('active'));

  window.openUploadOverlay = () => overlay.classList.add('active');
  window.closeUploadOverlay = () => overlay.classList.remove('active');

  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      imagePreview.innerHTML = `<img src="${e.target.result}" alt="Product preview">`;
    };
    reader.readAsDataURL(file);
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    successMsg.classList.remove('show');
    errorMsg.classList.remove('show');
    uploadBtn.classList.add('loading');
    uploadBtn.disabled = true;
    const formData = new FormData();
    formData.append('name', document.getElementById('productName').value.trim());
    formData.append('barcode', document.getElementById('barcode').value.trim());
    formData.append('price', document.getElementById('sellingPrice').value);
    formData.append('buying price', document.getElementById('buyingPrice').value);
    const stockValue = parseInt(document.getElementById('stockAmount').value, 10);
    if (isNaN(stockValue) || stockValue < 0) {
      uploadBtn.classList.remove('loading');
      uploadBtn.disabled = false;
      errorMsg.textContent = 'Stock amount must be a whole number';
      errorMsg.classList.add('show');
      return;
    }
    formData.append('stock_amount', stockValue);
    formData.append('tags', document.getElementById('tags').value.trim());

    

    const imageFile = imageInput.files[0];
    if (imageFile) {
      formData.append('main_image', imageFile);
    }
    try {
      const res = await fetch('/api/admin/items/upload', {
        method: 'POST',
        body: formData
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Upload failed');
      }

      uploadBtn.classList.remove('loading');
      uploadBtn.disabled = false;
      successMsg.classList.add('show');
      form.reset();
      imagePreview.innerHTML = '<span class="image-preview-placeholder">No image selected</span>';
      
      window.dispatchEvent(new CustomEvent('product:uploaded', { detail: data.product }));
      window.location.href = '/shop'
      setTimeout(() => {
        successMsg.classList.remove('show');
        overlay.classList.remove('active');
      }, 1500);

    } catch (err) {
      uploadBtn.classList.remove('loading');
      uploadBtn.disabled = false;
      errorMsg.textContent = err.message;
      errorMsg.classList.add('show');
    }
  });
});