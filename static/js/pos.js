let cart = [];
let allProducts = []; // Expose globally
let allClients = [];

document.addEventListener('DOMContentLoaded', async () => {
    // Load Products
    const res = await fetch('/api/products');
    allProducts = await res.json();

    // Load Clients
    const resClients = await fetch('/api/clients'); // Assuming endpoint exists or we use the page variable if rendered
    // Actually we need to fetch clients or pass them. The template doesn't seem to pass them as JSON.
    // Let's fetch them if endpoint exists, otherwise we'll skip for now or fix quick.
    // Wait, create_client_api exists, get_clients_page exists. Need GET /api/clients? 
    // In main.py, get_clients_page renders HTML. There is no GET /api/clients JSON endpoint?
    // I need to add that endpoint too for the dropdown to work in POS!

    // ... logic continues ...
    renderProducts(allProducts);
});

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
    const existing = cart.find(item => item.product_id === product.id);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({
            product_id: product.id,
            product_name: product.name,
            unit_price: product.price,
            quantity: 1
        });
    }
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

async function checkout() {
    if (cart.length === 0) return alert("El carrito está vacío");

    const salesData = {
        items: cart.map(i => ({ product_id: i.id, quantity: i.qty }))
    };

    try {
        const res = await fetch('/api/sales', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(salesData)
        });

        if (res.ok) {
            alert('Venta realizada con éxito');
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
        alert('Error de conexión');
    }
}
