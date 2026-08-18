const salesTable = document.getElementById("salesTable");
const outOfStockGrid = document.getElementById("outOfStockGrid");
const outOfStockCount = document.getElementById("outOfStockCount");

document.addEventListener('DOMContentLoaded', function () {
    async function loadSalesHistory() {
        try {
            const response = await fetch('/api/admin/sales/history');

            if (!response.ok) {
                throw new Error('Failed to load sales');
            }

            const salesHistory = await response.json();
            console.log(salesHistory);
            const salesArray = Array.isArray(salesHistory) ? salesHistory : [salesHistory];
            renderSales(salesArray);

        } catch (error) {
            console.error('Error loading sales history:', error);
        }
    }

    async function loadOutOfStock() {
        try {
            const response = await fetch('/api/admin/items/stock');

            if (!response.ok) {
                throw new Error('Failed to load out of stock items');
            }

            const data = await response.json();
            console.log(data);

            if (data.status === 'success' && data.out_of_stock_items) {
                renderOutOfStock(data.out_of_stock_items);
            } else {
                renderOutOfStock([]);
            }

        } catch (error) {
            console.error('Error loading out of stock items:', error);
            renderOutOfStock([]);
        }
    }

    function renderOutOfStock(items) {
        if (!outOfStockGrid) return;

        if (outOfStockCount) {
            outOfStockCount.textContent = items.length;
        }

        outOfStockGrid.innerHTML = '';

        if (!items || items.length === 0) {
            outOfStockGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #6b7280;">
                    <p>No out of stock items</p>
                </div>
            `;
            return;
        }

        items.forEach(product => {
            const productName = product.name || product.product_name || 'Unnamed Product';
            const sku = product.sku || product.barcode || 'N/A';
            const image = product.image_url || product.image || '';

            const cardHTML = `
                <div class="stock-card">
                    <div class="stock-card-image" style="${image ? `background-image: url('${image}'); background-size: cover; background-position: center;` : ''}"></div>
                    <div class="stock-card-info">
                        <div class="stock-card-name">${productName}</div>
                        <span class="stock-card-barcode">SKU ${sku}</span>
                        <button class="restock-btn" data-product-id="${product.id || product.product_id || ''}">Edit</button>
                    </div>
                </div>
            `;
            outOfStockGrid.insertAdjacentHTML('beforeend', cardHTML);
        });

        document.querySelectorAll('.restock-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const productId = this.dataset.productId;
                if (productId) {
                    window.location.href = `/admin/products/edit/${productId}`;
                }
            });
        });
    }

    function renderSales(salesHistory) {
        if (!salesTable) return;
        salesTable.innerHTML = '';

        if (!salesHistory || salesHistory.length === 0) {
            salesTable.innerHTML = `
                <tr>
                    <td colspan="4">
                        <div class="empty-state-container" style="grid-column: 1 / -1; text-align: center; padding: 40px;">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width: 48px; height: 48px; margin: 0 auto;">
                                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                                <path d="M3 6h18"/>
                                <path d="M16 10a4 4 0 0 1-8 0"/>
                                <line x1="8" y1="14" x2="16" y2="14"/>
                                <line x1="8" y1="18" x2="12" y2="18"/>
                            </svg>
                            <h3>No products available</h3>
                            <p>Check back later for new items.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        salesHistory.forEach(dt => {
            const productHTML = createSaleTable(dt);
            salesTable.insertAdjacentHTML('beforeend', productHTML);
        });
    }

    function createSaleTable(dt) {
        const salesID = dt.sales_id;
        const salesStatus = dt.sales_status;
        const total = dt.total;
        const transactionID = dt.transaction_id;

        return `
            <tr>
                <td>${salesID}</td>
                <td>${transactionID}</td>
                <td>KES ${total}</td>
                <td><span class="status status-paid">${salesStatus}</span></td>
            </tr>
        `;
    }

    loadSalesHistory();
    loadOutOfStock();
});