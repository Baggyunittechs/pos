const salesTable = document.getElementById("salesTable");
const outOfStockGrid = document.getElementById("outOfStockGrid");
const outOfStockCount = document.getElementById("outOfStockCount");
const exportCsvBtn = document.getElementById("exportCsvBtn");

let currentSalesData = [];
let currentPage = 1;
const itemsPerPage = 15;
let showMoreButton = null;
let totalItemsDisplayed = 0;

document.addEventListener('DOMContentLoaded', function () {
    async function loadSalesHistory() {
        try {
            const response = await fetch('/api/admin/sales/history/all');

            if (!response.ok) {
                throw new Error('Failed to load sales');
            }

            const salesHistory = await response.json();
            console.log(salesHistory);
            
            // Handle both array and object response formats
            let salesArray;
            if (Array.isArray(salesHistory)) {
                salesArray = salesHistory;
            } else if (salesHistory && salesHistory.sales && Array.isArray(salesHistory.sales)) {
                salesArray = salesHistory.sales;
            } else {
                salesArray = [];
            }
            
            currentSalesData = salesArray;
            currentPage = 1;
            totalItemsDisplayed = 0;
            renderSales(currentSalesData);

        } catch (error) {
            console.error('Error loading sales history:', error);
            renderSales([]);
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
        
        // Remove existing "Show More" button if it exists
        if (showMoreButton) {
            showMoreButton.remove();
            showMoreButton = null;
        }

        // If first time loading or resetting, clear the table
        if (currentPage === 1) {
            salesTable.innerHTML = '';
            totalItemsDisplayed = 0;
        }

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

        const totalItems = salesHistory.length;
        const totalPages = Math.ceil(totalItems / itemsPerPage);
        
        if (currentPage > totalPages) {
            currentPage = totalPages;
        }
        
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
        const pageItems = salesHistory.slice(startIndex, endIndex);

        // Append new items to the table
        pageItems.forEach(dt => {
            const productHTML = createSaleTable(dt);
            salesTable.insertAdjacentHTML('beforeend', productHTML);
        });

        totalItemsDisplayed = endIndex;

        // Add "Show More" button if there are more items to show
        if (endIndex < totalItems) {
            showMoreButton = document.createElement('tr');
            showMoreButton.innerHTML = `
                <td colspan="4" style="text-align: center; padding: 20px 0;">
                    <button id="showMoreBtn" style="
                        padding: 10px 30px;
                        background: #fab300d8;
                        color: #fff;
                        border: none;
                        border-radius: 4px;
                        font-size: 14px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: background 0.15s ease;
                        display: inline-flex;
                        align-items: center;
                        gap: 8px;
                    ">
                        Show More 
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                            <path d="M6 9l6 6l6 -6" />
                        </svg>
                    </button>
                </td>
            `;
            salesTable.parentElement.appendChild(showMoreButton);
            
            const showMoreBtn = document.getElementById('showMoreBtn');
            if (showMoreBtn) {
                showMoreBtn.addEventListener('click', function() {
                    currentPage++;
                    renderSales(currentSalesData);
                    setTimeout(() => {
                        this.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 100);
                });
                
                showMoreBtn.addEventListener('mouseenter', function() {
                    this.style.background = '#FAB400';
                    this.style.color = '#fefeff';
                });
                
                showMoreBtn.addEventListener('mouseleave', function() {
                    this.style.background = '#fab300d8';
                    this.style.color = '#fff';
                });
            }
        }
    }

    function createSaleTable(dt) {
        const salesID = dt.sales_id || 'N/A';
        const salesStatus = dt.sales_status || 'N/A';
        const total = dt.total || 0;
        const transactionID = dt.transaction_id || 'N/A';

        return `
            <tr>
                <td>${salesID}</td>
                <td>${transactionID}</td>
                <td>KES ${total}</td>
                <td><span class="status status-paid">${salesStatus}</span></td>
            </tr>
        `;
    }

    function exportTableToCSV() {
        if (!currentSalesData || currentSalesData.length === 0) {
            alert("No data available to export.");
            return;
        }

        let csvContent = "Sales ID,Transaction ID,Total (KES),Status\n";
        let sumTotal = 0;

        currentSalesData.forEach(dt => {
            const total = Number(dt.total) || 0;
            sumTotal += total;

            csvContent += `"${dt.sales_id}","${dt.transaction_id || ''}","${total}","${dt.sales_status || ''}"\n`;
        });

        csvContent += `\n"TOTALS","","${sumTotal}",""`;

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        
        link.setAttribute("href", url);
        link.setAttribute("download", `sales_export_${new Date().toISOString().slice(0,10)}.csv`);
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    if (exportCsvBtn) {
        exportCsvBtn.addEventListener("click", exportTableToCSV);
    }

    loadSalesHistory();
    loadOutOfStock();
});