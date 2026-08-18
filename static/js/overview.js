const totalOrder = document.getElementById("total_order");
const revToday = document.getElementById("rev-today");
const revMonth = document.getElementById("rev-month");
const salesTable = document.getElementById("salesTable");
const profMonthly = document.getElementById("monthly_profit")

document.addEventListener('DOMContentLoaded', function () {

  async function loadSales() {
    try {
      const response = await fetch('/api/admin/sales/summary');

      if (!response.ok) {
        throw new Error('Failed to load sales');
      }

      const data = await response.json();
      console.log(data);

      function calcDelta(current, previous) {
        if (previous > 0) return ((current - previous) / previous) * 100;
        if (current > 0) return 100; // grew from zero — treat as full growth
        return 0; // both zero, no change
      }

      function calcProfitDelta(current, previous) {
        if (previous !== 0) return ((current - previous) / Math.abs(previous)) * 100;
        if (current !== 0) return 100;
        return 0;
      }

      function pickTrend(trendArray, fallback) {
        return Array.isArray(trendArray) && trendArray.length ? trendArray : fallback;
      }

      if (response.ok) {
        totalOrder.textContent = data.today.sales_total;
        revToday.textContent = "KES " + data.today.revenue;
        revMonth.textContent = "KES " + data.this_month.revenue;
        profMonthly.textContent = "KES " + data.this_month.monthly_profit;

        document.getElementById("monthly_sales_count").textContent = data.this_month.sales_total;

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
      }

    } catch (error) {
      console.error('Error loading products:', error);
      showError();
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

  function setSparkline(svgId, values) {
    const svg = document.getElementById(svgId);
    if (!svg || !Array.isArray(values) || values.length < 2) return;

    const polyline = svg.querySelector('polyline');
    if (!polyline) return;

    const w = 100, h = 30, pad = 2;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = (max - min) || 1;
    const step = (w - pad * 2) / (values.length - 1);

    const points = values.map((v, i) => {
      const x = pad + i * step;
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x},${y}`;
    }).join(' ');

    polyline.setAttribute('points', points);
  }

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

  function renderSales(salesHistory) {
    if (!salesTable) return;
    salesTable.innerHTML = '';

    if (!salesHistory || salesHistory.length === 0) {
      salesTable.innerHTML = `
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
    const profit = dt.profit

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

  loadSalesHistory();
  loadSales();
});

function renderLineChart(svgId, data, lineColor, fillColor) {
  const svg = document.getElementById(svgId);
  const w = 280, h = 170, pad = 10;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = (max - min) || 1;
  const step = (w - pad * 2) / (data.length - 1);

  const points = data.map((v, i) => [
    pad + i * step,
    h - pad - ((v - min) / range) * (h - pad * 2)
  ]);

  function smoothPath(pts) {
    let d = `M ${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2] || p2;
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
    }
    return d;
  }

  const linePath = smoothPath(points);
  const last = points[points.length - 1];
  const first = points[0];
  const areaPath = `${linePath} L ${last[0]},${h - pad} L ${first[0]},${h - pad} Z`;

  svg.innerHTML = `
    <path d="${areaPath}" fill="${fillColor}" stroke="none"></path>
    <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="2" stroke-linecap="round"></path>
  `;
}

function formatNumber(n) {
  return n.toLocaleString();
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

      const revenueValues = dayOrder.map(day => weeklyRevenue[day] || 0);
      const salesValues = dayOrder.map(day => weeklySales[day] || 0);
      const shortDayLabels = dayOrder.map(day => day.substring(0, 3));

      renderLineChart('revenueChart', revenueValues, '#1E9E75', 'rgba(30, 158, 117, 0.15)');
      renderLineChart('salesChart', salesValues, '#F5A623', 'rgba(245, 166, 35, 0.15)');

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

      const revenueChart = document.getElementById('revenueChart');
      if (revenueChart) {
        revenueChart.innerHTML = `
          <text x="50%" y="50%" text-anchor="middle" fill="#999" font-size="12">
            No data available
          </text>
        `;
      }

      const salesChart = document.getElementById('salesChart');
      if (salesChart) {
        salesChart.innerHTML = `
          <text x="50%" y="50%" text-anchor="middle" fill="#999" font-size="12">
            No data available
          </text>
        `;
      }
    });
}

document.addEventListener('DOMContentLoaded', () => {
  loadWeeklyData();
});











