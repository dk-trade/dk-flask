/* ui_put_call_spread.js
 *
 * Front-end controller for the Put-Call Spread strategy page.
 * ------------------------------------------------------------------
 * – Builds dynamic stock inputs and dual-range sliders
 * – Sends filter payload to /api/fetch-put-call-spread
 * – Renders results via ResultsUI
 * – Lets user tweak option price (0 = Bid … 100 = Ask)
 *   without extra API calls.
 */

(() => {
    /* -----------------------------------------------------------------
     * Local state
     * ----------------------------------------------------------------- */
    const LS_SAVED_STOCKS = "savedStocksPutCallSpread";
    const savedStocks = JSON.parse(localStorage.getItem(LS_SAVED_STOCKS) || "[]");

    // after first fetch we keep full raw records here for re-calculation
    let rawRecords = [];
    let resultsUI = new ResultsUI("resultsContainer");

    /* -----------------------------------------------------------------
     * Helpers – generic range slider (same mechanics as other UIs)
     * ----------------------------------------------------------------- */
    function initSlider(sliderName, { min, max, startMin, startMax, suffix,
                                      minInputId, maxInputId }) {
      const slider = document.querySelector(`[data-slider="${sliderName}"]`);
      if (!slider) return;

      const track = slider.querySelector(".range-track");
      const sel   = slider.querySelector(".range-selected");
      const tMin  = slider.querySelector(".thumb-min");
      const tMax  = slider.querySelector(".thumb-max");
      const inpMin = document.getElementById(minInputId);
      const inpMax = document.getElementById(maxInputId);
      const disp   = slider.querySelector(".range-display");

      let vMin = startMin;
      let vMax = startMax;

      const pct = v => ((v - min) / (max - min)) * 100;

      const update = () => {
        sel.style.left  = pct(vMin) + "%";
        sel.style.width = pct(vMax) - pct(vMin) + "%";
        tMin.style.left = pct(vMin) + "%";
        tMax.style.left = pct(vMax) + "%";
        inpMin.value = vMin;
        inpMax.value = vMax;
        disp.textContent = sliderName === "dte"
          ? `${vMin} – ${vMax}${suffix}`
          : `${vMin}${suffix} – ${vMax}${suffix}`;
      };

      const makeDrag = isMin => ev => {
        ev.preventDefault();
        const startX = ev.clientX ?? ev.touches[0].clientX;
        const startVal = isMin ? vMin : vMax;
        const rect = track.getBoundingClientRect();

        const onMove = e => {
          const curX = e.clientX ?? e.touches[0].clientX;
          const diff = ((curX - startX) / rect.width) * (max - min);
          let val = Math.round(startVal + diff);
          if (isMin) {
            val = Math.max(min, Math.min(val, vMax - 1));
            vMin = val;
          } else {
            val = Math.max(vMin + 1, Math.min(val, max));
            vMax = val;
          }
          update();
        };
        const stop = () => {
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("mouseup", stop);
          document.removeEventListener("touchmove", onMove);
          document.removeEventListener("touchend", stop);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", stop);
        document.addEventListener("touchmove", onMove);
        document.addEventListener("touchend", stop);
      };

      tMin.addEventListener("mousedown", makeDrag(true));
      tMin.addEventListener("touchstart", makeDrag(true));
      tMax.addEventListener("mousedown", makeDrag(false));
      tMax.addEventListener("touchstart", makeDrag(false));

      // click on track
      track.addEventListener("click", e => {
        if (e.target.classList.contains("thumb")) return;
        const rect = track.getBoundingClientRect();
        const clickPct = (e.clientX - rect.left) / rect.width;
        const val = min + Math.round(clickPct * (max - min));
        if (Math.abs(val - vMin) < Math.abs(val - vMax)) {
          vMin = Math.max(min, Math.min(val, vMax - 1));
        } else {
          vMax = Math.max(vMin + 1, Math.min(val, max));
        }
        update();
      });

      update();
    }

    function initializeRangeSliders() {
      initSlider("strike", {
        min: 0, max: 100, startMin: 30, startMax: 90,
        suffix: "%", minInputId: "minStrike", maxInputId: "maxStrike"
      });
      initSlider("dte", {
        min: 1, max: 800, startMin: 30, startMax: 90,
        suffix: " days", minInputId: "minDte", maxInputId: "maxDte"
      });
    }

    /* -----------------------------------------------------------------
     * Stock input section
     * ----------------------------------------------------------------- */
    function createStockSection() {
      const form = document.getElementById("tradeForm");
      const sec = document.createElement("div");
      sec.className = "stock-input-section";
      sec.innerHTML = `
        <div class="manual-stocks">
          <h3>Enter Stocks</h3>
          <div id="stockInputs">
            <div class="stock-input-row">
              <input type="text" class="stock-input" list="symbolList" maxlength="7" placeholder="e.g., AAPL" />
              <label class="save-label" style="display:none;">
                <input type="checkbox" class="save-stock-cb" /> Save
              </label>
            </div>
          </div>
          <button type="button" id="addStockBtn" class="add-stock-btn">+ Add More</button>
        </div>
        <div class="saved-stocks-section">
          <h3>Saved Stocks</h3>
          <div id="savedStocks" class="stock-checkboxes"></div>
        </div>`;
      form.prepend(sec);

      const renderSaved = () => {
        const cont = document.getElementById("savedStocks");
        cont.innerHTML = "";
        if (savedStocks.length === 0) {
          cont.innerHTML = '<span class="no-saved">No saved stocks.</span>';
          return;
        }
        savedStocks.forEach(s => {
          const wrap = document.createElement("div");
          wrap.className = "saved-stock-wrapper";
          wrap.innerHTML = `
            <label class="stock-checkbox"><input type="checkbox" value="${s}" /> ${s}</label>
            <button type="button" class="remove-saved-btn" data-stock="${s}">×</button>`;
          cont.appendChild(wrap);
        });
        cont.querySelectorAll(".remove-saved-btn").forEach(btn => {
          btn.addEventListener("click", ({ target }) => {
            const stk = target.dataset.stock;
            const idx = savedStocks.indexOf(stk);
            if (idx >= 0) savedStocks.splice(idx, 1);
            localStorage.setItem(LS_SAVED_STOCKS, JSON.stringify(savedStocks));
            renderSaved();
          });
        });
      };

      const toggleSaveLabel = e => {
        const lbl = e.target.parentElement.querySelector(".save-label");
        lbl.style.display = e.target.value.trim() ? "inline-flex" : "none";
        if (!e.target.value.trim()) lbl.querySelector(".save-stock-cb").checked = false;
      };

      const addInputRow = () => {
        const row = document.createElement("div");
        row.className = "stock-input-row";
        row.innerHTML = `
          <input type="text" class="stock-input" list="symbolList" maxlength="7" placeholder="e.g., AAPL" />
          <label class="save-label" style="display:none;"><input type="checkbox" class="save-stock-cb" /> Save</label>
          <button type="button" class="remove-input-btn">×</button>`;
        document.getElementById("stockInputs").appendChild(row);
        row.querySelector(".stock-input").addEventListener("input", toggleSaveLabel);
        row.querySelector(".remove-input-btn").addEventListener("click", () => row.remove());
      };

      document.getElementById("addStockBtn").addEventListener("click", addInputRow);
      form.querySelector(".stock-input").addEventListener("input", toggleSaveLabel);
      renderSaved();
    }

    function getSelectedStocks() {
      const set = new Set();
      document.querySelectorAll(".stock-input").forEach(inp => {
        const val = inp.value.trim().toUpperCase();
        if (val) {
          set.add(val);
          if (inp.parentElement.querySelector(".save-stock-cb")?.checked &&
              !savedStocks.includes(val)) {
            savedStocks.push(val);
            localStorage.setItem(LS_SAVED_STOCKS, JSON.stringify(savedStocks));
          }
        }
      });
      document.querySelectorAll("#savedStocks input:checked").forEach(cb => set.add(cb.value));
      return Array.from(set);
    }

    /* -----------------------------------------------------------------
     * Market-price slider with modern styling (simplified for combined strategy)
     * ----------------------------------------------------------------- */
    function attachSliders() {
      const wrap = document.getElementById("marketPriceOptions");
      wrap.innerHTML = `
        <style>
          .slider-container {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 12px;
            border: 1px solid #e9ecef;
            margin: 20px auto;
            max-width: 600px;
          }
          
          .slider-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
          }
          
          .slider-label {
            font-weight: 600;
            color: #495057;
            font-size: 14px;
            margin-bottom: 5px;
          }
          
          .slider-track {
            display: flex;
            align-items: center;
            gap: 12px;
          }
          
          .slider-bounds {
            font-size: 12px;
            color: #6c757d;
            min-width: 80px;
            text-align: center;
          }
          
          .modern-slider {
            flex: 1;
            height: 8px;
            border-radius: 4px;
            background: #e9ecef;
            outline: none;
            appearance: none;
            cursor: pointer;
            transition: all 0.2s ease;
          }
          
          .modern-slider::-webkit-slider-thumb {
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #007bff;
            cursor: pointer;
            border: 3px solid white;
            box-shadow: 0 2px 6px rgba(0,123,255,0.3);
            transition: all 0.2s ease;
          }
          
          .modern-slider::-webkit-slider-thumb:hover {
            background: #0056b3;
            transform: scale(1.1);
            box-shadow: 0 4px 12px rgba(0,123,255,0.4);
          }
          
          .modern-slider::-moz-range-thumb {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #007bff;
            cursor: pointer;
            border: 3px solid white;
            box-shadow: 0 2px 6px rgba(0,123,255,0.3);
          }
          
          .slider-value {
            font-weight: bold;
            color: #007bff;
            font-size: 14px;
            min-width: 50px;
            text-align: center;
            padding: 4px 8px;
            background: #e7f3ff;
            border-radius: 6px;
          }
        </style>
        
        <div class="slider-container">
          <div class="slider-group">
            <div class="slider-label">Option Pricing Strategy</div>
            <div class="slider-track">
              <span class="slider-bounds">Conservative<br><small>Safe Pricing</small></span>
              <input type="range" id="unifiedSlider" min="0" max="50" value="50" class="modern-slider">
              <span class="slider-bounds">Aggressive<br><small>Optimal Pricing</small></span>
              <span id="unifiedDisplay" class="slider-value">Mid/Mid</span>
            </div>
          </div>
        </div>`;
      wrap.style.display = "block";

      const unifiedSlider = document.getElementById("unifiedSlider");
      const unifiedDisplay = document.getElementById("unifiedDisplay");

      const recalc = () => {
        const sliderValue = +unifiedSlider.value;
        
        if (sliderValue === 50) {
          unifiedDisplay.textContent = "Mid/Mid";
        } else if (sliderValue < 50) {
          unifiedDisplay.textContent = `${Math.abs(50 - sliderValue)}% Conservative`;
        }

        // Recalculate prices for all records based on strategy type
        const recalculated = rawRecords.map(r => {
          if (r.strategyType === "call_spread") {
            // Call spread recalculation
            const buyCallPct = 100 - sliderValue;
            const sellCallPct = sliderValue;
            
            const lowerPrice = r.lowerBid + (buyCallPct / 100) * (r.lowerAsk - r.lowerBid);
            const upperPrice = r.upperBid + (sellCallPct / 100) * (r.upperAsk - r.upperBid);
            
            const paid = (lowerPrice - upperPrice) * 100;
            const maxGain = (r.spreadWidth * 100) - paid;
            const pctGain = paid > 0 ? (maxGain / paid) * 100 : 0;
            const annPctGain = r.dte > 0 ? (pctGain * 365) / r.dte : 0;
            
            return { ...r, paid, maxGain, pctGain, annPctGain };
          } else if (r.strategyType === "put_spread") {
            // Put spread recalculation
            const buyPutPct = 100 - sliderValue;
            const sellPutPct = sliderValue;
            
            const lowerPrice = r.lowerBid + (buyPutPct / 100) * (r.lowerAsk - r.lowerBid);
            const higherPrice = r.higherBid + (sellPutPct / 100) * (r.higherAsk - r.higherBid);
            
            const creditReceived = (higherPrice - lowerPrice) * 100;
            const maxRisk = (r.spreadWidth * 100) - creditReceived;
            const maxGain = creditReceived;
            const pctGain = maxRisk > 0 ? (maxGain / maxRisk) * 100 : 0;
            const annPctGain = r.dte > 0 ? (pctGain * 365) / r.dte : 0;
            
            return { ...r, creditReceived, maxRisk, maxGain, pctGain, annPctGain };
          }
          return r;
        }).filter(x => x.maxGain > 0);

        resultsUI.setRecords(recalculated);
        resultsUI.render();

        const callCount = recalculated.filter(r => r.strategyType === "call_spread").length;
        const putCount = recalculated.filter(r => r.strategyType === "put_spread").length;
        
        document.getElementById("message").textContent =
          `Found ${recalculated.length} total opportunities: ${callCount} call spreads, ${putCount} put spreads (re-calculated).`;
      };

      unifiedSlider.addEventListener("input", recalc);
    }

    /* -----------------------------------------------------------------
     * Form submit → call backend
     * ----------------------------------------------------------------- */
    document.addEventListener("DOMContentLoaded", () => {
      initializeRangeSliders();
      createStockSection();

      // Load symbol list
      async function loadSymbolList() {
        try {
          const res = await fetch("/api/symbols");
          const list = await res.json();
          const dl = document.getElementById("symbolList");
          list.forEach(s => {
            const o = document.createElement("option");
            o.value = s;
            dl.appendChild(o);
          });
        } catch (err) {
          console.error("Failed to load symbols:", err);
        }
      }
      loadSymbolList();

      document.getElementById("tradeForm").addEventListener("submit", async e => {
        e.preventDefault();
        const msg = document.getElementById("message");
        msg.textContent = "";

        const symbols = getSelectedStocks();
        if (symbols.length === 0) {
          msg.textContent = "Please select at least one stock.";
          return;
        }

        const maxSpread = +document.getElementById("maxSpread").value;
        if (maxSpread < 1 || maxSpread > 30) {
          msg.textContent = "Max spread must be between 1 and 30.";
          return;
        }

        const payload = {
          symbols,
          minStrikePct: +document.getElementById("minStrike").value,
          maxStrikePct: +document.getElementById("maxStrike").value,
          minDte: +document.getElementById("minDte").value || 1,
          maxDte: +document.getElementById("maxDte").value || 365,
          maxSpread
        };

        msg.textContent = `Loading put-call spread options for ${symbols.length} stock(s)…`;
        resultsUI.setRecords([]);
        resultsUI.render();

        try {
          const res = await fetch("/api/fetch-put-call-spread", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${res.status}`);
          }
          const data = await res.json();
          rawRecords = data.records;

          if (rawRecords.length === 0) {
            msg.textContent = "No profitable put-call spreads found.";
            return;
          }

          const callCount = rawRecords.filter(r => r.strategyType === "call_spread").length;
          const putCount = rawRecords.filter(r => r.strategyType === "put_spread").length;

          msg.textContent =
            `Found ${rawRecords.length} total opportunities: ${callCount} call spreads, ${putCount} put spreads. API calls: ${data.apiCalls}`;

          attachSliders();
          resultsUI.setRecords(rawRecords);
          resultsUI.render();
        } catch (err) {
          console.error(err);
          msg.textContent = `Error: ${err.message}`;
        }
      });
    });
  })();