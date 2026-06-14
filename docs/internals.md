# Options API — Internal Functions

These functions are not exposed as HTTP endpoints. They are helpers called by the route handlers.

---

## Holiday / expiry validation

### `_easter(year) -> dt.date`

Computes the date of Easter Sunday for the given year using the Anonymous Gregorian algorithm.

```
year: int  →  dt.date
```

Used by `_nyse_friday_holidays` to derive Good Friday.

---

### `_nyse_friday_holidays(year) -> set[dt.date]`

Returns the set of dates in the given year on which the NYSE is closed **and** that date falls on a Friday. This covers:

- **New Year's Day** (Jan 1) — included if it is a Friday, or if Jan 1 is a Saturday (observed the preceding Friday, Dec 31)
- **Juneteenth** (Jun 19) — included if it is a Friday, or if Jun 19 is a Saturday (observed Jun 18)
- **Independence Day** (Jul 4) — included if it is a Friday, or if Jul 4 is a Saturday (observed Jul 3)
- **Christmas Day** (Dec 25) — included if it is a Friday, or if Dec 25 is a Saturday (observed Dec 24)
- **Good Friday** — always a Friday; date computed via `_easter`

Monday-observed holidays (MLK Day, Presidents Day, Memorial Day, Labor Day) and Thanksgiving are not included because they never fall on a Friday.

---

### `_is_valid_expiry(d) -> bool`

Returns `True` if `d` is a valid options expiration day.

```
d: dt.datetime  →  bool
```

Options normally expire on **Fridays**. When a standard expiry Friday is a NYSE holiday, the exchange moves expiration to **Thursday**. This function accepts both cases:

- `d.weekday() == 4` (Friday) → always valid
- `d.weekday() == 3` (Thursday) → valid only if `d + 1 day` is in `_nyse_friday_holidays`

Any other weekday returns `False`.

---

## Date range helpers

### `getWeekdays(startDate, endDate) -> int`

Counts the number of weekdays (Monday–Friday) between two date strings, inclusive on both ends.

```
startDate: str  "YYYY-MM-DD"
endDate:   str  "YYYY-MM-DD"
→ int
```

Used to compute the `LIMIT` and `OFFSET` for database queries when a date range is specified, since the options table only contains trading-day rows.

---

## Graph builders

### `graphOptionImg(ticker, strike, exp, type_, startDate, endDate, graphType) -> tuple[str, str]`

Queries the options database for a single contract's historical data and returns a Plotly line chart as a JSON string.

```
ticker:    str    Ticker symbol (uppercased internally)
strike:    float  Strike price
exp:       str    Expiration date "YYYY-MM-DD"
type_:     str    "call" or "put"
startDate: str    Range start "YYYY-MM-DD", or "" for no start bound
endDate:   str    Range end "YYYY-MM-DD", or "" for most recent 30 days
graphType: str    Column to plot: "lastPrice" | "volume" | "openInterest" | "impliedVolatility"

→ (chart_json: str, error: str)
    chart_json is the Plotly JSON string on success, "" on error.
    error is "none" on success, or a human-readable message on failure.
```

**Date range logic**

- If both `startDate` and `endDate` are empty, returns the 30 most recent rows.
- If only `startDate` is given, returns all rows from `startDate` to today.
- If both are given, the query window is `[startDate, endDate]`. The `OFFSET` is calculated as the number of weekdays from `endDate` to today minus 1, so that rows outside the requested window (i.e. more recent than `endDate`) are skipped via `ORDER BY date DESC`.
- If `startDate` > `endDate`, the two are swapped automatically.
- If `endDate` is in the future, it is clamped to today.

---

### `graphGreeks(args) -> tuple[str, str]`

Computes and plots all five Black-Scholes greeks over time for a single option contract.

```
args: flask.Request.args  (reads ticker, exp_date, strike_price, put_or_call,
                           start_date, end_date from query parameters)

→ (chart_json: str, error: str)
```

Steps:

1. Runs `verifyInput` — returns early with an error string if invalid.
2. Applies the same date-range / LIMIT / OFFSET logic as `graphOptionImg`.
3. Fetches implied volatility for each day from the options database.
4. Fetches the underlying stock's closing price from yfinance.
5. Fetches the 13-week T-bill rate (`^IRX`) from yfinance as the risk-free rate `r`.
6. Calls `getGreeks` for each date to compute delta, gamma, vega, theta, rho.
7. Returns a Plotly multi-line chart with one trace per greek.

---

### `getGreeks(date, expiry, stockPrice, r, sigma, strike, optionType) -> tuple`

Computes the five Black-Scholes greeks for a single option on a single date using `py_vollib`.

```
date:       str    Current date "YYYY-MM-DD"
expiry:     str    Expiration date "YYYY-MM-DD"
stockPrice: float  Underlying price on `date`
r:          float  Risk-free rate (decimal, e.g. 0.05)
sigma:      float  Implied volatility (decimal)
strike:     float  Strike price
optionType: str    "C" or "P"

→ (delta, gamma, vega, theta, rho)  all floats
```

Time to expiry `t` is computed as `(expiry - date).days / 365.25`.

---

## Input validation

### `verifyInput(args) -> str`

Validates the query parameters for a graph request. Returns an empty string on success, or a human-readable error message on failure.

```
args: flask.Request.args  (ImmutableMultiDict)
→ str   "" on success, error message on failure
```

Checks performed (in order):

1. Expiration date is a valid expiry day via `_is_valid_expiry` (Friday or holiday-adjusted Thursday).
2. Ticker is valid — `yf.Ticker(ticker).history()` must not be empty.
3. `exp_date` is non-empty.
4. `strike_price` is non-empty.
5. `start_date` and `end_date` are not identical non-empty strings.

---

### `index(type_, args) -> tuple[str, str]`

Thin wrapper around `verifyInput` + `graphOptionImg`. Parses and casts the raw query-parameter strings before passing them to `graphOptionImg`.

```
type_: str              Graph type (lastPrice | volume | openInterest | impliedVolatility)
args:  ImmutableMultiDict

→ (chart_json: str, error: str)
```

---

## Database helpers

### `returnStrikes(ticker, exp) -> dict`

Returns all unique strike prices stored in the database for a given ticker and expiration, grouped by option type.

```
ticker: str
exp:    str  "YYYY-MM-DD"

→ {"C": [float, ...], "P": [float, ...]}
```

Strikes are deduplicated in the order they appear when the table is sorted by date descending.

---

### `return_expiration_dates(ticker) -> list[tuple]`

Returns all distinct expiration dates in the database for the given ticker, ordered by date descending.

```
ticker: str

→ [(exp_str,), ...]   list of 1-tuples
```

The caller (`route_get_options_expiries`) filters this list to only future dates.

---

### `last_n_days(n) -> list[str]`

Returns the `n` most recent dates for which data was collected, determined by reading filenames from `./db/logs/`.

```
n: int

→ [str, ...]  dates "YYYY-MM-DD", most recent first
```

Each log file is named `YYYY-MM-DD.txt`. Used to build the `WHERE date IN (...)` condition for volume queries.

---

## HTTP utilities

### `cors_response(data) -> flask.Response`

Wraps a JSON-serialisable dict in a Flask `Response` and adds the `Access-Control-Allow-Origin: *` header.

```
data: dict  →  flask.Response
```

Used by routes that need explicit CORS headers beyond what Flask-CORS provides globally.
