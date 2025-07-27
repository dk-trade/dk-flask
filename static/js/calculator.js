// calculator.js – minimal client‑side helper for metric recalculation only.
// No Schwab API calls. Credentials remain on server.

export function calculateMetrics({ price, strike, bid, ask, dte, percentage = 50 }) {
    const callPrice = bid + (percentage / 100) * (ask - bid);
    const cost = (price - callPrice) * 100;
    const maxProfit = strike * 100 - cost;
    const pctCall = (maxProfit / cost) * 100;
    const annPctCall = (pctCall * 365) / dte;
  
    return {
      cost,
      maxProfit,
      pctCall,
      annPctCall,
    };
  }
  