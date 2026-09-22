const totalOrder = document.getElementById("total_order");
const revToday = document.getElementById("rev-today");
const revMonth = document.getElementById("rev-month");
const salesTable = document.getElementById("salesTable");
const profMonthly = document.getElementById("monthly_profit");
const exportCsvBtn = document.getElementById("exportCsvBtn");

let currentSalesData = [];
let currentPage = 1;
const itemsPerPage = 15;
let showMoreButton = null;
let totalItemsDisplayed = 0;

document.addEventListener('DOMContentLoaded', function () {

  async function loadSales() {
    try {
      const response = await fetch('/api/admin/sales/summary');

      if (!response.ok) {
        throw new Error('Failed to load sales');
      }

      const data = await response.json();

      function calcDelta(current, previous) {
        const c = Number(current) || 0;
        const p = Number(previous) || 0;
        if (p > 0) return ((c - p) / p) * 100;
        if (c > 0) return 100;
        return 0;
      }

      function calcProfitDelta(current, previous) {
        const c = Number(current) || 0;
        const p = Number(previous) || 0;
        if (p !== 0) return ((c - p) / Math.abs(p)) * 100;
        if (c !== 0) return 100;
        return 0;
      }

      function pickTrend(trendArray, fallback) {
        return Array.isArray(trendArray) && trendArray.length ? trendArray : fallback;
      }

      totalOrder.textContent = data.today.sales_total;
      revToday.textContent = "KES " + data.today.revenue;
      revMonth.textContent = "KES " + data.this_month.revenue;
      profMonthly.textContent = "KES " + data.this_month.monthly_profit;

      const monthlySalesCountEl = document.getElementById("monthly_sales_count");
      if (monthlySalesCountEl) {
        monthlySalesCountEl.textContent = data.this_month.sales_total;
      }

      const salesChangePct = calcDelta(data.today.sales_total, data.yesterday.sales_total);
      const salesChangeMnth = calcDelta(data.this_month.sales_total, data.last_month.sales_total);
      const revenueChangePct = calcDelta(data.today.revenue, data.yesterday.revenue);
      const revenueChangeMnth = calcDelta(data.this_month.revenue, data.last_month.revenue);
      const profChangeMnth = calcProfitDelta(data.this_month.monthly_profit, data.last_month.last_month_profit);

      setDelta('sales-delta', salesChangePct);
      setDelta('rev-today-delta', revenueChangePct);
      setDelta('rev-month-delta', revenueChangeMnth);
      setDelta('sales-month-delta', salesChangeMnth);
      setDelta('monthly_profit_delta', profChangeMnth);

      setSparkline('sales-sparkline', pickTrend(data.daily_sales_trend, [data.yesterday.sales_total, data.today.sales_total]));
      setSparkline('rev-today-sparkline', pickTrend(data.daily_revenue_trend, [data.yesterday.revenue, data.today.revenue]));
      setSparkline('rev-month-sparkline', pickTrend(data.monthly_revenue_trend, [data.last_month.revenue, data.this_month.revenue]));
      setSparkline('sales-month-sparkline', pickTrend(data.monthly_sales_trend, [data.last_month.sales_total, data.this_month.sales_total]));
      setSparkline('monthly_profit_sparkline', pickTrend(data.monthly_profit_trend, [data.last_month.last_month_profit, data.this_month.monthly_profit]));

    } catch (error) {
      console.error('Error loading products:', error);
    }
  }

  function setDelta(elementId, pct) {
    const el = document.getElementById(elementId);
    if (!el || pct === undefined || pct === null || isNaN(pct)) return;

    const rounded = Math.round(pct * 10) / 10;
    el.textContent = (rounded >= 0 ? "+" : "") + rounded + "%";
    el.classList.toggle('positive', rounded >= 0);
    el.classList.toggle('negative', rounded < 0);
  }

  function setSparkline(svgId, rawValues) {
    const svg = document.getElementById(svgId);
    if (!svg) return;

    const values = Array.isArray(rawValues) ? rawValues.map(v => Number(v) || 0) : [];
    if (values.length < 2) return;

    const polyline = svg.querySelector('polyline');
    if (!polyline) return;

    const w = 100, h = 30, pad = 2;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = (max - min) === 0 ? 1 : (max - min);
    const step = (w - pad * 2) / (values.length - 1);

    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

    const points = values.map((v, i) => {
      const x = pad + i * step;
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    polyline.setAttribute('points', points);
  }

  async function loadSalesHistory() {
    try {
      const response = await fetch('/api/admin/sales/history');

      if (!response.ok) {
        throw new Error('Failed to load sales');
      }

      const result = await response.json();
      
      let salesHistory;
      if (Array.isArray(result)) {
        salesHistory = result;
      } else if (result.sales && Array.isArray(result.sales)) {
        salesHistory = result.sales;
        const monthInfoEl = document.getElementById('month-info');
        if (monthInfoEl && result.month) {
          monthInfoEl.textContent = `Showing: ${result.month} (${result.total_sales} sales)`;
        }
      } else {
        salesHistory = [];
      }
      
      currentSalesData = salesHistory;
      currentPage = 1;
      totalItemsDisplayed = 0;
      renderSales(currentSalesData);

    } catch (error) {
      console.error('Error loading sales history:', error);
    }
  }

  function renderSales(salesHistory) {
    if (!salesTable) return;
    
    if (showMoreButton) {
      showMoreButton.remove();
      showMoreButton = null;
    }

    if (currentPage === 1) {
      salesTable.innerHTML = '';
      totalItemsDisplayed = 0;
    }

    if (!salesHistory || salesHistory.length === 0) {
      salesTable.innerHTML = `
        <tr>
          <td colspan="5">
            <div class="empty-state-container" style="grid-column: 1 / -1; text-align: center; padding: 40px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width: 48px; height: 48px; margin: 0 auto;">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                <path d="M3 6h18"/>
                <path d="M16 10a4 4 0 0 1-8 0"/>
                <line x1="8" y1="14" x2="16" y2="14"/>
                <line x1="8" y1="18" x2="12" y2="18"/>
              </svg>
              <h3>No sales for this month</h3>
              <p>Check back later for new transactions.</p>
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

    pageItems.forEach(dt => {
      const productHTML = createSaleTable(dt);
      salesTable.insertAdjacentHTML('beforeend', productHTML);
    });

    totalItemsDisplayed = endIndex;

    if (endIndex < totalItems) {
      showMoreButton = document.createElement('tr');
      showMoreButton.innerHTML = `
        <td colspan="5" style="text-align: center; padding: 20px 0;">
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
          this.style.color = '#fff';
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
    const profit = dt.profit || 0;

    return `
      <tr>
        <td>${salesID}</td>
        <td>${transactionID}</td>
        <td>KES ${total}</td>
        <td>KES ${profit}</td>
        <td><span class="status status-paid">${salesStatus}</span></td>
      </tr>
    `;
  }

  function exportTableToCSV() {
    if (!currentSalesData || currentSalesData.length === 0) {
      alert("No data available to export.");
      return;
    }

    let csvContent = "Sales ID,Transaction ID,Total (KES),Profit (KES),Status\n";
    let sumTotal = 0;
    let sumProfit = 0;

    currentSalesData.forEach(dt => {
      const total = Number(dt.total) || 0;
      const profit = Number(dt.profit) || 0;
      
      sumTotal += total;
      sumProfit += profit;

      csvContent += `"${dt.sales_id}","${dt.transaction_id}","${total}","${profit}","${dt.sales_status}"\n`;
    });

    csvContent += `\n"TOTALS","","${sumTotal}","${sumProfit}",""`;

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
  loadSales();
  loadWeeklyData();
});

function renderLineChart(svgId, rawData, lineColor, fillColor) {
  const svg = document.getElementById(svgId);
  if (!svg) return;

  const data = Array.isArray(rawData) ? rawData.map(v => Number(v) || 0) : [];

  if (data.length < 2) {
    svg.innerHTML = `
      <text x="140" y="85" text-anchor="middle" fill="#9aa0aa" font-size="13" font-weight="500">
        No data available
      </text>
    `;
    return;
  }

  const w = 280, h = 170, pad = 15;
  const min = 0;
  let max = Math.max(...data);
  if (max === 0) max = 1;
  max = max * 1.1;

  const range = max - min;
  const step = (w - pad * 2) / (data.length - 1);

  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const points = data.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const firstX = pad;
  const lastX = pad + (data.length - 1) * step;
  const bottomY = h - pad;
  const areaPoints = `${firstX},${bottomY} ${points} ${lastX},${bottomY}`;

  svg.innerHTML = `
    <polygon points="${areaPoints}" fill="${fillColor}" />
    <polyline points="${points}" fill="none" stroke="${lineColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
  `;
}

function formatNumber(n) {
  return Number(n || 0).toLocaleString();
}

function renderLabels(containerId, labels) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = labels.map(l => `<span>${l}</span>`).join('');
}

function loadWeeklyData() {
  fetch('/api/admin/sales/weekly')
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load weekly sales data');
      }
      return response.json();
    })
    .then(data => {
      const weeklyRevenue = data.revenue || {};
      const weeklySales = data.sales || {};
      const dayOrder = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

      const revenueValues = dayOrder.map(day => Number(weeklyRevenue[day]) || 0);
      const salesValues = dayOrder.map(day => Number(weeklySales[day]) || 0);

      const shortDayLabels = dayOrder.map(day => day.substring(0, 3));

      renderLineChart('salesChart', salesValues, '#F5A623', 'rgba(245, 166, 35, 0.15)');
      renderLineChart('revenueChart', revenueValues, '#1E9E75', 'rgba(30, 158, 117, 0.15)');

      const totalRevenue = revenueValues.reduce((a, b) => a + b, 0);
      const totalSales = salesValues.reduce((a, b) => a + b, 0);

      const revenueTotalEl = document.getElementById('revenueTotal');
      if (revenueTotalEl) {
        revenueTotalEl.textContent = 'KES ' + formatNumber(totalRevenue);
      }

      const salesTotalEl = document.getElementById('salesTotal');
      if (salesTotalEl) {
        salesTotalEl.textContent = formatNumber(totalSales);
      }

      renderLabels('revenueLabels', shortDayLabels);
      renderLabels('salesLabels', shortDayLabels);
    })
    .catch(error => {
      console.error('Error loading weekly data:', error);

      const charts = ['revenueChart', 'salesChart'];
      charts.forEach(id => {
        const svg = document.getElementById(id);
        if (svg) {
          svg.innerHTML = `
            <text x="140" y="85" text-anchor="middle" fill="#9aa0aa" font-size="13" font-weight="500">
              Failed to load data
            </text>
          `;
        }
      });
    });
}