document.addEventListener("DOMContentLoaded", async () => {
    const params = new URLSearchParams(window.location.search);
    const salesId = params.get("sales_id");

    if (!salesId) {
        console.error("sales_id not found");
        return;
    }

    const response = await fetch(`/api/checkout?sales_id=${salesId}`);
    const result = await response.json();

    window.saleData = { salesId: null, total: null, checkoutRequestId: null, phoneNumber: null };

    if (result.status === "success") {
        const saleIdElement = document.getElementById("sale-id");
        if (saleIdElement) {
            saleIdElement.textContent = result.sale.sales_id;
        }
        
        const totalElement = document.getElementById("total");
        if (totalElement) {
            totalElement.textContent = result.sale.total;
        }
        
        const payTotalElement = document.getElementById("pay-total");
        if (payTotalElement) {
            payTotalElement.textContent = result.sale.total;
        }

        window.saleData.salesId = result.sale.sales_id;
        window.saleData.total = result.sale.total;
        
    } else {
        window.location.href = `/cart`
        console.error("Checkout error:", result.message);
        
    }

    window.saleData.paymentMethod = 'mpesa';
    window.saleData.hybridPhoneNumber = null;

    const payMethodEls = document.querySelectorAll('.pay-method');
    const mpesaWrap = document.getElementById('mpesa-wrap');
    const hybridWrap = document.getElementById('hybrid-wrap');
    const hybridCashInput = document.getElementById('hybrid-cash-amount');
    const hybridMpesaInput = document.getElementById('hybrid-mpesa-amount');

    function totalAsNumber() {
        return parseFloat(window.saleData.total) || 0;
    }

    function updatePayButtonState() {
        const payBtn = document.getElementById('pay-btn');
        if (!payBtn) return;
        const method = window.saleData.paymentMethod || 'mpesa';

        if (method === 'mpesa') {
            payBtn.disabled = !window.saleData.phoneNumber;
        } else if (method === 'cash') {
            payBtn.disabled = false;
        } else if (method === 'hybrid') {
            const cash = parseFloat(hybridCashInput ? hybridCashInput.value : '');
            const mpesa = parseFloat(hybridMpesaInput ? hybridMpesaInput.value : '');
            const total = totalAsNumber();
            const amountsOk = !isNaN(cash) && !isNaN(mpesa) && cash > 0 && mpesa > 0 &&
                Math.abs((cash + mpesa) - total) < 0.01;
            payBtn.disabled = !(window.saleData.hybridPhoneNumber && amountsOk);
        }
    }

    payMethodEls.forEach(function (el) {
        el.addEventListener('click', function () {
            payMethodEls.forEach(function (m) { m.classList.remove('active'); });
            el.classList.add('active');

            const method = el.getAttribute('value');
            window.saleData.paymentMethod = method;

            if (mpesaWrap) mpesaWrap.style.display = (method === 'mpesa' || method === 'cash') ? '' : 'none';
            if (hybridWrap) hybridWrap.style.display = method === 'hybrid' ? '' : 'none';

            updatePayButtonState();
        });
    });

    // Cash and M-Pesa amounts must sum to exactly the sale total (the hybrid
    // API rejects anything else), so keep them balanced as the person types.
    if (hybridCashInput && hybridMpesaInput) {
        hybridCashInput.addEventListener('input', function () {
            const cash = parseFloat(hybridCashInput.value) || 0;
            const remainder = Math.max(0, totalAsNumber() - cash);
            hybridMpesaInput.value = remainder ? remainder.toFixed(2) : '';
            updatePayButtonState();
        });

        hybridMpesaInput.addEventListener('input', function () {
            const mpesa = parseFloat(hybridMpesaInput.value) || 0;
            const remainder = Math.max(0, totalAsNumber() - mpesa);
            hybridCashInput.value = remainder ? remainder.toFixed(2) : '';
            updatePayButtonState();
        });
    }

    function setupPhoneValidation(config) {
        var phoneInput = document.getElementById(config.inputId);
        var phoneWrap = document.getElementById(config.wrapId);
        var phoneHint = document.getElementById(config.hintId);

        function sanitizePhone(raw) {
            var digits = raw.replace(/\D/g, '');
            
            if (digits.length === 0) {
                return '';
            }
            
            if (digits.startsWith('0')) {
                digits = digits.substring(1);
                if (digits.length > 0) {
                    return '254' + digits;
                }
            } else if (digits.startsWith('7') || digits.startsWith('1')) {
                return '254' + digits;
            } else if (digits.startsWith('254')) {
                return digits;
            }
            
            return digits;
        }

        function isValidPhone(phone) {
            return /^254[71]\d{8}$/.test(phone);
        }

        function formatDisplay(phone) {
            var display = phone.replace(/^254/, '');
            var parts = [];
            if (display.length > 0) parts.push(display.slice(0, 3));
            if (display.length > 3) parts.push(display.slice(3, 6));
            if (display.length > 6) parts.push(display.slice(6, 9));
            return parts.join(' ');
        }

        function validateAndUpdate(phoneInputValue) {
            var sanitized = sanitizePhone(phoneInputValue);
            var valid = isValidPhone(sanitized);
            
            if (sanitized.length === 0) {
                phoneWrap.classList.remove('error');
                phoneHint.classList.remove('error');
                phoneHint.textContent = 'Enter a valid Kenyan number, e.g. 0712 345 678 or 712 345 678';
                window.saleData[config.targetKey] = null;
                updatePayButtonState();
                return;
            }
            
            if (valid) {
                phoneWrap.classList.remove('error');
                phoneHint.classList.remove('error');
                var display = formatDisplay(sanitized);
                phoneHint.textContent = '✅ Valid number: ' + display + ' (' + sanitized + ')';
                window.saleData[config.targetKey] = sanitized;
            } else {
                phoneWrap.classList.add('error');
                phoneHint.classList.add('error');
                phoneHint.textContent = '❌ Invalid Kenyan number. Must start with 07 or 7 and have 9 digits (e.g., 0712 345 678)';
                window.saleData[config.targetKey] = null;
            }
            updatePayButtonState();
        }

        if (phoneInput) {
            phoneInput.addEventListener('input', function (e) {
                var rawValue = e.target.value;
                validateAndUpdate(rawValue);
            });

            phoneInput.addEventListener('paste', function (e) {
                e.preventDefault();
                var pasted = (e.clipboardData || window.clipboardData).getData('text');
                phoneInput.value = pasted;
                validateAndUpdate(pasted);
            });

            phoneInput.addEventListener('keydown', function (e) {
                var allowed = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Home', 'End'];
                if (allowed.indexOf(e.key) !== -1) return;
                if (!/^\d$/.test(e.key)) e.preventDefault();
            });

            phoneInput.addEventListener('blur', function (e) {
                var rawValue = e.target.value;
                var sanitized = sanitizePhone(rawValue);
                if (isValidPhone(sanitized)) {
                    var display = formatDisplay(sanitized);
                    phoneInput.value = display;
                }
            });

            validateAndUpdate('');
        }
    }

    setupPhoneValidation({ inputId: 'phone', wrapId: 'phone-wrap', hintId: 'phone-hint', targetKey: 'phoneNumber' });
    setupPhoneValidation({ inputId: 'hybrid-phone', wrapId: 'hybrid-phone-wrap', hintId: 'hybrid-phone-hint', targetKey: 'hybridPhoneNumber' });

    async function payWithMpesa(salesId) {
        const phoneNumber = window.saleData.phoneNumber;

        if (!phoneNumber) {
            alert('Please enter a valid phone number');
            return;
        }

        showOverlay('Processing payment', 'Sending your M-Pesa request...', 'loading');

        try {
            const paymentResponse = await fetch('/api/sales/payments/mpesa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    phone: phoneNumber,
                    sales_id: salesId
                })
            });

            const paymentResult = await paymentResponse.json();

            if (paymentResponse.ok && paymentResult.ResponseCode === '0') {
                const checkoutRequestId = paymentResult.CheckoutRequestID;
                window.saleData.checkoutRequestId = checkoutRequestId;
                
                showOverlay(
                    'Payment request sent!',
                    `Check your phone for the M-Pesa prompt\nTransaction ID: ${checkoutRequestId}`,
                    'accepted'
                );

                listenForCallback(salesId, checkoutRequestId);
            } else {
                const errorMsg = paymentResult.ResponseDescription || paymentResult.message || 'Payment initiation failed';
                showOverlay(
                    'Payment failed',
                    errorMsg,
                    'failed'
                );
                addRetryButton();
            }
        } catch (error) {
            console.error('Payment error:', error);
            showOverlay(
                'Payment failed',
                'Network error. Please check your connection and try again.',
                'failed'
            );
            addRetryButton();
        }
    }

    async function payWithCash(salesId) {
        showOverlay('Processing payment', 'Recording cash payment...', 'loading');

        try {
            const paymentResponse = await fetch('/api/payment/cash', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ sales_id: salesId })
            });

            const paymentResult = await paymentResponse.json();

            if (paymentResponse.ok && paymentResult.status === 'success') {
                showOverlay(
                    'Payment Successful!',
                    `Amount: KES ${window.saleData.total}\nMethod: Cash`,
                    'success'
                );
                showActionButtons();
            } else {
                showOverlay(
                    'Payment failed',
                    paymentResult.message || 'Could not record cash payment',
                    'failed'
                );
                addRetryButton();
            }
        } catch (error) {
            console.error('Payment error:', error);
            showOverlay(
                'Payment failed',
                'Network error. Please check your connection and try again.',
                'failed'
            );
            addRetryButton();
        }
    }

    async function payWithHybrid(salesId) {
        const phoneNumber = window.saleData.hybridPhoneNumber;
        const cashAmount = parseFloat(document.getElementById('hybrid-cash-amount').value);
        const mpesaAmount = parseFloat(document.getElementById('hybrid-mpesa-amount').value);

        if (!phoneNumber) {
            alert('Please enter a valid phone number');
            return;
        }

        if (isNaN(cashAmount) || isNaN(mpesaAmount) || cashAmount <= 0 || mpesaAmount <= 0) {
            alert('Enter both a cash amount and an M-Pesa amount');
            return;
        }

        showOverlay('Processing payment', 'Recording cash and sending your M-Pesa request...', 'loading');

        try {
            const paymentResponse = await fetch('/api/sales/payments/hybrid', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sales_id: salesId,
                    phone: phoneNumber,
                    cash_amount: cashAmount,
                    mpesa_amount: mpesaAmount
                })
            });

            const paymentResult = await paymentResponse.json();

            if (paymentResponse.ok && paymentResult.status === 'pending') {
                const checkoutRequestId = paymentResult.checkout_request_id;
                window.saleData.checkoutRequestId = checkoutRequestId;

                showOverlay(
                    'Cash received!',
                    `Check your phone for the M-Pesa prompt\nM-Pesa amount: KES ${mpesaAmount}\nTransaction ID: ${checkoutRequestId}`,
                    'accepted'
                );

                // Same STK-push callback the mpesa flow polls — the hybrid
                // sale only needs the M-Pesa portion confirmed.
                listenForCallback(salesId, checkoutRequestId);
            } else {
                const errorMsg = paymentResult.message || 'Hybrid payment failed';
                showOverlay('Payment failed', errorMsg, 'failed');
                addRetryButton();
            }
        } catch (error) {
            console.error('Payment error:', error);
            showOverlay(
                'Payment failed',
                'Network error. Please check your connection and try again.',
                'failed'
            );
            addRetryButton();
        }
    }

    const payBtn = document.getElementById('pay-btn');
    if (payBtn) {
        payBtn.addEventListener('click', async function(e) {
            e.preventDefault();

            const salesId = window.saleData.salesId;
            const method = window.saleData.paymentMethod || 'mpesa';

            if (method === 'mpesa') {
                await payWithMpesa(salesId);
            } else if (method === 'cash') {
                await payWithCash(salesId);
            } else if (method === 'hybrid') {
                await payWithHybrid(salesId);
            }
        });
    }

    function listenForCallback(salesId, checkoutRequestId) {
        let attempts = 0;
        const maxAttempts = 30;
        const interval = 2000;

        const checkCallback = setInterval(async () => {
            attempts++;
            
            try {
                const statusResponse = await fetch('/api/payment/mpesa/callback/status', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        sales_id: salesId,
                        checkout_request_id: checkoutRequestId
                    })
                });
                
                const statusResult = await statusResponse.json();

                if (statusResult.status === 'success') {
                    clearInterval(checkCallback);
                    updateOverlayContent(
                        'Payment Successful!',
                        `Amount: KES ${window.saleData.total}\nReceipt: ${statusResult.receipt || 'N/A'}`,
                        'success'
                    );
                    showActionButtons();
                    return;
                }
                
                if (statusResult.status === 'failed') {
                    clearInterval(checkCallback);
                    updateOverlayContent(
                        'Payment failed',
                        statusResult.message || 'Transaction declined',
                        'failed'
                    );
                    addRetryButton();
                    return;
                }
                
                if (statusResult.status === 'pending') {
                    if (attempts % 5 === 0) {
                        updateOverlayContent(
                            'Waiting for confirmation',
                            `Please check your phone and enter your PIN\n(${Math.floor(attempts * interval / 1000)}s)`,
                            'loading'
                        );
                    }
                }
                
                if (attempts >= maxAttempts) {
                    clearInterval(checkCallback);
                    updateOverlayContent(
                        'Payment timeout',
                        'Please check your M-Pesa transaction status or contact support.',
                        'pending'
                    );
                    addRetryButton();
                }
                
            } catch (error) {
                console.error('Callback check error:', error);
                if (attempts >= maxAttempts) {
                    clearInterval(checkCallback);
                    updateOverlayContent(
                        'Status check failed',
                        'Please contact support.',
                        'failed'
                    );
                    addRetryButton();
                }
            }
        }, interval);
    }

    function getStatusIcon(type) {
        const icons = {
            loading: {
                class: 'spin',
                svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9" stroke-opacity="0.25"/><path d="M21 12a9 9 0 0 0-9-9"/></svg>'
            },
            accepted: {
                class: 'pop',
                svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7Z"/></svg>'
            },
            pending: {
                class: 'pulse',
                svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>'
            },
            success: {
                class: 'pop',
                svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path class="check-path" d="M8 12.5l2.6 2.6L16 9.5"/></svg>'
            },
            failed: {
                class: 'shake',
                svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5l5 5"/><path d="M14.5 9.5l-5 5"/></svg>'
            }
        };
        return icons[type] || icons.loading;
    }

    function parseOverlayMessage(title, message) {
        const lines = message.split('\n').map(l => l.trim()).filter(Boolean);
        const metaRows = [];
        const textLines = [];

        lines.forEach(line => {
            const match = line.match(/^([A-Za-z ]{3,24}):\s*(.+)$/);
            if (match) {
                metaRows.push({ label: match[1].trim(), value: match[2].trim() });
            } else if (line) {
                textLines.push(line);
            }
        });

        return { title, textLines, metaRows };
    }

    function renderOverlayContent(title, message, type) {
        const overlay = document.getElementById('payment-overlay');
        const content = document.getElementById('overlay-content');
        
        if (!overlay || !content) return;

        const icon = getStatusIcon(type);
        const { textLines, metaRows } = parseOverlayMessage(title, message);

        content.className = 'overlay-content ' + type;

        let html = `
            <div class="status-visual">
                <div class="status-icon ${icon.class}">${icon.svg}</div>
            </div>
            <h3 class="status-title">${title}</h3>
        `;

        textLines.forEach(line => {
            html += `<p class="status-text">${line}</p>`;
        });

        if (metaRows.length) {
            html += `<div class="status-meta">`;
            metaRows.forEach(row => {
                html += `
                    <div class="status-meta-row">
                        <span class="status-meta-label">${row.label}</span>
                        <span class="status-meta-value">${row.value}</span>
                    </div>
                `;
            });
            html += `</div>`;
        }

        content.innerHTML = html;
        overlay.style.display = 'flex';
    }

    function showOverlay(title, message, type) {
        renderOverlayContent(title, message, type);
    }

    function updateOverlayContent(title, message, type) {
        renderOverlayContent(title, message, type);
    }

    function showActionButtons() {
        const content = document.getElementById('overlay-content');
        if (!content) return;

        let buttonsHTML = `
            <button class="overlay-action-btn continue-btn" onclick="window.location.href='/shop'">
                Continue Shopping
            </button>
            <div class="btn-group">
                <button class="overlay-action-btn continue-btn" onclick="window.print()">
                    Print Receipt
                </button>
                <button class="overlay-action-btn continue-btn" onclick="shareWhatsApp()">
                    WhatsApp
                </button>
                <button class="overlay-action-btn continue-btn" onclick="shareEmail()">
                    Email
                </button>
            </div>
        `;

        content.innerHTML += buttonsHTML;
    }

    function addRetryButton() {
        const content = document.getElementById('overlay-content');
        if (!content) return;

        const existingBtn = content.querySelector('.retry-btn');
        if (existingBtn) existingBtn.remove();

        const retryBtn = document.createElement('button');
        retryBtn.textContent = 'Try again';
        retryBtn.className = 'overlay-action-btn retry-btn';
        retryBtn.onclick = function() {
            const overlay = document.getElementById('payment-overlay');
            if (overlay) overlay.style.display = 'none';
            const payBtn = document.getElementById('pay-btn');
            if (payBtn) payBtn.disabled = false;
        };
        content.appendChild(retryBtn);
    }

    window.shareWhatsApp = function() {
        const total = window.saleData.total || '0.00';
        const transactionId = window.saleData.checkoutRequestId || 'N/A';
        const message = `Thank you for your purchase!\nTotal: KES ${total}\nTransaction ID: ${transactionId}`;
        const url = `https://wa.me/?text=${encodeURIComponent(message)}`;
        window.open(url, '_blank');
    };

    window.shareEmail = function() {
        const total = window.saleData.total || '0.00';
        const transactionId = window.saleData.checkoutRequestId || 'N/A';
        const subject = 'Your Purchase Receipt';
        const body = `Thank you for your purchase!\n\nTotal: KES ${total}\nTransaction ID: ${transactionId}`;
        window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    };

    const overlay = document.getElementById('payment-overlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                const content = document.getElementById('overlay-content');
                if (content && content.classList.contains('success')) {
                    this.style.display = 'none';
                }
                if (content && content.classList.contains('failed')) {
                    this.style.display = 'none';
                }
            }
        });
    }
});