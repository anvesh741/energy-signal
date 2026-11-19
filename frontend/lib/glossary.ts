/** Short definitions shown when you hover or tab onto a dotted term. Plain words, one or two sentences. */
export const GLOSSARY: Record<string, string> = {
  US48: "The 48 connected U.S. states, which share one power grid system. Alaska and Hawaii run their own.",
  MWh: "Megawatt-hour. Enough electricity to run roughly 1,000 homes for an hour.",
  TWh: "Terawatt-hour, a million MWh. The U.S. uses around 11 TWh on a typical day.",
  WTI: "West Texas Intermediate, the main U.S. crude oil price, set at Cushing, Oklahoma.",
  Brent: "The main international crude oil price, based on North Sea oil.",
  "Henry Hub": "The main U.S. natural gas price, named after a pipeline hub in Louisiana.",
  MMBtu: "Million British thermal units, the standard unit for natural gas. A typical home uses about 60–80 a year.",
  Bcf: "Billion cubic feet of natural gas. The U.S. uses roughly 90 Bcf on an average day.",
  "day-ahead forecast":
    "The grid operators' own prediction of tomorrow's demand, made so they can line up enough power plants.",
  "partial day":
    "A day that isn't finished yet, or is missing hours. We leave it out of totals so it doesn't look like a drop.",
  MASE: "Mean absolute scaled error. Below 1 means the model beat a simple 'same as last week' guess.",
  "80% band":
    "The range we expect the real value to land in 8 times out of 10, based on how wrong the model has been before.",
  backtest:
    "Replaying the past: forecast from an old date, compare with what actually happened, repeat hundreds of times.",
  percentile: "Where a value ranks. 95th percentile means bigger than 95% of the moves in the comparison window.",
};
