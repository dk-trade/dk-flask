/* calculator_put_call_spread.js
 *
 * Put-Call Spread strategy calculator functions.
 * Handles calculations for both call spreads and put spreads.
 */

(() => {
    /* --------------------------------------------------------------
     * Call Spread Calculations
     * -------------------------------------------------------------- */
    
    function calculateCallSpread(record, buyCallPct = 50, sellCallPct = 50) {
        // Lower strike (BUY CALL) - we pay this price
        const lowerPrice = record.lowerBid + (buyCallPct / 100) * (record.lowerAsk - record.lowerBid);
        // Upper strike (SELL CALL) - we receive this price  
        const upperPrice = record.upperBid + (sellCallPct / 100) * (record.upperAsk - record.upperBid);
        
        const paid = (lowerPrice - upperPrice) * 100;  // Net debit paid
        const maxGain = (record.spreadWidth * 100) - paid;  // Max profit
        const pctGain = paid > 0 ? (maxGain / paid) * 100 : 0;
        const annPctGain = record.dte > 0 ? (pctGain * 365) / record.dte : 0;
        
        return {
            ...record,
            paid,
            maxGain,
            pctGain,
            annPctGain,
            lowerPrice,
            upperPrice
        };
    }

    /* --------------------------------------------------------------
     * Put Spread Calculations
     * -------------------------------------------------------------- */
    
    function calculatePutSpread(record, buyPutPct = 50, sellPutPct = 50) {
        // Lower strike (BUY PUT) - we pay this price
        const lowerPrice = record.lowerBid + (buyPutPct / 100) * (record.lowerAsk - record.lowerBid);
        // Higher strike (SELL PUT) - we receive this price
        const higherPrice = record.higherBid + (sellPutPct / 100) * (record.higherAsk - record.higherBid);
        
        const creditReceived = (higherPrice - lowerPrice) * 100;  // Net credit received
        const maxRisk = (record.spreadWidth * 100) - creditReceived;  // Max loss
        const maxGain = creditReceived;  // For put credit spreads, max gain is the credit
        const pctGain = maxRisk > 0 ? (maxGain / maxRisk) * 100 : 0;
        const annPctGain = record.dte > 0 ? (pctGain * 365) / record.dte : 0;
        
        return {
            ...record,
            creditReceived,
            maxRisk,
            maxGain,
            pctGain,
            annPctGain,
            lowerPrice,
            higherPrice
        };
    }

    /* --------------------------------------------------------------
     * Combined Calculator
     * -------------------------------------------------------------- */
    
    function calculatePutCallSpread(record, pricingPct = 50) {
        if (record.strategyType === "call_spread") {
            // For call spreads: more conservative = buy higher %, sell lower %
            const buyCallPct = 100 - pricingPct;
            const sellCallPct = pricingPct;
            return calculateCallSpread(record, buyCallPct, sellCallPct);
        } else if (record.strategyType === "put_spread") {
            // For put spreads: use same pricing logic
            const buyPutPct = 100 - pricingPct;
            const sellPutPct = pricingPct;
            return calculatePutSpread(record, buyPutPct, sellPutPct);
        }
        return record;
    }

    /* --------------------------------------------------------------
     * Profit/Loss Calculations
     * -------------------------------------------------------------- */
    
    function calculateProfitLoss(record, underlyingPriceAtExpiry) {
        if (record.strategyType === "call_spread") {
            return calculateCallSpreadPL(record, underlyingPriceAtExpiry);
        } else if (record.strategyType === "put_spread") {
            return calculatePutSpreadPL(record, underlyingPriceAtExpiry);
        }
        return 0;
    }
    
    function calculateCallSpreadPL(record, underlyingPrice) {
        const lowerStrike = record.lowerStrike;
        const upperStrike = record.upperStrike;
        const paid = record.paid || 0;
        
        if (underlyingPrice <= lowerStrike) {
            // Both options expire worthless
            return -paid;
        } else if (underlyingPrice >= upperStrike) {
            // Maximum profit scenario
            return record.maxGain || 0;
        } else {
            // Between strikes - partial profit
            return ((underlyingPrice - lowerStrike) * 100) - paid;
        }
    }
    
    function calculatePutSpreadPL(record, underlyingPrice) {
        const lowerStrike = record.lowerStrike;
        const higherStrike = record.higherStrike;
        const creditReceived = record.creditReceived || 0;
        
        if (underlyingPrice >= higherStrike) {
            // Both options expire worthless - keep full credit
            return creditReceived;
        } else if (underlyingPrice <= lowerStrike) {
            // Maximum loss scenario
            return -(record.maxRisk || 0);
        } else {
            // Between strikes - partial loss
            return creditReceived - ((higherStrike - underlyingPrice) * 100);
        }
    }

    /* --------------------------------------------------------------
     * Breakeven Calculations
     * -------------------------------------------------------------- */
    
    function calculateBreakeven(record) {
        if (record.strategyType === "call_spread") {
            return record.lowerStrike + (record.paid / 100);
        } else if (record.strategyType === "put_spread") {
            return record.higherStrike - (record.creditReceived / 100);
        }
        return 0;
    }

    /* --------------------------------------------------------------
     * Risk/Reward Metrics
     * -------------------------------------------------------------- */
    
    function calculateRiskRewardRatio(record) {
        if (record.strategyType === "call_spread") {
            const maxRisk = record.paid || 0;
            const maxGain = record.maxGain || 0;
            return maxRisk > 0 ? maxGain / maxRisk : 0;
        } else if (record.strategyType === "put_spread") {
            const maxRisk = record.maxRisk || 0;
            const maxGain = record.maxGain || 0;
            return maxRisk > 0 ? maxGain / maxRisk : 0;
        }
        return 0;
    }
    
    function calculateWinProbability(record) {
        // Simple approximation based on how far strikes are from current price
        const currentPrice = record.price;
        const breakeven = calculateBreakeven(record);
        const priceDiff = Math.abs(currentPrice - breakeven) / currentPrice;
        
        // This is a rough approximation - in reality you'd use option pricing models
        return Math.max(0.1, Math.min(0.9, 0.5 + (priceDiff * 2)));
    }

    /* --------------------------------------------------------------
     * Export to global scope
     * -------------------------------------------------------------- */
    
    window.PutCallSpreadCalculator = {
        calculateCallSpread,
        calculatePutSpread,
        calculatePutCallSpread,
        calculateProfitLoss,
        calculateBreakeven,
        calculateRiskRewardRatio,
        calculateWinProbability
    };

})();