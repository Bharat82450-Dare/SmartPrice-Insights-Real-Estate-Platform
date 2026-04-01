// Configuration - Use environment variables in production
const API_BASE_URL = 'http://localhost:5000'; // Backend server URL

// DOM Elements
const elements = {
    locationSelect: document.getElementById('uiLocation'),
    areaTypeSelect: document.getElementById('uiAreaType'),
    societyContainer: document.getElementById('societyContainer'),
    loadingElement: document.getElementById('loadingSocieties'),
    applyFiltersBtn: document.getElementById('applyFilters'),
    propertyMap: document.getElementById('propertyMap'),
    errorContainer: document.getElementById('errorContainer')
};

// State
let state = {
    allSocieties: [],
    allLocations: [],
    allAreaTypes: [],
    map: null,
    markers: [],
    hoverTimeout: null
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // First verify backend connection
        if (!await testBackendConnection()) {
            return;
        }
        
        await initMap();
        await loadInitialData();
        setupEventListeners();
    } catch (error) {
        console.error("Initialization error:", error);
        showError("Failed to initialize application. Please try again later.");
    }
});

// ======================
// Core Functions
// ======================

/**
 * Tests connection to backend server
 */
async function testBackendConnection() {
    try {
        elements.loadingElement.textContent = "Connecting to server...";
        elements.loadingElement.classList.remove('hidden');
        
        const response = await fetch(`${API_BASE_URL}/api/locations`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Backend responded with status ${response.status}`);
        }
        
        return true;
    } catch (error) {
        showError("Cannot connect to server. Please ensure the backend is running.");
        console.error("Backend connection failed:", error);
        return false;
    } finally {
        elements.loadingElement.classList.add('hidden');
    }
}

/**
 * Initializes the map
 */
async function initMap() {
    state.map = L.map(elements.propertyMap).setView([12.9716, 77.5946], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(state.map);
}

/**
 * Loads initial data from backend
 */
async function loadInitialData() {
    try {
        elements.loadingElement.textContent = "Loading data...";
        elements.loadingElement.classList.remove('hidden');
        
        const [locations, areaTypes] = await Promise.all([
            fetchData('/api/locations'),
            fetchData('/api/area_types')
        ]);
        
        state.allLocations = locations;
        state.allAreaTypes = areaTypes;
        
        populateSelect(elements.locationSelect, locations);
        populateSelect(elements.areaTypeSelect, areaTypes);
        
        if (locations.length > 0) {
            await loadSocieties(locations[0]);
        }
    } catch (error) {
        console.error("Data loading error:", error);
        throw error;
    } finally {
        elements.loadingElement.classList.add('hidden');
    }
}

// ======================
// API Functions
// ======================

/**
 * Fetches data from API with proper error handling
 * @param {string} endpoint - API endpoint
 * @returns {Promise<any>} - Parsed JSON data
 */
async function fetchData(endpoint) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status && data.status !== 'success') {
            throw new Error(data.message || 'API request failed');
        }
        
        return data.locations || data.area_types || data.societies || data;
    } catch (error) {
        console.error(`API call failed for ${endpoint}:`, error);
        showError(`Failed to load data: ${error.message}`);
        throw error;
    }
}

/**
 * Loads societies for a specific location
 * @param {string} location - Location to filter societies
 */
async function loadSocieties(location) {
    try {
        elements.loadingElement.textContent = "Loading societies...";
        elements.loadingElement.classList.remove('hidden');
        elements.societyContainer.innerHTML = '';
        
        const societies = await fetchData(`/api/societies?location=${encodeURIComponent(location)}`);
        state.allSocieties = societies;
        
        renderSocieties();
        updateMapMarkers();
    } catch (error) {
        console.error("Error loading societies:", error);
        throw error;
    } finally {
        elements.loadingElement.classList.add('hidden');
    }
}

// ======================
// Rendering Functions
// ======================

/**
 * Renders societies based on current filters
 */
function renderSocieties() {
    const filters = getCurrentFilters();
    const filteredSocieties = filterSocieties(filters);
    
    if (filteredSocieties.length === 0) {
        elements.societyContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <p>No matching societies found</p>
                <button class="btn-reset" id="resetFilters">Reset Filters</button>
            </div>
        `;
        
        document.getElementById('resetFilters')?.addEventListener('click', () => {
            resetFilters();
            renderSocieties();
        });
        return;
    }
    
    elements.societyContainer.innerHTML = '';
    
    filteredSocieties.forEach(society => {
        const item = document.createElement('div');
        item.className = 'society-item';
        item.innerHTML = `
            <div class="society-info">
                <div class="society-name">${society.name}</div>
                <div class="society-location">${society.location}</div>
                <div class="society-amenities">
                    ${(society.amenities || []).slice(0, 3).map(amenity => 
                        `<span class="amenity-tag">${amenity}</span>`
                    ).join('')}
                </div>
            </div>
            <div class="society-price">₹${society.base_price}L</div>
            
            <div class="society-popup">
                <div class="popup-gallery">
                    <img src="https://source.unsplash.com/random/600x400/?apartment,${encodeURIComponent(society.name)}" 
                         alt="${society.name}" loading="lazy">
                </div>
                <div class="popup-details">
                    <div class="detail-row">
                        <span>Area Type:</span>
                        <span>${society.area_type}</span>
                    </div>
                    <div class="detail-row">
                        <span>BHK Available:</span>
                        <span>${society.bhk_available.join(', ')}</span>
                    </div>
                    <div class="detail-row">
                        <span>Area Range:</span>
                        <span>${society.min_area} - ${society.max_area} sq.ft</span>
                    </div>
                </div>
                <div class="popup-contact">
                    ${generateContactInfo(society)}
                </div>
            </div>
        `;
        
        setupSocietyItemInteractions(item, society);
        elements.societyContainer.appendChild(item);
    });
}

/**
 * Updates map markers based on current societies
 */
function updateMapMarkers() {
    // Clear existing markers
    state.markers.forEach(marker => state.map.removeLayer(marker));
    state.markers = [];
    
    // Add new markers
    state.allSocieties.forEach(society => {
        if (society.lat && society.lng) {
            const marker = L.marker([society.lat, society.lng], {
                title: society.name
            })
            .addTo(state.map)
            .bindPopup(`
                <div class="map-popup">
                    <h4>${society.name}</h4>
                    <p>${society.location}</p>
                    <p>₹${society.base_price}L</p>
                    <p>${society.bhk_available.join(', ')} BHK available</p>
                </div>
            `);
            
            state.markers.push(marker);
        }
    });
    
    // Fit map to markers if any
    if (state.markers.length > 0) {
        const markerGroup = new L.featureGroup(state.markers);
        state.map.fitBounds(markerGroup.getBounds().pad(0.2));
    }
}

// ======================
// Helper Functions
// ======================

function populateSelect(selectElement, options) {
    selectElement.innerHTML = options.map(option => 
        `<option value="${option}">${option}</option>`
    ).join('');
}

function getCurrentFilters() {
    return {
        location: elements.locationSelect.value,
        areaType: elements.areaTypeSelect.value,
        bhk: document.querySelector('input[name="filterBHK"]:checked')?.value || 'any',
        amenities: Array.from(document.querySelectorAll('input[name="uiAmenities"]:checked')).map(el => el.value)
    };
}

function filterSocieties(filters) {
    return state.allSocieties.filter(society => {
        // Location filter
        if (filters.location && society.location !== filters.location) return false;
        
        // Area type filter
        if (filters.areaType && society.area_type !== filters.areaType) return false;
        
        // BHK filter
        if (filters.bhk !== 'any' && !society.bhk_available.includes(parseInt(filters.bhk))) return false;
        
        // Amenities filter
        if (filters.amenities.length > 0 && 
            !filters.amenities.every(a => (society.amenities || []).includes(a))) return false;
            
        return true;
    });
}

function generateContactInfo(society) {
    const contacts = [
        { icon: 'phone', text: `+91 ${Math.floor(7000000000 + Math.random() * 3000000000)}` },
        { icon: 'envelope', text: `contact@${society.name.toLowerCase().replace(/\s+/g,'')}.com` },
        { icon: 'user-tie', text: ['Rajesh','Priya','Amit','Neha'][Math.floor(Math.random()*4)] },
        { icon: 'clock', text: '9AM-6PM' }
    ];
    
    return contacts.map(contact => `
        <div class="popup-contact-item">
            <i class="fas fa-${contact.icon}"></i>
            <span>${contact.text}</span>
        </div>
    `).join('');
}

function setupSocietyItemInteractions(item, society) {
    // Hover with delay
    let hoverTimer;
    
    item.addEventListener('mouseenter', () => {
        hoverTimer = setTimeout(() => {
            const popup = item.querySelector('.society-popup');
            if (popup) {
                popup.style.opacity = '1';
                popup.style.visibility = 'visible';
            }
        }, 300);
    });
    
    item.addEventListener('mouseleave', () => {
        clearTimeout(hoverTimer);
        const popup = item.querySelector('.society-popup');
        if (popup) {
            popup.style.opacity = '0';
            popup.style.visibility = 'hidden';
        }
    });
    
    // Click handling
    item.addEventListener('click', () => {
        document.querySelectorAll('.society-item').forEach(el => {
            el.classList.remove('selected');
        });
        item.classList.add('selected');
        
        if (society.lat && society.lng) {
            state.map.flyTo([society.lat, society.lng], 15);
            
            // Highlight corresponding marker
            state.markers.forEach(marker => {
                if (marker.getLatLng().lat === society.lat && 
                    marker.getLatLng().lng === society.lng) {
                    marker.openPopup();
                }
            });
        }
    });
}

function resetFilters() {
    // Reset select elements
    elements.locationSelect.selectedIndex = 0;
    elements.areaTypeSelect.selectedIndex = 0;
    
    // Reset radio buttons
    document.querySelector('input[name="filterBHK"][value="any"]').checked = true;
    
    // Reset checkboxes
    document.querySelectorAll('input[name="uiAmenities"]').forEach(checkbox => {
        checkbox.checked = false;
    });
}

function showError(message) {
    elements.errorContainer.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
        </div>
    `;
    elements.errorContainer.classList.remove('hidden');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        elements.errorContainer.classList.add('hidden');
    }, 5000);
}

// ======================
// Event Listeners
// ======================

function setupEventListeners() {
    // Location change
    elements.locationSelect.addEventListener('change', () => {
        loadSocieties(elements.locationSelect.value);
    });
    
    // Apply filters button
    elements.applyFiltersBtn.addEventListener('click', () => {
        const location = elements.locationSelect.value || state.allLocations[0];
        loadSocieties(location);
    });
    
    // Map resize handler
    window.addEventListener('resize', () => {
        if (state.map) {
            setTimeout(() => state.map.invalidateSize(), 100);
        }
    });
    
    // Error container close button
    elements.errorContainer.addEventListener('click', () => {
        elements.errorContainer.classList.add('hidden');
    });
}