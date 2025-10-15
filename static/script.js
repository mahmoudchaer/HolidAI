// HotelPlanner Web UI JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('searchForm');
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    const errorDiv = document.getElementById('error');
    const searchBtn = document.querySelector('.search-btn');
    const btnText = document.querySelector('.btn-text');
    const btnLoading = document.querySelector('.btn-loading');

    // Set default dates
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const nextWeek = new Date(today);
    nextWeek.setDate(nextWeek.getDate() + 7);

    document.getElementById('check_in').value = tomorrow.toISOString().split('T')[0];
    document.getElementById('check_out').value = nextWeek.toISOString().split('T')[0];

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Hide previous results/errors
        resultsDiv.style.display = 'none';
        errorDiv.style.display = 'none';
        
        // Show loading state
        searchBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';
        
        try {
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            // Remove empty values
            Object.keys(data).forEach(key => {
                if (data[key] === '') {
                    delete data[key];
                }
            });
            
            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.success) {
                displayResults(result.result);
            } else {
                showError(result.error);
            }
            
        } catch (error) {
            showError('Network error: ' + error.message);
        } finally {
            // Hide loading state
            searchBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
        }
    });

    function displayResults(result) {
        let html = '';
        
        // Display trip summary
        html += `
            <div class="trip-summary" style="background: #e3f2fd; padding: 20px; border-radius: 15px; margin-bottom: 30px;">
                <h3>✈️ Trip Summary</h3>
                <p><strong>📍 Destination:</strong> ${result.city}</p>
                <p><strong>📅 Dates:</strong> ${result.check_in} to ${result.check_out}</p>
                <p><strong>🌙 Nights:</strong> ${result.nights}</p>
                <p><strong>👥 Guests:</strong> ${result.num_adults} adults, ${result.num_children} children</p>
            </div>
        `;
        
        // Display selected hotel
        if (result.selected_hotel) {
            const hotel = result.selected_hotel;
            html += `
                <div class="selected-hotel" style="background: #e8f5e8; padding: 20px; border-radius: 15px; margin-bottom: 30px;">
                    <h3>🏨 Selected Hotel</h3>
                    <div class="hotel-card">
                        <div class="hotel-name">${hotel.name}</div>
                        <div class="hotel-details">
                            <div class="hotel-detail">⭐ ${hotel.overall_rating || 'N/A'} (${hotel.reviews || 0} reviews)</div>
                            <div class="hotel-detail">🏨 ${hotel.hotel_class || 'N/A'}</div>
                        </div>
                        <div class="hotel-price">${hotel.rate_per_night?.lowest || 'N/A'}/night</div>
                        ${hotel.amenities ? `
                            <div class="hotel-amenities">
                                <strong>Amenities:</strong>
                                <div class="amenities-list">
                                    ${hotel.amenities.slice(0, 5).map(amenity => `<span class="amenity">${amenity}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        // Display budget
        if (result.budget) {
            const budget = result.budget;
            const daily = result.daily_expenses || {};
            const totalTrip = budget.total_budget + (daily.total_daily_expenses || 0) * result.nights;
            
            html += `
                <div class="budget-section">
                    <h3>💰 Budget Breakdown</h3>
                    <div class="budget-breakdown">
                        <div class="budget-item">
                            <div class="label">Accommodation</div>
                            <div class="amount">$${budget.accommodation_subtotal?.toFixed(2) || 0}</div>
                        </div>
                        <div class="budget-item">
                            <div class="label">Taxes & Fees</div>
                            <div class="amount">$${budget.taxes?.toFixed(2) || 0}</div>
                        </div>
                        <div class="budget-item">
                            <div class="label">Daily Expenses</div>
                            <div class="amount">$${daily.total_daily_expenses?.toFixed(2) || 0}/day</div>
                        </div>
                        <div class="budget-item" style="background: #667eea; color: white;">
                            <div class="label">Total Trip Cost</div>
                            <div class="amount">$${totalTrip.toFixed(2)}</div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Display nearby places
        if (result.nearby_places && result.nearby_places.length > 0) {
            html += `
                <div class="nearby-places">
                    <h3>🗺️ Nearby Places</h3>
                    ${result.nearby_places.map(place => `
                        <div class="place-item">
                            <div class="place-name">${place.name}</div>
                            <div class="place-transport">
                                ${place.transportations ? place.transportations.map(t => `${t.type}: ${t.duration}`).join(', ') : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        // Display all messages
        if (result.messages && result.messages.length > 0) {
            html += `
                <div class="messages" style="background: #f8f9fa; padding: 20px; border-radius: 15px; margin-top: 20px;">
                    <h3>📋 Process Log</h3>
                    <div style="white-space: pre-line; font-family: monospace; font-size: 0.9rem; color: #666;">
                        ${result.messages.join('\n')}
                    </div>
                </div>
            `;
        }
        
        resultsContent.innerHTML = html;
        resultsDiv.style.display = 'block';
        resultsDiv.classList.add('show');
        
        // Scroll to results
        resultsDiv.scrollIntoView({ behavior: 'smooth' });
    }

    function showError(message) {
        document.getElementById('errorMessage').textContent = message;
        errorDiv.style.display = 'block';
        errorDiv.scrollIntoView({ behavior: 'smooth' });
    }
});
