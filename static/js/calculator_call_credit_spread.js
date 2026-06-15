/* calculator_call_credit_spread.js
 *
 * Pure-function helpers for OTM call-credit-spread-strategy math.
 * No Schwab API calls – those are done server-side. The helpers are
 * used on the client so the user can tweak option price sliders
 * without another round-trip.
 *
 * This is a CALL credit spread (above current price):
 * - SELL lower strike call (closer to ATM, more expensive)
 * - BUY higher strike call (further OTM, cheaper)
 * - Credit = lowerMid - higherMid
 *
 * Public surface
 * --------------
 * - calculateCallCreditSpreadMetrics({ lowerBid, lowerAsk, higherBid, higherAsk,
 *                                      spreadWidth, dte, pct = 50 })
 *        -> { creditReceived, maxRisk, maxGain, pctGain, annPctGain }
 *
 * - recalcRecord(record, pct)
 *        - returns new record clone with recalculated metrics
 *
 * - recalcAll(records, pct)
 *        - bulk helper: returns new array, filters out non-profitable
 */

(function (root) {
    /** Compute call credit spread metrics for one spread (per-100-shares numbers). */
    function calculateCallCreditSpreadMetrics({
      lowerBid,
      lowerAsk,
      higherBid,
      higherAsk,
      spreadWidth,
      dte,
      pct = 50
    }) {
      // Derived option prices between bid-ask using percentage slider
      // For call credit spread: we SELL lower strike, BUY higher strike
      const lowerPrice = lowerBid + (pct / 100) * (lowerAsk - lowerBid);
      const higherPrice = higherBid + (pct / 100) * (higherAsk - higherBid);

      // Credit = what we receive (lower) - what we pay (higher)
      const creditReceived = (lowerPrice - higherPrice) * 100;  // Net credit received
      const maxRisk = (spreadWidth * 100) - creditReceived;     // Max loss
      const maxGain = creditReceived;                           // Max gain is the credit
      const pctGain = maxRisk > 0 ? (maxGain / maxRisk) * 100 : 0;
      const annPctGain = dte > 0 ? (pctGain * 365) / dte : 0;

      return { creditReceived, maxRisk, maxGain, pctGain, annPctGain };
    }

    /** Return a new record with updated metrics (leave original untouched). */
    function recalcRecord(rec, pct) {
      const metrics = calculateCallCreditSpreadMetrics({
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

    /** Bulk helper -> returns new array, filters out spreads with <=0 profit. */
    function recalcAll(records, pct) {
      return records
        .map(r => recalcRecord(r, pct))
        .filter(r => r.creditReceived > 0);
    }

    /* expose to global namespace */
    root.CallCreditSpreadCalcUtils = {
      calculateCallCreditSpreadMetrics,
      recalcRecord,
      recalcAll
    };
  })(window);
