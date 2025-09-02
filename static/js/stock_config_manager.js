/* stock_config_manager.js
 *
 * Stock configuration management for put-call-spread strategy.
 * Provides form-based editor for managing stock lists with individual parameters.
 */

(() => {
    let currentConfig = null;
    let configModal = null;

    /* -----------------------------------------------------------------
     * Modal Creation and Management
     * ----------------------------------------------------------------- */
    function createConfigModal() {
        const modal = document.createElement('div');
        modal.className = 'config-modal';
        modal.innerHTML = `
            <style>
                .config-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                    z-index: 1000;
                    padding: 20px;
                    box-sizing: border-box;
                    overflow-y: auto;
                }
                
                .config-content {
                    background: white;
                    border-radius: 12px;
                    width: 100%;
                    max-width: 1000px;
                    max-height: 90vh;
                    overflow-y: auto;
                    position: relative;
                    margin-top: 20px;
                }
                
                .config-header {
                    padding: 20px;
                    border-bottom: 1px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: #f8f9fa;
                    border-radius: 12px 12px 0 0;
                }
                
                .config-title {
                    margin: 0;
                    font-size: 1.5rem;
                    color: #2c3e50;
                }
                
                .close-btn {
                    background: none;
                    border: none;
                    font-size: 1.5rem;
                    cursor: pointer;
                    color: #6c757d;
                    padding: 0;
                    width: 30px;
                    height: 30px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                
                .close-btn:hover {
                    color: #dc3545;
                }
                
                .config-body {
                    padding: 20px;
                }
                
                .config-section {
                    margin-bottom: 30px;
                }
                
                .section-title {
                    font-size: 1.2rem;
                    font-weight: 600;
                    margin-bottom: 15px;
                    color: #2c3e50;
                    border-bottom: 2px solid #e9ecef;
                    padding-bottom: 8px;
                }
                
                .form-row {
                    display: flex;
                    gap: 15px;
                    margin-bottom: 15px;
                    align-items: center;
                }
                
                .form-group {
                    display: flex;
                    flex-direction: column;
                    flex: 1;
                }
                
                .form-group label {
                    font-weight: 500;
                    margin-bottom: 5px;
                    color: #495057;
                }
                
                .form-group input, .form-group textarea {
                    padding: 8px 12px;
                    border: 1px solid #ced4da;
                    border-radius: 6px;
                    font-size: 14px;
                }
                
                .form-group input:focus, .form-group textarea:focus {
                    outline: none;
                    border-color: #007bff;
                    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
                }
                
                .stock-list {
                    background: #f8f9fa;
                    border-radius: 8px;
                    padding: 15px;
                    max-height: 400px;
                    overflow-y: auto;
                }
                
                .stocks-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
                    gap: 8px;
                    margin-bottom: 20px;
                }
                
                .stock-button {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    width: 90px;
                    height: 65px;
                    border: 2px solid #e9ecef;
                    border-radius: 8px;
                    background: white;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    position: relative;
                    padding: 4px;
                }
                
                .stock-button:hover {
                    border-color: #007bff;
                    box-shadow: 0 2px 4px rgba(0, 123, 255, 0.15);
                }
                
                .stock-button.disabled {
                    opacity: 0.5;
                    background: #f5f5f5;
                }
                
                .stock-button.selected {
                    border-color: #007bff;
                    box-shadow: 0 2px 8px rgba(0, 123, 255, 0.25);
                    background: #e7f3ff;
                }
                
                .stock-symbol-btn {
                    font-weight: bold;
                    font-size: 11px;
                    color: #2c3e50;
                    margin-bottom: 2px;
                    text-align: center;
                }
                
                .stock-toggle {
                    position: absolute;
                    top: 2px;
                    right: 2px;
                    width: 14px;
                    height: 14px;
                    border-radius: 50%;
                    border: 1px solid #ccc;
                    background: #fff;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                
                .stock-toggle.enabled {
                    background: #28a745;
                    border-color: #28a745;
                }
                
                .stock-toggle.enabled::after {
                    content: '✓';
                    color: white;
                    font-size: 8px;
                    font-weight: bold;
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                }
                
                .stock-remove {
                    position: absolute;
                    top: 2px;
                    left: 2px;
                    width: 14px;
                    height: 14px;
                    border-radius: 50%;
                    background: #dc3545;
                    color: white;
                    border: none;
                    font-size: 8px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    opacity: 0;
                    transition: opacity 0.2s ease;
                }
                
                .stock-button:hover .stock-remove {
                    opacity: 1;
                }
                
                .stock-summary-btn {
                    font-size: 8px;
                    color: #6c757d;
                    text-align: center;
                    line-height: 1.1;
                }
                
                .stock-notes-indicator {
                    position: absolute;
                    bottom: 2px;
                    right: 2px;
                    font-size: 8px;
                    color: #28a745;
                }
                
                .stock-expanded-form {
                    display: none;
                    background: white;
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    padding: 15px;
                    margin-top: 15px;
                }
                
                .stock-expanded-form.show {
                    display: block;
                }
                
                .stock-controls {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }
                
                .toggle-switch {
                    position: relative;
                    width: 50px;
                    height: 24px;
                    background: #ccc;
                    border-radius: 12px;
                    cursor: pointer;
                    transition: background 0.3s;
                }
                
                .toggle-switch.enabled {
                    background: #28a745;
                }
                
                .toggle-switch::before {
                    content: '';
                    position: absolute;
                    width: 20px;
                    height: 20px;
                    border-radius: 50%;
                    background: white;
                    top: 2px;
                    left: 2px;
                    transition: transform 0.3s;
                }
                
                .toggle-switch.enabled::before {
                    transform: translateX(26px);
                }
                
                .remove-stock-btn {
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                }
                
                .remove-stock-btn:hover {
                    background: #c82333;
                }
                
                .stock-params {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                }
                
                .param-group {
                    display: flex;
                    flex-direction: column;
                }
                
                .param-label {
                    font-size: 12px;
                    color: #6c757d;
                    margin-bottom: 5px;
                    font-weight: 500;
                }
                
                .range-input-container {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .range-input {
                    flex: 1;
                }
                
                .range-value {
                    font-size: 12px;
                    font-weight: bold;
                    color: #007bff;
                    min-width: 40px;
                    text-align: center;
                }
                
                .add-stock-section {
                    display: flex;
                    gap: 10px;
                    align-items: flex-end;
                }
                
                .btn {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                
                .btn-primary {
                    background: #007bff;
                    color: white;
                }
                
                .btn-primary:hover {
                    background: #0056b3;
                }
                
                .btn-success {
                    background: #28a745;
                    color: white;
                }
                
                .btn-success:hover {
                    background: #1e7e34;
                }
                
                .btn-outline {
                    background: white;
                    color: #6c757d;
                    border: 1px solid #ced4da;
                }
                
                .btn-outline:hover {
                    background: #f8f9fa;
                }
                
                .bulk-actions {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 15px;
                    flex-wrap: wrap;
                }
                
                .bulk-actions button {
                    font-size: 12px;
                    padding: 6px 12px;
                }
                
                .notes-textarea {
                    resize: vertical;
                    min-height: 40px;
                }
                
                .config-footer {
                    padding: 20px;
                    border-top: 1px solid #e9ecef;
                    display: flex;
                    justify-content: flex-end;
                    gap: 10px;
                    background: #f8f9fa;
                    border-radius: 0 0 12px 12px;
                }
            </style>
            
            <div class="config-content">
                <div class="config-header">
                    <h2 class="config-title">Stock Configuration Manager</h2>
                    <button class="close-btn" onclick="closeConfigModal()">&times;</button>
                </div>
                
                <div class="config-body">
                    <!-- Basic Config Section -->
                    <div class="config-section">
                        <h3 class="section-title">Basic Configuration</h3>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="configName">Configuration Name</label>
                                <input type="text" id="configName" placeholder="My Put-Call Spreads">
                            </div>
                            <div class="form-group">
                                <label for="configDescription">Description</label>
                                <input type="text" id="configDescription" placeholder="Description of this configuration">
                            </div>
                        </div>
                    </div>
                    
                    <!-- Default Parameters Section -->
                    <div class="config-section">
                        <h3 class="section-title">Default Parameters</h3>
                        <p style="color: #6c757d; font-size: 14px; margin-bottom: 15px;">
                            These parameters will be used as defaults for new stocks and bulk updates.
                        </p>
                        <div id="defaultParamsContainer"></div>
                    </div>
                    
                    <!-- Stock List Section -->
                    <div class="config-section">
                        <h3 class="section-title">Stock List</h3>
                        
                        <!-- Bulk Actions -->
                        <div class="bulk-actions">
                            <button class="btn btn-outline" onclick="applyDefaultsToAll()">Apply Defaults to All</button>
                            <button class="btn btn-outline" onclick="enableAllStocks()">Enable All</button>
                            <button class="btn btn-outline" onclick="disableAllStocks()">Disable All</button>
                        </div>
                        
                        <!-- Stock List -->
                        <div class="stock-list" id="stockList"></div>
                        
                        <!-- Add New Stock -->
                        <div class="add-stock-section">
                            <div class="form-group" style="flex: 1;">
                                <label for="newStockSymbol">Add New Stock</label>
                                <input type="text" id="newStockSymbol" placeholder="Enter symbol (e.g., AAPL)" 
                                       style="text-transform: uppercase;" maxlength="7">
                            </div>
                            <button class="btn btn-primary" onclick="addNewStock()" style="margin-top: 25px;">Add Stock</button>
                        </div>
                    </div>
                </div>
                
                <div class="config-footer">
                    <button class="btn btn-outline" onclick="closeConfigModal()">Cancel</button>
                    <button class="btn btn-success" onclick="saveConfiguration()">Save Configuration</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        return modal;
    }

    /* -----------------------------------------------------------------
     * Parameter Slider Creation
     * ----------------------------------------------------------------- */
    function createParameterSliders(containerId, params, prefix = '') {
        const container = document.getElementById(containerId);
        container.innerHTML = `
            <div class="stock-params">
                <div class="param-group">
                    <div class="param-label">Min Strike %</div>
                    <div class="range-input-container">
                        <input type="range" class="range-input" id="${prefix}minStrike" 
                               min="0" max="100" value="${params.minStrikePct || 30}">
                        <span class="range-value" id="${prefix}minStrikeValue">${params.minStrikePct || 30}%</span>
                    </div>
                </div>
                
                <div class="param-group">
                    <div class="param-label">Max Strike %</div>
                    <div class="range-input-container">
                        <input type="range" class="range-input" id="${prefix}maxStrike" 
                               min="0" max="100" value="${params.maxStrikePct || 90}">
                        <span class="range-value" id="${prefix}maxStrikeValue">${params.maxStrikePct || 90}%</span>
                    </div>
                </div>
                
                <div class="param-group">
                    <div class="param-label">Min DTE</div>
                    <div class="range-input-container">
                        <input type="range" class="range-input" id="${prefix}minDte" 
                               min="1" max="365" value="${params.minDte || 30}">
                        <span class="range-value" id="${prefix}minDteValue">${params.minDte || 30}</span>
                    </div>
                </div>
                
                <div class="param-group">
                    <div class="param-label">Max DTE</div>
                    <div class="range-input-container">
                        <input type="range" class="range-input" id="${prefix}maxDte" 
                               min="1" max="365" value="${params.maxDte || 90}">
                        <span class="range-value" id="${prefix}maxDteValue">${params.maxDte || 90}</span>
                    </div>
                </div>
                
                <div class="param-group">
                    <div class="param-label">Max Spread</div>
                    <div class="range-input-container">
                        <input type="range" class="range-input" id="${prefix}maxSpread" 
                               min="1" max="30" value="${params.maxSpread || 20}">
                        <span class="range-value" id="${prefix}maxSpreadValue">${params.maxSpread || 20}</span>
                    </div>
                </div>
            </div>
        `;
        
        // Add event listeners for real-time updates
        ['minStrike', 'maxStrike', 'minDte', 'maxDte', 'maxSpread'].forEach(param => {
            const slider = document.getElementById(prefix + param);
            const value = document.getElementById(prefix + param + 'Value');
            if (slider && value) {
                slider.addEventListener('input', () => {
                    const suffix = param.includes('Strike') ? '%' : '';
                    value.textContent = slider.value + suffix;
                });
            }
        });
    }

    /* -----------------------------------------------------------------
     * Stock Management Functions
     * ----------------------------------------------------------------- */
    function renderStockList() {
        const container = document.getElementById('stockList');
        container.innerHTML = '';
        
        if (!currentConfig.stocks || currentConfig.stocks.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #6c757d; padding: 20px;">No stocks configured. Add a stock below.</p>';
            return;
        }
        
        // Create grid container
        const gridContainer = document.createElement('div');
        gridContainer.className = 'stocks-grid';
        
        currentConfig.stocks.forEach((stock, index) => {
            // Create short summary
            const summary = `${stock.minStrikePct || 'D'}%-${stock.maxStrikePct || 'D'}%\n${stock.minDte || 'D'}-${stock.maxDte || 'D'}d`;
            
            const stockButton = document.createElement('div');
            stockButton.className = `stock-button ${stock.enabled === false ? 'disabled' : ''}`;
            stockButton.setAttribute('data-stock-index', index);
            
            stockButton.innerHTML = `
                <div class="stock-toggle ${stock.enabled !== false ? 'enabled' : ''}" 
                     onclick="event.stopPropagation(); toggleStock(${index})"></div>
                <button class="stock-remove" onclick="event.stopPropagation(); removeStock(${index})">×</button>
                <div class="stock-symbol-btn">${stock.symbol}</div>
                <div class="stock-summary-btn">${summary}</div>
                ${stock.notes ? '<div class="stock-notes-indicator">📝</div>' : ''}
            `;
            
            stockButton.addEventListener('click', () => toggleStockExpansion(index));
            gridContainer.appendChild(stockButton);
        });
        
        container.appendChild(gridContainer);
        
        // Create expanded form container (initially hidden)
        const expandedForm = document.createElement('div');
        expandedForm.id = 'expandedStockForm';
        expandedForm.className = 'stock-expanded-form';
        expandedForm.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h4 id="expandedStockTitle" style="margin: 0; color: #2c3e50;">Stock Parameters</h4>
                <button onclick="closeExpandedForm()" style="background: none; border: none; font-size: 18px; cursor: pointer;">&times;</button>
            </div>
            <div id="expandedStockParams"></div>
            <div class="form-group" style="margin-top: 15px;">
                <label>Notes</label>
                <textarea id="expandedStockNotes" class="notes-textarea" 
                          placeholder="Optional notes about this stock"></textarea>
            </div>
        `;
        
        container.appendChild(expandedForm);
    }

    /* -----------------------------------------------------------------
     * Stock expansion/collapse functionality
     * ----------------------------------------------------------------- */
    window.toggleStockExpansion = function(index) {
        const stockButton = document.querySelector(`[data-stock-index="${index}"]`);
        const expandedForm = document.getElementById('expandedStockForm');
        const isCurrentlySelected = stockButton.classList.contains('selected');
        
        // Clear all selections
        document.querySelectorAll('.stock-button.selected').forEach(btn => {
            btn.classList.remove('selected');
        });
        
        if (!isCurrentlySelected) {
            // Select this stock and show expanded form
            stockButton.classList.add('selected');
            expandedForm.classList.add('show');
            
            const stock = currentConfig.stocks[index];
            document.getElementById('expandedStockTitle').textContent = `${stock.symbol} Parameters`;
            document.getElementById('expandedStockNotes').value = stock.notes || '';
            
            // Store current editing index
            expandedForm.setAttribute('data-editing-index', index);
            
            // Create parameter sliders
            createParameterSliders('expandedStockParams', stock, `expanded_`);
        } else {
            // Hide expanded form
            expandedForm.classList.remove('show');
        }
    };
    
    window.closeExpandedForm = function() {
        document.querySelectorAll('.stock-button.selected').forEach(btn => {
            btn.classList.remove('selected');
        });
        document.getElementById('expandedStockForm').classList.remove('show');
    };

    /* -----------------------------------------------------------------
     * Global Functions (exposed to window for onclick handlers)
     * ----------------------------------------------------------------- */
    window.openConfigModal = async function() {
        try {
            // Load current configuration
            const response = await fetch('/api/config/put-call-spread');
            if (response.ok) {
                currentConfig = await response.json();
            } else {
                // Use default config
                currentConfig = {
                    name: "My Put-Call Spreads",
                    description: "Combined put and call spread opportunities",
                    defaultParams: {
                        minStrikePct: 30,
                        maxStrikePct: 90,
                        minDte: 30,
                        maxDte: 90,
                        maxSpread: 20
                    },
                    stocks: []
                };
            }
            
            // Create and show modal
            configModal = createConfigModal();
            
            // Populate form fields
            document.getElementById('configName').value = currentConfig.name || '';
            document.getElementById('configDescription').value = currentConfig.description || '';
            
            // Create default parameter sliders
            createParameterSliders('defaultParamsContainer', currentConfig.defaultParams, 'default_');
            
            // Render stock list
            renderStockList();
            
        } catch (error) {
            console.error('Error loading configuration:', error);
            alert('Failed to load configuration: ' + error.message);
        }
    };

    window.closeConfigModal = function() {
        if (configModal) {
            configModal.remove();
            configModal = null;
        }
    };

    window.addNewStock = function() {
        const symbolInput = document.getElementById('newStockSymbol');
        const symbol = symbolInput.value.trim().toUpperCase();
        
        if (!symbol) {
            alert('Please enter a stock symbol');
            return;
        }
        
        if (currentConfig.stocks.some(s => s.symbol === symbol)) {
            alert('Stock already exists in the list');
            return;
        }
        
        // Create new stock with default parameters
        const newStock = {
            symbol: symbol,
            enabled: true,
            ...currentConfig.defaultParams,
            notes: ""
        };
        
        currentConfig.stocks.push(newStock);
        symbolInput.value = '';
        renderStockList();
    };

    window.removeStock = function(index) {
        if (confirm(`Remove ${currentConfig.stocks[index].symbol} from the list?`)) {
            currentConfig.stocks.splice(index, 1);
            renderStockList();
        }
    };

    window.toggleStock = function(index) {
        currentConfig.stocks[index].enabled = !currentConfig.stocks[index].enabled;
        renderStockList();
    };

    window.applyDefaultsToAll = function() {
        if (confirm('Apply default parameters to all stocks? This will overwrite individual settings.')) {
            currentConfig.stocks.forEach(stock => {
                Object.assign(stock, {
                    ...currentConfig.defaultParams,
                    symbol: stock.symbol,
                    enabled: stock.enabled,
                    notes: stock.notes
                });
            });
            renderStockList();
        }
    };

    window.enableAllStocks = function() {
        currentConfig.stocks.forEach(stock => stock.enabled = true);
        renderStockList();
    };

    window.disableAllStocks = function() {
        currentConfig.stocks.forEach(stock => stock.enabled = false);
        renderStockList();
    };

    window.saveConfiguration = function() {
        try {
            // Update basic config
            currentConfig.name = document.getElementById('configName').value;
            currentConfig.description = document.getElementById('configDescription').value;
            
            // Update default parameters
            currentConfig.defaultParams = {
                minStrikePct: parseInt(document.getElementById('default_minStrike').value),
                maxStrikePct: parseInt(document.getElementById('default_maxStrike').value),
                minDte: parseInt(document.getElementById('default_minDte').value),
                maxDte: parseInt(document.getElementById('default_maxDte').value),
                maxSpread: parseInt(document.getElementById('default_maxSpread').value)
            };
            
            // Update individual stock parameters and notes
            currentConfig.stocks.forEach((stock, index) => {
                // Only update if stock is currently being edited in expanded form
                const expandedForm = document.getElementById('expandedStockForm');
                const editingIndex = expandedForm?.getAttribute('data-editing-index');
                
                if (editingIndex == index && expandedForm.classList.contains('show')) {
                    // Update from expanded form
                    const prefix = `expanded_`;
                    stock.minStrikePct = parseInt(document.getElementById(prefix + 'minStrike')?.value || stock.minStrikePct);
                    stock.maxStrikePct = parseInt(document.getElementById(prefix + 'maxStrike')?.value || stock.maxStrikePct);
                    stock.minDte = parseInt(document.getElementById(prefix + 'minDte')?.value || stock.minDte);
                    stock.maxDte = parseInt(document.getElementById(prefix + 'maxDte')?.value || stock.maxDte);
                    stock.maxSpread = parseInt(document.getElementById(prefix + 'maxSpread')?.value || stock.maxSpread);
                    stock.notes = document.getElementById('expandedStockNotes')?.value || '';
                }
            });
            
            // Save to backend
            fetch('/api/config/put-call-spread', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(currentConfig)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Configuration saved successfully!');
                    closeConfigModal();
                } else {
                    throw new Error(data.error || 'Save failed');
                }
            })
            .catch(error => {
                console.error('Error saving configuration:', error);
                alert('Failed to save configuration: ' + error.message);
            });
            
        } catch (error) {
            console.error('Error preparing configuration:', error);
            alert('Error preparing configuration: ' + error.message);
        }
    };

    // Close modal on background click
    document.addEventListener('click', function(event) {
        if (configModal && event.target === configModal) {
            closeConfigModal();
        }
    });

    // Handle Enter key in new stock input
    document.addEventListener('keypress', function(event) {
        if (event.target.id === 'newStockSymbol' && event.key === 'Enter') {
            addNewStock();
        }
    });

})();