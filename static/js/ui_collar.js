/* ui_collar.js
 *
 * Front-end controller for the **Collar** strategy page.
 * ------------------------------------------------------------------
 * – Builds dynamic stock inputs and dual-range sliders
 * – Sends filter payload to `/api/fetch-collar`
 * – Renders results via ResultsUI
 * – Lets user tweak CALL-sell / PUT-buy price (0 = Bid … 100 = Ask)
 *   without extra API calls.
 */

(() => {
    /* -----------------------------------------------------------------
     * Local state
     * ----------------------------------------------------------------- */
    const LS_SAVED_STOCKS = "savedStocksCollar";
    const savedStocks = JSON.parse(localStorage.getItem(LS_SAVED_STOCKS) || "[]");
  
    // after first fetch we keep full raw records here for re-calculation
    let rawRecords = [];
    let resultsUI = new ResultsUI("resultsContainer");
  
    /* -----------------------------------------------------------------
     * Helpers – generic range slider (same mechanics as covered-call UI)
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
        min: 0, max: 100, startMin: 75, startMax: 80,
        suffix: "%", minInputId: "minStrike", maxInputId: "maxStrike"
      });
      initSlider("dte", {
        min: 1, max: 800, startMin: 29, startMax: 45,
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
     * Market-price sliders (CALL % and PUT %)
     * ----------------------------------------------------------------- */
    function attachPriceSliders() {
      const wrap = document.getElementById("marketPriceOptions");
      wrap.innerHTML = `
        <div class="price-slider-group">
          <label>CALL Sell Price: <span id="callPriceDisplay">50%</span></label>
          <input type="range" id="callPriceSlider" min="0" max="100" value="50">
        </div>
        <div class="price-slider-group">
          <label>PUT Buy Price: <span id="putPriceDisplay">50%</span></label>
          <input type="range" id="putPriceSlider" min="0" max="100" value="50">
        </div>`;
      wrap.style.display = "block";
  
      const callSlider = document.getElementById("callPriceSlider");
      const putSlider  = document.getElementById("putPriceSlider");
      const callDisp   = document.getElementById("callPriceDisplay");
      const putDisp    = document.getElementById("putPriceDisplay");
  
      const recalc = () => {
        const cPct = +callSlider.value;
        const pPct = +putSlider.value;
        callDisp.textContent = `${cPct}%`;
        putDisp.textContent  = `${pPct}%`;
  
        const recalculated = rawRecords.map(r => {
          const callPrice = r.callBid + (cPct / 100) * (r.callAsk - r.callBid);
          const putPrice  = r.putBid  + (pPct / 100) * (r.putAsk  - r.putBid);
          const netCost = (r.price - callPrice + putPrice) * 100;
          const collar  = (r.strike - r.price + callPrice - putPrice) * 100;
          const annReturn = (collar / netCost) * (365 / r.dte) * 100;
          return { ...r, netCost, collar, annReturn };
        }).filter(x => x.collar > 0);
  
        resultsUI.setRecords(recalculated);
        resultsUI.render();
  
        document.getElementById("message").textContent =
          `Found ${recalculated.length} profitable collar positions (re-calculated).`;
      };
  
      callSlider.addEventListener("input", recalc);
      putSlider.addEventListener("input", recalc);
    }
  
    /* -----------------------------------------------------------------
     * Form submit → call backend
     * ----------------------------------------------------------------- */
    document.addEventListener("DOMContentLoaded", () => {
      initializeRangeSliders();
      createStockSection();
  
      document.getElementById("tradeForm").addEventListener("submit", async e => {
        e.preventDefault();
        const msg = document.getElementById("message");
        msg.textContent = "";
  
        const symbols = getSelectedStocks();
        if (symbols.length === 0) {
          msg.textContent = "Please select at least one stock.";
          return;
        }
  
        const payload = {
          symbols,
          minStrikePct: +document.getElementById("minStrike").value,
          maxStrikePct: +document.getElementById("maxStrike").value,
          minDte: +document.getElementById("minDte").value || 1,
          maxDte: +document.getElementById("maxDte").value || 365
        };
  
        msg.textContent = `Loading collar options for ${symbols.length} stock(s)…`;
        resultsUI.setRecords([]);
        resultsUI.render();
  
        try {
          const res = await fetch("/api/fetch-collar", {
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
            msg.textContent = "No profitable collar positions found.";
            return;
          }
  
          msg.textContent =
            `Found ${rawRecords.length} profitable collar positions. API calls: ${data.apiCalls}`;
  
          attachPriceSliders();          // show price tweak sliders
          resultsUI.setRecords(rawRecords);
          resultsUI.render();
        } catch (err) {
          console.error(err);
          msg.textContent = `Error: ${err.message}`;
        }
      });
    });
  })();
  