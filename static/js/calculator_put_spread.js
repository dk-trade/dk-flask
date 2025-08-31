/* calculator_put_spread.js
 *
 * Pure-function helpers for put-spread-strategy math.
 * No Schwab API calls – those are done server-side. The helpers are
 * used on the client so the user can tweak option price sliders
 * without another round-trip.
 *
 * Public surface
 * --------------
 * • calculatePutSpreadMetrics({ lowerBid, lowerAsk, higherBid, higherAsk,
 *                                spreadWidth, dte, pct = 50 })
 *        → { creditReceived, maxRisk, maxGain, pctGain, annPctGain }
 *
 * • recalcRecord(record, pct)
 *        – returns new record clone with recalculated metrics
 *
 * • recalcAll(records, pct)
 *        – bulk helper: returns new array, filters out non-profitable
 */

(function (root) {
    /** Compute put spread metrics for one spread (per-100-shares numbers). */
    function calculatePutSpreadMetrics({
      lowerBid,
      lowerAsk, 
      higherBid,
      higherAsk,
      spreadWidth,
      dte,
      pct = 50
    }) {
      // Derived option prices between bid-ask using percentage slider
      const lowerPrice = lowerBid + (pct / 100) * (lowerAsk - lowerBid);
      const higherPrice = higherBid + (pct / 100) * (higherAsk - higherBid);

      const creditReceived = (higherPrice - lowerPrice) * 100;  // Net credit received
      const maxRisk = (spreadWidth * 100) - creditReceived;     // Max loss
      const maxGain = creditReceived;                           // Max gain is the credit
      const pctGain = maxRisk > 0 ? (maxGain / maxRisk) * 100 : 0;
      const annPctGain = dte > 0 ? (pctGain * 365) / dte : 0;

      return { creditReceived, maxRisk, maxGain, pctGain, annPctGain };
    }

    /** Return a new record with updated metrics (leave original untouched). */
    function recalcRecord(rec, pct) {
      const metrics = calculatePutSpreadMetrics({
        lowerBid: rec.lowerBid,
        lowerAsk: rec.lowerAsk,
        higherBid: rec.higherBid,
        higherAsk: rec.higherAsk,
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
        .filter(r => r.creditReceived > 0);
    }

    /* expose to global namespace */
    root.PutSpreadCalcUtils = {
      calculatePutSpreadMetrics,
      recalcRecord,
      recalcAll
    };
  })(window);