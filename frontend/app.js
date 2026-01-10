const API_URL = '/api';

let coins = [];
let cart = [];
let currentFilter = 'all';
let currentOrderId = null;
let currentUser = null;

async function checkAuth() {
    try {
        const response = await fetch(`${API_URL}/auth/me`);
        const data = await response.json();
        currentUser = data.user;
        updateAuthStatus();
    } catch (error) {
        console.error('Error checking auth:', error);
    }
}

function updateAuthStatus() {
    const authStatus = document.getElementById('auth-status');
    if (!authStatus) return;

    if (currentUser) {
        let html = `<span class="user-greeting">Hi, ${currentUser.username}</span>`;
        if (currentUser.is_admin) {
            html += `<a href="/manage" class="nav-btn manage-btn">Manage</a>`;
            html += `<a href="/admin" class="nav-btn">Orders</a>`;
        } else {
            html += `<a href="/orders" class="nav-btn">My Orders</a>`;
        }
        html += `<button onclick="logout()" class="nav-btn logout-btn">Logout</button>`;
        authStatus.innerHTML = html;
    } else {
        authStatus.innerHTML = `
            <a href="/login" class="nav-btn signin-btn">Sign In</a>
            <a href="/register" class="nav-btn signup-btn">Sign Up</a>
        `;
    }
}

async function logout() {
    await fetch(`${API_URL}/auth/logout`, { method: 'POST' });
    currentUser = null;
    updateAuthStatus();
}

async function fetchCoins() {
    try {
        const response = await fetch(`${API_URL}/coins`);
        coins = await response.json();
        renderCoins();
    } catch (error) {
        console.error('Error fetching coins:', error);
    }
}

function renderCoins() {
    const grid = document.getElementById('coins-grid');
    const filteredCoins = currentFilter === 'all'
        ? coins
        : coins.filter(c => c.metal === currentFilter);

    grid.innerHTML = filteredCoins.map(coin => `
        <div class="coin-card" onclick="viewCoin('${coin._id}')">
            <img class="coin-image" src="${coin.image_url || 'https://via.placeholder.com/300x200?text=Coin'}" alt="${coin.name}">
            <div class="coin-content">
                <h3 class="coin-name">${coin.name}</h3>
                <p class="coin-description">${coin.description}</p>
                <div class="coin-tags">
                    <span class="coin-tag">${coin.metal}</span>
                    <span class="coin-tag">${coin.weight_grams}g</span>
                    <span class="coin-tag">${coin.country}</span>
                    <span class="coin-tag">${coin.year}</span>
                </div>
                <div class="coin-footer">
                    <div class="coin-price">$${coin.price.toLocaleString()}</div>
                    <div class="coin-stock">${coin.stock} in stock</div>
                    <button class="add-to-cart" onclick="event.stopPropagation(); addToCart('${coin._id}')" ${coin.stock === 0 ? 'disabled' : ''}>
                        ${coin.stock === 0 ? 'Out of Stock' : 'Add to Cart'}
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function viewCoin(coinId) {
    window.location.href = `/coin/${coinId}`;
}

function addToCart(coinId) {
    const coin = coins.find(c => c._id === coinId);
    if (!coin) return;

    const existingItem = cart.find(item => item.coin_id === coinId);
    if (existingItem) {
        if (existingItem.quantity < coin.stock) {
            existingItem.quantity++;
        }
    } else {
        cart.push({ coin_id: coinId, quantity: 1, coin });
    }
    updateCart();
}

function removeFromCart(coinId) {
    const index = cart.findIndex(item => item.coin_id === coinId);
    if (index > -1) {
        if (cart[index].quantity > 1) {
            cart[index].quantity--;
        } else {
            cart.splice(index, 1);
        }
    }
    updateCart();
}

function updateCart() {
    const cartItems = document.getElementById('cart-items');
    const cartCount = document.getElementById('cart-count');
    const cartTotal = document.getElementById('cart-total');

    cartCount.textContent = cart.reduce((sum, item) => sum + item.quantity, 0);

    const total = cart.reduce((sum, item) => sum + (item.coin.price * item.quantity), 0);
    cartTotal.textContent = total.toLocaleString(undefined, { minimumFractionDigits: 2 });

    cartItems.innerHTML = cart.map(item => `
        <div class="cart-item">
            <div class="cart-item-info">
                <h4>${item.coin.name}</h4>
                <p>$${item.coin.price.toLocaleString()} x ${item.quantity}</p>
            </div>
            <div class="cart-item-actions">
                <button onclick="removeFromCart('${item.coin_id}')">-</button>
                <span>${item.quantity}</span>
                <button onclick="addToCart('${item.coin_id}')">+</button>
            </div>
        </div>
    `).join('');
}

function toggleCart() {
    document.getElementById('cart-sidebar').classList.toggle('open');
    document.getElementById('cart-overlay').classList.toggle('open');
}

function checkout() {
    if (cart.length === 0) return;
    document.getElementById('checkout-modal').classList.add('open');
}

function closeModal() {
    document.getElementById('checkout-modal').classList.remove('open');
}

document.getElementById('checkout-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const order = {
        customer_name: document.getElementById('customer-name').value,
        customer_email: document.getElementById('customer-email').value,
        items: cart.map(item => ({ coin_id: item.coin_id, quantity: item.quantity })),
        payment_method: 'twint'
    };

    try {
        const response = await fetch(`${API_URL}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(order)
        });

        if (response.ok) {
            const createdOrder = await response.json();
            currentOrderId = createdOrder._id;

            // Show payment modal with amount
            const total = cart.reduce((sum, item) => sum + (item.coin.price * item.quantity), 0);
            document.getElementById('payment-amount').textContent = total.toLocaleString(undefined, { minimumFractionDigits: 2 });

            closeModal();
            document.getElementById('payment-modal').classList.add('open');
        } else {
            const error = await response.json();
            alert(error.detail || 'Error placing order');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error placing order');
    }
});

async function confirmPayment() {
    if (!currentOrderId) return;

    try {
        const response = await fetch(`${API_URL}/orders/${currentOrderId}/confirm-payment`, {
            method: 'POST'
        });

        if (response.ok) {
            document.getElementById('payment-modal').classList.remove('open');
            alert('Payment successful! Thank you for your order.');
            cart = [];
            currentOrderId = null;
            updateCart();
            toggleCart();
            fetchCoins();
            document.getElementById('checkout-form').reset();
        } else {
            const error = await response.json();
            alert(error.detail || 'Payment failed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Payment failed');
    }
}

function cancelPayment() {
    document.getElementById('payment-modal').classList.remove('open');
    currentOrderId = null;
}

document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.metal;
        renderCoins();
    });
});

checkAuth();
fetchCoins();
