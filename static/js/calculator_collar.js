/* calculator_collar.js
 *
 * Pure-function helpers for **collar-strategy** math.
 * No Schwab API calls – those are done server-side.  The helpers are
 * used on the client so the user can tweak CALL / PUT price sliders
 * without another round-trip.
 *
 * Public surface
 * --------------
 * • calculateCollarMetrics({ price, strike, callBid, callAsk,
 *                             putBid, putAsk, dte,
 *                             callPct = 50, putPct = 50 })
 *        → { netCost, collar, annReturn, strikePricePct }
 *
 * • recalcRecord(record, callPct, putPct)
 *        – returns **new** record clone with recalculated metrics
 *
 * • recalcAll(records, callPct, putPct)
 *        – bulk helper: returns new array, filters out non-profitable
 */

(function (root) {
    /** Compute collar metrics for one option pair (per-100-shares numbers). */
    function calculateCollarMetrics({
      price,
      strike,
      callBid,
      callAsk,
      putBid,
      putAsk,
      dte,
      callPct = 50,
      putPct = 50
    }) {
      // Derived CALL / PUT prices between bid-ask using percentage sliders
      const callPrice = callBid + (callPct / 100) * (callAsk - callBid);
      const putPrice  = putBid  + (putPct  / 100) * (putAsk  - putBid);
  
      const netCost   = (price - callPrice + putPrice) * 100;
      const collar    = (strike - price + callPrice - putPrice) * 100;
      const annReturn =
        netCost !== 0 ? (collar / netCost) * (365 / dte) * 100 : 0;
      const strikePct = price ? (strike / price) * 100 : 0;
  
      return { netCost, collar, annReturn, strikePricePct: strikePct };
    }
  
    /** Return a *new* record with updated metrics (leave original untouched). */
    function recalcRecord(rec, callPct, putPct) {
      const metrics = calculateCollarMetrics({
        price:   rec.price,
        strike:  rec.strike,
        callBid: rec.callBid,
        callAsk: rec.callAsk,
        putBid:  rec.putBid,
        putAsk:  rec.putAsk,
        dte:     rec.dte,
        callPct,
        putPct
      });
      return { ...rec, ...metrics };
    }
  
    /** Bulk helper → returns new array, filters out collars with ≤0 profit. */
    function recalcAll(records, callPct, putPct) {
      return records
        .map(r => recalcRecord(r, callPct, putPct))
        .filter(r => r.collar > 0);
    }
  
    /* expose to global namespace */
    root.CollarCalcUtils = {
      calculateCollarMetrics,
      recalcRecord,
      recalcAll
    };
  })(window);
  