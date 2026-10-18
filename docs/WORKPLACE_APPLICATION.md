# Applying the analysis to your own purchasing operation

## Questions this project teaches you to ask

Start with the meaning of the timestamps. Does PO creation occur when a buyer drafts it, when approval finishes, or when the supplier receives it? Is a goods receipt recorded when materials physically arrive, when inspection approves them, or when someone posts the ERP transaction? These differences change what a measured interval means.

Use supplier comparisons as investigation priorities. A long interval can reflect an early planned order, agreed manufacturing lead time, internal release delays, transportation, quality holds or posting lag. Its length alone does not assign responsibility.

## A practical review sequence

1. **Look at distributions, not just averages.** Compare median and P90 by the same material family and order type. Inspect a sample of long-tail transactions.
2. **Show the denominator.** Pair every time statistic with the number of eligible orders and the share that has an observed receipt. A supplier with many missing outcomes can otherwise look artificially fast.
3. **Separate first receipt from completion.** Check quantities and posting IDs before treating repeated receipts as partial deliveries or the last posting as full completion.
4. **Review order changes in context.** Inspect when a change happened and who requested it. A price correction after arrival cannot explain an earlier delivery interval.
5. **Distinguish purchasing flow from payment flow.** A long invoice-to-clearing interval may reflect agreed payment terms. Ask whether a payment was actually overdue before treating it as a bottleneck.
6. **Understand cancellations.** Separate deleted, closed, reversed, reactivated and genuinely open lines. Preserve the original population when comparing rates.

## Additional ERP fields needed for stronger questions

| Question | Minimum additional fields | Why they matter |
|---|---|---|
| Did a supplier deliver late? | Original requested date, supplier-confirmed date, actual physical arrival date, agreed delivery terms, changes to each promised date | Distinguishes late delivery from an intentionally long lead time or revised agreement |
| Was the full order delivered? | PO line quantity/UOM, unique receipt posting ID, receipt quantity, reversal-to-original link, returns | Allows partial receipts and reversals to be netted without double counting |
| What caused the elapsed time? | Release/approval timestamp, supplier acknowledgement, dispatch, carrier milestones, arrival, inspection and ERP posting times | Separates internal preparation, supplier production, transit and recording delay |
| Which materials risk stockouts? | Material/SKU ID, location, usable stock, reservations, demand/production requirements, expected inbound quantities/dates, quality holds | Supports time-phased supply-versus-demand checks |
| How much safety stock is appropriate? | Consumption history, replenishment lead times, shortage history, target service level, forecast error, lot-size constraints | Connects variability to an explicit service and cost tradeoff |
| What is the financial impact? | Original unmasked unit costs, currency, expedited freight, shortage consequences, contribution margins and carrying-cost assumptions | Prevents confusing anonymized source values or calendar days with actual savings |

## Example management questions after reviewing the dashboard

- Are long-tail materials naturally made to order, or do they suffer avoidable release or receiving delays?
- Does the same supplier vary across comparable SKUs, sites and ordering policies?
- How many apparent unreceived items were deleted or superseded?
- Are receipts promptly posted, or does administrative lag distort supplier comparisons?
- Do long invoice intervals align with contracted terms?
- What would need to be measured before setting a realistic supplier target?

The next analytical step is a validated, time-phased material availability table—not a stockout score inferred solely from purchasing event durations.
