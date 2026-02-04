let cart = [];
let allProducts = []; // Expose globally
let allClients = [];

document.addEventListener('DOMContentLoaded', async () => {
    // Load Products
    const res = await fetch('/api/products');
    allProducts = await res.json();

    // Load Clients
    try {
        const resClients = await fetch('/api/clients');
        if (resClients.ok) {
            allClients = await resClients.json();
            const clientSelect = document.getElementById('client-select');
            if (clientSelect) {
                // Keep default option
                clientSelect.innerHTML = '<option value="">Cliente Casual</option>';
                allClients.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.name;
                    clientSelect.appendChild(opt);
                });
            }
        }
    } catch (err) {
        console.error("Error loading clients:", err);
    }

    // ... logic continues ...
    renderProducts(allProducts);

    // Filter products
    document.getElementById('product-search').addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const filtered = allProducts.filter(p =>
            p.name.toLowerCase().includes(term) ||
            (p.barcode && p.barcode.includes(term))
        );
        renderProducts(filtered);

        // Auto-add if exact barcode match
        const exactMatch = allProducts.find(p => p.barcode === term);
        if (exactMatch) {
            addToCart(exactMatch);
            e.target.value = ''; // Clear for next scan
            renderProducts(allProducts);
        }
    });
});

function renderProducts(products) {
    const container = document.getElementById('product-results');
    container.innerHTML = products.map(p => `
        <div onclick="addToCart({id: ${p.id}, name: '${p.name}', price: ${p.price}})"
             style="cursor: pointer; padding: 12px; border: 1px solid rgba(0,0,0,0.1); border-radius: 8px; text-align: center; background: rgba(255,255,255,0.4);">
            <div style="font-weight: 600;">${p.name}</div>
            <div style="color: var(--primary-color); font-weight: 700;">$${p.price}</div>
            <div style="font-size: 0.8rem; color: #666;">Stock: ${p.stock_quantity}</div>
        </div>
    `).join('');
}

function addToCart(product) {
    const qtyInput = document.getElementById('pos-qty');
    const qty = parseInt(qtyInput.value) || 1;

    const existing = cart.find(item => item.product_id === product.id);
    if (existing) {
        existing.quantity += qty;
    } else {
        cart.push({
            product_id: product.id,
            product_name: product.name,
            unit_price: product.price,
            quantity: qty
        });
    }

    // Reset Qty to 1 after add? Optional. Let's keep it for bulk scanning.
    // qtyInput.value = 1; 

    updateCart();
}

function updateCart() {
    const tbody = document.getElementById('cart-body');
    let total = 0;

    tbody.innerHTML = cart.map(item => {
        const lineTotal = item.unit_price * item.quantity;
        total += lineTotal;
        return `
        <tr>
            <td>${item.product_name}</td>
            <td>${item.quantity}</td>
            <td>$${lineTotal.toFixed(2)}</td>
            <td><button onclick="removeFromCart(${item.product_id})" style="background:none; border:none; color: red; cursor:pointer;">&times;</button></td>
        </tr>
        `;
    }).join('');

    document.getElementById('cart-total').innerText = '$' + total.toFixed(2);
}

function removeFromCart(id) {
    cart = cart.filter(i => i.product_id !== id);
    updateCart();
}

function checkout() {
    if (cart.length === 0) return alert("El carrito está vacío");

    const clientSelect = document.getElementById('client-select');
    const clientId = clientSelect ? clientSelect.value : "";
    const clientName = clientSelect ? clientSelect.options[clientSelect.selectedIndex].text : "Casual";

    // Calculate Total
    let total = cart.reduce((acc, item) => acc + (item.unit_price * item.quantity), 0);

    // Update Modal UI
    document.getElementById('modal-total-display').textContent = '$' + total.toFixed(2);
    document.getElementById('modal-client-display').textContent = clientName;
    document.getElementById('payment-amount').value = total.toFixed(2); // Default to full payment

    // Show Modal
    document.getElementById('payment-modal').style.display = 'flex';
    document.getElementById('payment-amount').focus();
    document.getElementById('payment-amount').select();
}

function closePaymentModal() {
    document.getElementById('payment-modal').style.display = 'none';
}

async function confirmCheckout() {
    const clientSelect = document.getElementById('client-select');
    const clientId = clientSelect ? clientSelect.value : null;

    let amountPaidInput = document.getElementById('payment-amount').value;
    let amountPaid = parseFloat(amountPaidInput);

    if (isNaN(amountPaid) || amountPaid < 0) {
        return alert("Por favor ingrese un monto válido");
    }

    const salesData = {
        items: cart.map(i => ({ product_id: i.product_id, quantity: i.quantity })),
        client_id: clientId ? parseInt(clientId) : null,
        amount_paid: amountPaid
    };

    // Disable button to prevent double submit
    const btn = document.querySelector('#payment-modal .btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Procesando...";

    try {
        const res = await fetch('/api/sales', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(salesData)
        });

        if (res.ok) {
            const sale = await res.json();

            closePaymentModal();

            // Ask to print Remito
            if (confirm('Venta realizada con éxito. ¿Desea generar el Remito?')) {
                window.open(`/sales/${sale.id}/remito`, '_blank');
            }

            cart = [];
            updateCart();

            // Reload products to update stock
            const pRes = await fetch('/api/products');
            allProducts = await pRes.json();
            renderProducts(allProducts);
        } else {
            const err = await res.json();
            alert('Error: ' + err.detail);
        }
    } catch (e) {
        console.error(e);
        alert('Error de conexión o proceso: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}
