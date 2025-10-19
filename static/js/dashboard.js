// HolidAI Dashboard JavaScript - React-like Components
// Modern ES6+ with component-based architecture

class HolidAIDashboard {
    constructor() {
        this.user = null;
        this.bookings = [];
        this.isLoggedIn = false;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuthStatus();
        this.loadDashboardData();
        this.setupDateInputs();
    }

    setupEventListeners() {
        // Form submissions
        document.getElementById('loginForm')?.addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('registerForm')?.addEventListener('submit', (e) => this.handleRegister(e));
        document.getElementById('searchForm')?.addEventListener('submit', (e) => this.handleSearch(e));
        document.getElementById('flightSearchForm')?.addEventListener('submit', (e) => this.handleFlightSearch(e));
        
        // Chat functionality
        document.getElementById('chatInput')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        // Modal controls
        this.setupModalControls();
    }

    setupModalControls() {
        // Close modals when clicking outside
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });

        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }

    setupDateInputs() {
        // Set default dates
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const nextWeek = new Date(today);
        nextWeek.setDate(nextWeek.getDate() + 7);

        // Hotel search dates
        const checkInInput = document.getElementById('checkIn');
        const checkOutInput = document.getElementById('checkOut');
        
        if (checkInInput) {
            checkInInput.value = tomorrow.toISOString().split('T')[0];
            checkInInput.min = today.toISOString().split('T')[0];
        }
        
        if (checkOutInput) {
            checkOutInput.value = nextWeek.toISOString().split('T')[0];
            checkOutInput.min = tomorrow.toISOString().split('T')[0];
        }

        // Update check-out minimum when check-in changes
        checkInInput?.addEventListener('change', (e) => {
            const checkInDate = new Date(e.target.value);
            const minCheckOut = new Date(checkInDate);
            minCheckOut.setDate(minCheckOut.getDate() + 1);
            checkOutInput.min = minCheckOut.toISOString().split('T')[0];
        });

        // Flight search dates
        const flightDepartureInput = document.getElementById('flightDepartureDate');
        const flightReturnInput = document.getElementById('flightReturnDate');
        
        if (flightDepartureInput) {
            flightDepartureInput.value = tomorrow.toISOString().split('T')[0];
            flightDepartureInput.min = today.toISOString().split('T')[0];
        }
        
        if (flightReturnInput) {
            flightReturnInput.min = tomorrow.toISOString().split('T')[0];
        }

        // Update return date minimum when departure date changes
        flightDepartureInput?.addEventListener('change', (e) => {
            const departureDate = new Date(e.target.value);
            const minReturn = new Date(departureDate);
            minReturn.setDate(minReturn.getDate() + 1);
            flightReturnInput.min = minReturn.toISOString().split('T')[0];
        });
    }

    isTokenValid(token) {
        if (!token) return false;
        
        try {
            // Decode JWT token to check expiration
            const payload = JSON.parse(atob(token.split('.')[1]));
            const now = Math.floor(Date.now() / 1000);
            return payload.exp > now;
        } catch (error) {
            return false;
        }
    }

    async checkAuthStatus() {
        const token = localStorage.getItem('holidai_token');
        const userData = localStorage.getItem('holidai_user');
        
        console.log('Checking auth status:', { token: !!token, userData: !!userData, isValid: token ? this.isTokenValid(token) : false });
        
        if (token && userData && this.isTokenValid(token)) {
            try {
                this.user = JSON.parse(userData);
                this.isLoggedIn = true;
                console.log('User logged in:', this.user.first_name);
                this.updateUserInterface();
                await this.loadUserBookings();
            } catch (error) {
                console.error('Error parsing user data:', error);
                this.logout();
            }
        } else {
            // Token invalid or missing - clear storage
            if (token && !this.isTokenValid(token)) {
                console.log('Token expired, logging out');
                this.logout();
                return;
            }
            
            // User not logged in - just update UI, don't force login
            console.log('User not logged in');
            this.user = null;
            this.isLoggedIn = false;
            this.updateUserInterface();
        }
    }

    showLoginButton() {
        // Only show login button on chat page
        const currentPath = window.location.pathname;
        if (currentPath === '/chat') {
            // Check if login button already exists
            if (!document.getElementById('loginButton')) {
                const header = document.querySelector('.header');
                if (header) {
                    const loginButton = document.createElement('button');
                    loginButton.id = 'loginButton';
                    loginButton.className = 'btn btn-primary';
                    loginButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
                    loginButton.onclick = () => this.showLoginModal();
                    
                    // Add to header
                    const headerActions = header.querySelector('.header-actions');
                    if (headerActions) {
                        headerActions.appendChild(loginButton);
                    }
                }
            }
        }
    }

    removeLoginButton() {
        // Remove login button when user logs in
        const loginButton = document.getElementById('loginButton');
        if (loginButton) {
            loginButton.remove();
        }
    }

    updateUserInterface() {
        if (this.user) {
            // Update user info
            document.getElementById('userName').textContent = `${this.user.first_name} ${this.user.last_name}`;
            document.getElementById('userEmail').textContent = this.user.email;
            document.getElementById('userAvatar').textContent = this.user.first_name.charAt(0).toUpperCase();
            
            // Update welcome message
            document.getElementById('welcomeTitle').textContent = `Welcome back, ${this.user.first_name}!`;
            document.getElementById('welcomeSubtitle').textContent = 'Ready to plan your next adventure?';
            
            // Hide login prompt
            const loginPrompt = document.getElementById('loginPrompt');
            if (loginPrompt) {
                loginPrompt.style.display = 'none';
            }
            
            // Remove login button if it exists
            this.removeLoginButton();
        } else {
            // User not logged in - show default state
            document.getElementById('userName').textContent = 'Welcome!';
            document.getElementById('userEmail').textContent = 'Please log in';
            document.getElementById('userAvatar').innerHTML = '<i class="fas fa-user"></i>';
            
            // Only update welcome message on dashboard page
            const currentPath = window.location.pathname;
            if (currentPath === '/' || currentPath === '/dashboard') {
                document.getElementById('welcomeTitle').textContent = 'Welcome to HolidAI!';
                document.getElementById('welcomeSubtitle').textContent = 'Your intelligent travel planning assistant';
                
                // Show login prompt on dashboard
                const loginPrompt = document.getElementById('loginPrompt');
                if (loginPrompt) {
                    loginPrompt.style.display = 'block';
                }
            }
            
            // Show login button on chat page
            this.showLoginButton();
        }
    }

    async loadDashboardData() {
        if (!this.isLoggedIn) return;

        try {
            // Load user bookings
            await this.loadUserBookings();
            
            // Calculate stats
            this.calculateStats();
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showNotification('Error loading dashboard data', 'error');
        }
    }

    async loadUserBookings() {
        if (!this.user) return;

        try {
            const response = await fetch(`/api/user/bookings?email=${this.user.email}`);
            const data = await response.json();
            
            if (data.success) {
                this.bookings = data.bookings;
                this.renderRecentBookings();
                this.renderUpcomingTrips();
            }
        } catch (error) {
            console.error('Error loading bookings:', error);
        }
    }

    calculateStats() {
        const totalBookings = this.bookings.length;
        const totalSpent = this.bookings.reduce((sum, booking) => sum + booking.total_cost, 0);
        const avgRating = this.bookings.length > 0 
            ? (this.bookings.reduce((sum, booking) => sum + (booking.hotel_rating || 0), 0) / this.bookings.length).toFixed(1)
            : 0;
        const citiesVisited = new Set(this.bookings.map(booking => booking.hotel_name.split(',')[0])).size;

        // Update stats display
        document.getElementById('totalBookings').textContent = totalBookings;
        document.getElementById('totalSpent').textContent = `$${totalSpent.toLocaleString()}`;
        document.getElementById('avgRating').textContent = avgRating;
        document.getElementById('citiesVisited').textContent = citiesVisited;
    }

    renderRecentBookings() {
        const container = document.getElementById('recentBookings');
        const recentBookings = this.bookings.slice(0, 3);

        if (recentBookings.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">No bookings yet</h3>
                        <p class="card-subtitle">Start by searching for hotels!</p>
                    </div>
                    <div class="card-body">
                        <button class="btn btn-primary" onclick="showSearchModal()">
                            <i class="fas fa-search"></i> Search Hotels
                        </button>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = recentBookings.map(booking => this.createBookingCard(booking)).join('');
    }

    renderUpcomingTrips() {
        const container = document.getElementById('upcomingTrips');
        const today = new Date();
        const upcomingTrips = this.bookings.filter(booking => {
            const checkInDate = new Date(booking.check_in_date);
            return checkInDate >= today && booking.status === 'confirmed';
        }).slice(0, 2);

        if (upcomingTrips.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">No upcoming trips</h3>
                        <p class="card-subtitle">Plan your next adventure!</p>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = upcomingTrips.map(booking => this.createBookingCard(booking, true)).join('');
    }

    createBookingCard(booking, isUpcoming = false) {
        const checkInDate = new Date(booking.check_in_date);
        const checkOutDate = new Date(booking.check_out_date);
        const daysUntilTrip = Math.ceil((checkInDate - new Date()) / (1000 * 60 * 60 * 24));

        return `
            <div class="booking-card">
                <div class="booking-header">
                    <div class="booking-hotel">${booking.hotel_name}</div>
                    <div class="booking-status booking-status-${booking.status}">
                        ${booking.status.charAt(0).toUpperCase() + booking.status.slice(1)}
                    </div>
                </div>
                
                <div class="booking-details">
                    <div class="booking-detail">
                        <div class="booking-detail-label">Check-in</div>
                        <div class="booking-detail-value">${checkInDate.toLocaleDateString()}</div>
                    </div>
                    <div class="booking-detail">
                        <div class="booking-detail-label">Check-out</div>
                        <div class="booking-detail-value">${checkOutDate.toLocaleDateString()}</div>
                    </div>
                    <div class="booking-detail">
                        <div class="booking-detail-label">Nights</div>
                        <div class="booking-detail-value">${booking.nights}</div>
                    </div>
                    <div class="booking-detail">
                        <div class="booking-detail-label">Guests</div>
                        <div class="booking-detail-value">${booking.guests}</div>
                    </div>
                    <div class="booking-detail">
                        <div class="booking-detail-label">Room Type</div>
                        <div class="booking-detail-value">${booking.room_type}</div>
                    </div>
                    <div class="booking-detail">
                        <div class="booking-detail-label">Total Cost</div>
                        <div class="booking-detail-value">$${booking.total_cost.toLocaleString()}</div>
                    </div>
                </div>
                
                ${isUpcoming ? `
                    <div class="booking-info">
                        <div class="badge badge-primary">
                            <i class="fas fa-calendar"></i> 
                            ${daysUntilTrip > 0 ? `${daysUntilTrip} days until trip` : 'Trip starts today!'}
                        </div>
                    </div>
                ` : ''}
                
                <div class="booking-actions">
                    <button class="btn btn-secondary btn-sm" onclick="viewBookingDetails('${booking.confirmation_number}')">
                        <i class="fas fa-eye"></i> View Details
                    </button>
                    ${booking.status === 'confirmed' ? `
                        <button class="btn btn-error btn-sm" onclick="cancelBooking('${booking.confirmation_number}')">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                this.user = data.user;
                this.isLoggedIn = true;
                localStorage.setItem('holidai_token', data.access_token);
                localStorage.setItem('holidai_user', JSON.stringify(data.user));
                
                this.closeLoginModal();
                this.updateUserInterface();
                await this.loadDashboardData();
                this.showNotification('Welcome back!', 'success');
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showNotification('Login failed. Please try again.', 'error');
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        
        const formData = {
            email: document.getElementById('registerEmail').value,
            username: document.getElementById('username').value,
            password: document.getElementById('registerPassword').value,
            first_name: document.getElementById('firstName').value,
            last_name: document.getElementById('lastName').value,
            phone: document.getElementById('phone').value
        };

        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (data.success) {
                this.user = data.user;
                this.isLoggedIn = true;
                localStorage.setItem('holidai_token', data.access_token);
                localStorage.setItem('holidai_user', JSON.stringify(data.user));
                
                this.closeRegisterModal();
                this.updateUserInterface();
                await this.loadDashboardData();
                this.showNotification('Account created successfully!', 'success');
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            console.error('Registration error:', error);
            this.showNotification('Registration failed. Please try again.', 'error');
        }
    }

    async handleSearch(e) {
        e.preventDefault();
        
        const searchData = {
            destination: document.getElementById('destination').value,
            checkIn: document.getElementById('checkIn').value,
            checkOut: document.getElementById('checkOut').value,
            guests: document.getElementById('guests').value,
            maxPrice: document.getElementById('maxPrice').value
        };

        this.closeSearchModal();
        this.openChat();
        
        // Send search query to chat
        const chatInput = document.getElementById('chatInput');
        chatInput.value = `Find hotels in ${searchData.destination} from ${searchData.checkIn} to ${searchData.checkOut} for ${searchData.guests} guests${searchData.maxPrice ? ` under $${searchData.maxPrice} per night` : ''}`;
        this.sendMessage();
    }

    async handleFlightSearch(e) {
        e.preventDefault();
        
        const flightData = {
            origin: document.getElementById('flightOrigin').value,
            destination: document.getElementById('flightDestination').value,
            departureDate: document.getElementById('flightDepartureDate').value,
            returnDate: document.getElementById('flightReturnDate').value,
            passengers: document.getElementById('flightPassengers').value,
            cabinClass: document.getElementById('flightCabinClass').value
        };

        this.closeFlightSearchModal();
        this.openChat();
        
        // Send flight search query to chat
        const chatInput = document.getElementById('chatInput');
        const returnText = flightData.returnDate ? ` and return on ${flightData.returnDate}` : '';
        chatInput.value = `Find flights from ${flightData.origin} to ${flightData.destination} departing on ${flightData.departureDate}${returnText} for ${flightData.passengers} passengers in ${flightData.cabinClass} class`;
        this.sendMessage();
    }

    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        
        if (!message) return;

        // Add user message to chat
        this.addMessageToChat(message, 'user');
        input.value = '';

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            const data = await response.json();

            if (data.success) {
                this.addMessageToChat(data.response, 'assistant');
            } else {
                this.addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
        }
    }

    addMessageToChat(message, sender) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const icon = sender === 'user' ? 'fas fa-user' : 'fas fa-robot';
        messageDiv.innerHTML = `
            <div class="message-content">
                <i class="${icon}"></i>
                ${message}
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    logout() {
        this.user = null;
        this.isLoggedIn = false;
        this.bookings = [];
        localStorage.removeItem('holidai_token');
        localStorage.removeItem('holidai_user');
        
        // Reset UI
        document.getElementById('userName').textContent = 'Welcome!';
        document.getElementById('userEmail').textContent = 'Please log in';
        document.getElementById('userAvatar').innerHTML = '<i class="fas fa-user"></i>';
        document.getElementById('welcomeTitle').textContent = 'Welcome to HolidAI!';
        document.getElementById('welcomeSubtitle').textContent = 'Your intelligent travel planning assistant';
        
        // Reset stats
        document.getElementById('totalBookings').textContent = '0';
        document.getElementById('totalSpent').textContent = '$0';
        document.getElementById('avgRating').textContent = '0.0';
        document.getElementById('citiesVisited').textContent = '0';
        
        // Reset bookings
        document.getElementById('recentBookings').innerHTML = '';
        document.getElementById('upcomingTrips').innerHTML = '';
        
        this.showLoginModal();
        this.showNotification('Logged out successfully', 'info');
    }

    closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.style.display = 'none';
        });
    }

    // Modal control methods
    showLoginModal() {
        document.getElementById('loginModal').style.display = 'flex';
    }

    closeLoginModal() {
        document.getElementById('loginModal').style.display = 'none';
    }

    showRegisterModal() {
        this.closeLoginModal();
        document.getElementById('registerModal').style.display = 'flex';
    }

    closeRegisterModal() {
        document.getElementById('registerModal').style.display = 'none';
    }

    showSearchModal() {
        if (!this.isLoggedIn) {
            this.showLoginModal();
            return;
        }
        document.getElementById('searchModal').style.display = 'flex';
    }

    closeSearchModal() {
        document.getElementById('searchModal').style.display = 'none';
    }

    showFlightSearchModal() {
        if (!this.isLoggedIn) {
            this.showLoginModal();
            return;
        }
        document.getElementById('flightSearchModal').style.display = 'flex';
    }

    closeFlightSearchModal() {
        document.getElementById('flightSearchModal').style.display = 'none';
    }

    openChat() {
        document.getElementById('chatModal').style.display = 'flex';
    }

    closeChatModal() {
        document.getElementById('chatModal').style.display = 'none';
    }

    showBookings() {
        // Implementation for showing all bookings
        this.showNotification('Booking management coming soon!', 'info');
    }

    showProfile() {
        // Implementation for profile management
        this.showNotification('Profile management coming soon!', 'info');
    }

    showAllBookings() {
        // Implementation for showing all bookings
        this.showNotification('Full booking list coming soon!', 'info');
    }

    viewBookingDetails(confirmationNumber) {
        // Implementation for viewing booking details
        this.showNotification(`Viewing details for booking ${confirmationNumber}`, 'info');
    }

    async cancelBooking(confirmationNumber) {
        if (!confirm('Are you sure you want to cancel this booking?')) return;

        try {
            const response = await fetch('/api/booking/cancel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    confirmation_number: confirmationNumber,
                    reason: 'Cancelled by user'
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Booking cancelled successfully', 'success');
                await this.loadUserBookings();
                this.calculateStats();
            } else {
                this.showNotification(data.error, 'error');
            }
        } catch (error) {
            console.error('Cancel booking error:', error);
            this.showNotification('Failed to cancel booking', 'error');
        }
    }
}

// Global functions for HTML onclick handlers
function showSearchModal() {
    dashboard.showSearchModal();
}

function closeSearchModal() {
    dashboard.closeSearchModal();
}

function showFlightSearchModal() {
    dashboard.showFlightSearchModal();
}

function closeFlightSearchModal() {
    dashboard.closeFlightSearchModal();
}

function openChat() {
    dashboard.openChat();
}

function closeChatModal() {
    dashboard.closeChatModal();
}

function sendMessage() {
    dashboard.sendMessage();
}

function showLoginModal() {
    dashboard.showLoginModal();
}

function closeLoginModal() {
    dashboard.closeLoginModal();
}

function showRegisterModal() {
    dashboard.showRegisterModal();
}

function closeRegisterModal() {
    dashboard.closeRegisterModal();
}

function logout() {
    dashboard.logout();
}

function showBookings() {
    dashboard.showBookings();
}

function showProfile() {
    dashboard.showProfile();
}

function showAllBookings() {
    dashboard.showAllBookings();
}

function viewBookingDetails(confirmationNumber) {
    dashboard.viewBookingDetails(confirmationNumber);
}

function cancelBooking(confirmationNumber) {
    dashboard.cancelBooking(confirmationNumber);
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new HolidAIDashboard();
});
