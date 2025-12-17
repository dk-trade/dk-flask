/* calculator_iron_condor.js
 *
 * Pure-function helpers for iron-condor-strategy math.
 * No Schwab API calls – those are done server-side. The helpers are
 * used on the client so the user can tweak option price sliders
 * without another round-trip.
 *
 * An Iron Condor combines:
 * - Put Credit Spread (sell higher put, buy lower put)
 * - Call Credit Spread (sell lower call, buy higher call)
 * Both spreads must have the same width.
 *
 * Public surface
 * --------------
 * • calculateIronCondorMetrics({ putLowerBid, putLowerAsk, putHigherBid, putHigherAsk,
 *                                 callLowerBid, callLowerAsk, callHigherBid, callHigherAsk,
 *                                 spreadWidth, dte, pct = 50 })
 *        → { putCredit, callCredit, totalCredit, maxRisk, pctGain, annPctGain }
 *
 * • recalcRecord(record, pct)
 *        – returns new record clone with recalculated metrics
 *
 * • recalcAll(records, pct)
 *        – bulk helper: returns new array, filters out non-profitable
 */

(function (root) {
    /** Compute iron condor metrics for one position (per-100-shares numbers). */
    function calculateIronCondorMetrics({
      putLowerBid,
      putLowerAsk,
      putHigherBid,
      putHigherAsk,
      callLowerBid,
      callLowerAsk,
      callHigherBid,
      callHigherAsk,
      spreadWidth,
      dte,
      pct = 50
    }) {
      // Derived option prices between bid-ask using percentage slider
      // For puts: buy lower (pay ask side), sell higher (receive bid side)
      // For calls: sell lower (receive bid side), buy higher (pay ask side)

      // PUT side - credit spread
      // Buy lower put (we pay) - use higher price when conservative (pct < 50)
      const putLowerPrice = putLowerBid + ((100 - pct) / 100) * (putLowerAsk - putLowerBid);
      // Sell higher put (we receive) - use lower price when conservative (pct < 50)
      const putHigherPrice = putHigherBid + (pct / 100) * (putHigherAsk - putHigherBid);

      // CALL side - credit spread
      // Sell lower call (we receive) - use lower price when conservative (pct < 50)
      const callLowerPrice = callLowerBid + (pct / 100) * (callLowerAsk - callLowerBid);
      // Buy higher call (we pay) - use higher price when conservative (pct < 50)
      const callHigherPrice = callHigherBid + ((100 - pct) / 100) * (callHigherAsk - callHigherBid);

      // Put credit = sell higher - buy lower
      const putCredit = (putHigherPrice - putLowerPrice) * 100;
      // Call credit = sell lower - buy higher
      const callCredit = (callLowerPrice - callHigherPrice) * 100;

      const totalCredit = putCredit + callCredit;
      const maxRisk = (spreadWidth * 100) - totalCredit;
      const pctGain = maxRisk > 0 ? (totalCredit / maxRisk) * 100 : 0;
      const annPctGain = dte > 0 ? (pctGain * 365) / dte : 0;

      return { putCredit, callCredit, totalCredit, maxRisk, pctGain, annPctGain };
    }

    /** Return a new record with updated metrics (leave original untouched). */
    function recalcRecord(rec, pct) {
      const metrics = calculateIronCondorMetrics({
        putLowerBid: rec.putLowerBid,
        putLowerAsk: rec.putLowerAsk,
        putHigherBid: rec.putHigherBid,
        putHigherAsk: rec.putHigherAsk,
        callLowerBid: rec.callLowerBid,
        callLowerAsk: rec.callLowerAsk,
        callHigherBid: rec.callHigherBid,
        callHigherAsk: rec.callHigherAsk,
        spreadWidth: rec.spreadWidth,
        dte: rec.dte,
        pct
      });
      return { ...rec, ...metrics };
    }

    /** Bulk helper → returns new array, filters out condors with ≤0 profit. */
    function recalcAll(records, pct) {
      return records
        .map(r => recalcRecord(r, pct))
        .filter(r => r.totalCredit > 0);
    }

    /* expose to global namespace */
    root.IronCondorCalcUtils = {
      calculateIronCondorMetrics,
      recalcRecord,
      recalcAll
    };
  })(window);
