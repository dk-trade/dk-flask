/* results_ui_put_call_spread.js
 *
 * Renders and sorts the put-call-spread-strategy results table.
 * Handles both call spread and put spread records with different columns.
 * Exposes a global ResultsUI class just like the other strategies.
 */

(() => {
    /* --------------------------------------------------------------
     * Utility
     * -------------------------------------------------------------- */
    function fmt(num) {
      if (typeof num !== "number") return num;
      return num.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }

    // Column definitions for call spreads
    const CALL_SPREAD_COLS = [
      { key: "strategyType",  label: "Strategy" },
      { key: "symbol",        label: "Symbol",           dynamicSkip: true },
      { key: "price",         label: "Price",            dynamicSkip: true },
      { key: "expDate",       label: "Expire Date" },
      { key: "dte",           label: "DTE" },
      { key: "strikePct",     label: "Strike %" },
      { key: "lowerStrike",   label: "Lower Strike" },
      { key: "upperStrike",   label: "Upper Strike" },
      { key: "spreadWidth",   label: "Spread Width" },
      { key: "paid",          label: "Paid" },
      { key: "maxGain",       label: "Max Gain" },
      { key: "pctGain",       label: "% Gain" },
      { key: "annPctGain",    label: "Ann. % Gain" }
    ];

    // Column definitions for put spreads
    const PUT_SPREAD_COLS = [
      { key: "strategyType",  label: "Strategy" },
      { key: "symbol",        label: "Symbol",           dynamicSkip: true },
      { key: "price",         label: "Price",            dynamicSkip: true },
      { key: "expDate",       label: "Expire Date" },
      { key: "dte",           label: "DTE" },
      { key: "strikePct",     label: "Strike %" },
      { key: "lowerStrike",   label: "Lower Strike" },
      { key: "higherStrike",  label: "Higher Strike" },
      { key: "spreadWidth",   label: "Spread Width" },
      { key: "creditReceived", label: "Credit Received" },
      { key: "maxRisk",       label: "Max Risk" },
      { key: "maxGain",       label: "Max Gain" },
      { key: "pctGain",       label: "% Gain" },
      { key: "annPctGain",    label: "Ann. % Gain" }
    ];

    // Unified columns for mixed display
    const UNIFIED_COLS = [
      { key: "strategyType",  label: "Strategy" },
      { key: "symbol",        label: "Symbol",           dynamicSkip: true },
      { key: "price",         label: "Price",            dynamicSkip: true },
      { key: "expDate",       label: "Expire Date" },
      { key: "dte",           label: "DTE" },
      { key: "strikePct",     label: "Strike %" },
      { key: "strikes",       label: "Strikes" },
      { key: "spreadWidth",   label: "Spread Width" },
      { key: "cost",          label: "Cost/Credit" },
      { key: "maxGain",       label: "Max Gain" },
      { key: "pctGain",       label: "% Gain" },
      { key: "annPctGain",    label: "Ann. % Gain" }
    ];

    /* --------------------------------------------------------------
     * Sorting helper – primary column asc/desc, secondary annPctGain
     * -------------------------------------------------------------- */
    function sortRecords(records, column, direction) {
      const sorted = [...records];
      sorted.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];

        // parse % strings if any
        if (typeof aVal === "string" && aVal.includes("%")) {
          aVal = parseFloat(aVal);
          bVal = parseFloat(bVal);
        }
        if (column === "symbol" || column === "expDate" || column === "strategyType") {
          aVal = aVal.toString();
          bVal = bVal.toString();
        }

        let cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        if (direction === "desc") cmp *= -1;

        // tie-break on annPctGain (descending)
        if (cmp === 0 && column !== "annPctGain") {
          cmp = b.annPctGain - a.annPctGain;
        }
        return cmp;
      });
      return sorted;
    }

    /* --------------------------------------------------------------
     * ResultsUI class
     * -------------------------------------------------------------- */
    class ResultsUI {
      constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.records   = [];
        this.sortState = { column: null, direction: null };
      }

      setRecords(arr) {
        this.records   = Array.isArray(arr) ? [...arr] : [];
        this.sortState = { column: null, direction: null };
      }

      /* -------------------- public render ------------------------ */
      render() {
        this.container.innerHTML = "";
        if (this.records.length === 0) {
          this.container.innerHTML = "<p>No results to display.</p>";
          return;
        }

        // default sort
        let rows = [...this.records];
        if (this.sortState.column) {
          rows = sortRecords(rows, this.sortState.column, this.sortState.direction);
        } else {
          rows.sort((a, b) => b.annPctGain - a.annPctGain);
        }

        // single-symbol info block
        const uniqueSyms = [...new Set(rows.map(r => r.symbol))];
        const isSingle   = uniqueSyms.length === 1;
        if (isSingle) {
          const info = document.createElement("div");
          info.className = "stock-info";
          info.innerHTML = `
            <h2>${uniqueSyms[0]}</h2>
            <p class="stock-price">Current Price: ${fmt(rows[0].price)}</p>`;
          this.container.appendChild(info);
        }

        // Apply 300-row limit
        const totalRows = rows.length;
        const displayedRows = rows.slice(0, 300);
        
        // Strategy type summary for displayed rows
        const callCount = displayedRows.filter(r => r.strategyType === "call_spread").length;
        const putCount = displayedRows.filter(r => r.strategyType === "put_spread").length;
        
        const summary = document.createElement("p");
        const limitText = totalRows > 300 ? ` (displaying first 300)` : ``;
        summary.innerHTML = `Showing ${displayedRows.length} total opportunities${limitText}: 
          <span style="color: #28a745; font-weight: bold;">${callCount} call spreads</span>, 
          <span style="color: #ffc107; font-weight: bold;">${putCount} put spreads</span>`;
        this.container.appendChild(summary);
        
        // Use displayedRows for rendering
        rows = displayedRows;

        const tblWrap = document.createElement("div");
        tblWrap.className = "table-scroll-container";
        this.container.appendChild(tblWrap);

        const table = document.createElement("table");
        table.className = "result-table";
        table.appendChild(this._createHeader(isSingle));
        const tbody = document.createElement("tbody");

        rows.forEach(r => {
          const tr = document.createElement("tr");
          // Add strategy-specific styling
          if (r.strategyType === "call_spread") {
            tr.style.borderLeft = "4px solid #28a745";
          } else if (r.strategyType === "put_spread") {
            tr.style.borderLeft = "4px solid #ffc107";
          }
          
          const cells = [];

          UNIFIED_COLS.forEach(col => {
            if (col.dynamicSkip && isSingle) return;

            let val;
            switch (col.key) {
              case "strategyType":
                val = r[col.key] === "call_spread" ? "Call Spread" : "Put Spread";
                break;
              case "price":
                val = fmt(r[col.key]);
                break;
              case "strikes":
                if (r.strategyType === "call_spread") {
                  val = `${r.lowerStrike} / ${r.upperStrike}`;
                } else {
                  val = `${r.lowerStrike} / ${r.higherStrike}`;
                }
                break;
              case "spreadWidth":
                val = fmt(r[col.key]);
                break;
              case "cost":
                if (r.strategyType === "call_spread") {
                  val = fmt(r.paid) + " (Paid)";
                } else {
                  val = fmt(r.creditReceived) + " (Credit)";
                }
                break;
              case "strikePct":
                val = r[col.key].toFixed(1) + "%";
                break;
              case "pctGain":
                val = r[col.key].toFixed(2) + "%";
                break;
              case "annPctGain":
                val = fmt(r[col.key]) + "%";
                break;
              case "maxGain":
                val = fmt(r[col.key]);
                break;
              default:
                val = r[col.key];
            }
            cells.push(`<td>${val}</td>`);
          });

          tr.innerHTML = cells.join("");
          tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        tblWrap.appendChild(table);
      }

      /* ----------------- header (sortable) ----------------------- */
      _createHeader(isSingle) {
        const thead = document.createElement("thead");
        const tr = document.createElement("tr");

        UNIFIED_COLS.forEach(col => {
          if (col.dynamicSkip && isSingle) return;
          const th = document.createElement("th");
          th.className = "sortable";
          th.dataset.column = col.key;
          th.innerHTML = `${col.label} <span class="sort-arrow"></span>`;

          if (this.sortState.column === col.key) {
            th.classList.add("sorted");
            th.querySelector(".sort-arrow").textContent =
              this.sortState.direction === "asc" ? "▲" : "▼";
          }

          th.addEventListener("click", () => this._handleSort(col.key));
          tr.appendChild(th);
        });

        thead.appendChild(tr);
        return thead;
      }

      _handleSort(column) {
        if (this.sortState.column === column) {
          // asc → desc → none
          if (this.sortState.direction === "asc") {
            this.sortState.direction = "desc";
          } else if (this.sortState.direction === "desc") {
            this.sortState.column = null;
            this.sortState.direction = null;
          }
        } else {
          this.sortState.column = column;
          this.sortState.direction = "asc";
        }
        this.render();
      }
    }

    /* expose */
    window.ResultsUI = ResultsUI;
  })();