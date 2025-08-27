/* calculator_call_spread.js
 *
 * Pure-function helpers for call-spread-strategy math.
 * No Schwab API calls – those are done server-side. The helpers are
 * used on the client so the user can tweak option price sliders
 * without another round-trip.
 *
 * Public surface
 * --------------
 * • calculateCallSpreadMetrics({ lowerBid, lowerAsk, upperBid, upperAsk,
 *                                 spreadWidth, dte, pct = 50 })
 *        → { paid, maxGain, pctGain, annPctGain }
 *
 * • recalcRecord(record, pct)
 *        – returns new record clone with recalculated metrics
 *
 * • recalcAll(records, pct)
 *        – bulk helper: returns new array, filters out non-profitable
 */

(function (root) {
    /** Compute call spread metrics for one spread (per-100-shares numbers). */
    function calculateCallSpreadMetrics({
      lowerBid,
      lowerAsk, 
      upperBid,
      upperAsk,
      spreadWidth,
      dte,
      pct = 50
    }) {
      // Derived option prices between bid-ask using percentage slider
      const lowerPrice = lowerBid + (pct / 100) * (lowerAsk - lowerBid);
      const upperPrice = upperBid + (pct / 100) * (upperAsk - upperBid);

      const paid = (lowerPrice - upperPrice) * 100;  // Net debit paid
      const maxGain = (spreadWidth * 100) - paid;    // Max profit
      const pctGain = paid > 0 ? (maxGain / paid) * 100 : 0;
      const annPctGain = dte > 0 ? (pctGain * 365) / dte : 0;

      return { paid, maxGain, pctGain, annPctGain };
    }

    /** Return a new record with updated metrics (leave original untouched). */
    function recalcRecord(rec, pct) {
      const metrics = calculateCallSpreadMetrics({
        lowerBid: rec.lowerBid,
        lowerAsk: rec.lowerAsk,
        upperBid: rec.upperBid,
        upperAsk: rec.upperAsk,
        spreadWidth: rec.spreadWidth,
        dte: rec.dte,
        pct
      });
      return { ...rec, ...metrics };
    }

    /** Bulk helper → returns new array, filters out spreads with ≤0 profit. */
    function recalcAll(records, pct) {
      return records
        .map(r => recalcRecord(r, pct))
        .filter(r => r.maxGain > 0);
    }

    /* expose to global namespace */
    root.CallSpreadCalcUtils = {
      calculateCallSpreadMetrics,
      recalcRecord,
      recalcAll
    };
  })(window);