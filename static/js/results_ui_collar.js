/* results_ui_collar.js
 *
 * Renders and sorts the collar-strategy results table.
 * Exposes a global `ResultsUI` class just like the covered-call bundle,
 * so `ui_collar.js` can initialise it with:
 *
 *     const resultsUI = new ResultsUI("resultsContainer");
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
  
    // Column definitions shared by header builder & row renderer
    const COLS = [
      { key: "symbol",        label: "Symbol",      dynamicSkip: true },
      { key: "price",         label: "Price",       dynamicSkip: true },
      { key: "expDate",       label: "Expire Date" },
      { key: "dte",           label: "DTE" },
      { key: "strike",        label: "Strike" },
      { key: "strikePricePct",label: "Strike/Price %" },
      { key: "callBid",       label: "Call Bid" },
      { key: "callAsk",       label: "Call Ask" },
      { key: "callMid",       label: "Call Mid" },
      { key: "putBid",        label: "Put Bid" },
      { key: "putAsk",        label: "Put Ask" },
      { key: "putMid",        label: "Put Mid" },
      { key: "netCost",       label: "Net Cost" },
      { key: "collar",        label: "Collar (Profit)" },
      { key: "annReturn",     label: "Ann. Return %" }
    ];
  
    /* --------------------------------------------------------------
     * Sorting helper – primary column asc/desc, secondary annReturn
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
        if (column === "symbol" || column === "expDate") {
          aVal = aVal.toString();
          bVal = bVal.toString();
        }
  
        let cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        if (direction === "desc") cmp *= -1;
  
        // tie-break on annReturn (descending)
        if (cmp === 0 && column !== "annReturn") {
          cmp = b.annReturn - a.annReturn;
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
          rows.sort((a, b) => b.annReturn - a.annReturn);
        }
  
        // single-symbol info block
        const uniqueSyms = [...new Set(rows.map(r => r.symbol))];
        const isSingle   = uniqueSyms.length === 1;
        if (isSingle) {
          const info = document.createElement("div");
          info.className = "stock-info";
          info.innerHTML = `
            <h2>${uniqueSyms[0]}</h2>
            <p class="stock-price">Current Price: $${fmt(rows[0].price)}</p>`;
          this.container.appendChild(info);
        }
  
        const summary = document.createElement("p");
        summary.textContent = `Showing ${rows.length} profitable collar opportunities.`;
        this.container.appendChild(summary);
  
        const tblWrap = document.createElement("div");
        tblWrap.className = "table-scroll-container";
        this.container.appendChild(tblWrap);
  
        const table = document.createElement("table");
        table.className = "result-table";
        table.appendChild(this._createHeader(isSingle));
        const tbody = document.createElement("tbody");
  
        rows.forEach(r => {
          const tr = document.createElement("tr");
          const cells = [];
  
          COLS.forEach(col => {
            if (col.dynamicSkip && isSingle) return;
  
            let val;
            switch (col.key) {
              case "price":
              case "strike":
              case "callBid":
              case "callAsk":
              case "callMid":
              case "putBid":
              case "putAsk":
              case "putMid":
              case "netCost":
              case "collar":
                val = fmt(r[col.key]);
                break;
              case "strikePricePct":
                val = r[col.key].toFixed(2) + "%";
                break;
              case "annReturn":
                val = fmt(r[col.key]) + "%";
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
  
        COLS.forEach(col => {
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
  