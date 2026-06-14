# Options API — Route Reference

Base URL: `https://options-api.jcrayb.com`

All endpoints return JSON. Errors are returned in the `error` field.

---

## Options Graph

### `GET /graph/single/<type>`

Returns a Plotly JSON chart of a single option contract's historical data.

**URL parameters**

| Parameter | Values |
|-----------|--------|
| `type` | `lastPrice`, `volume`, `openInterest`, `impliedVolatility` |

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ticker` | string | yes | Ticker symbol (e.g. `AAPL`) |
| `exp_date` | string | yes | Expiration date (`YYYY-MM-DD`). Must be a Friday, or a Thursday when Friday is a NYSE holiday. |
| `strike_price` | float | yes | Strike price (e.g. `200.0`) |
| `put_or_call` | string | yes | `call` or `put` |
| `start_date` | string | no | Range start (`YYYY-MM-DD`). Empty string = most recent 30 trading days. |
| `end_date` | string | no | Range end (`YYYY-MM-DD`). Empty string = today. |

**Response**

```json
{
  "message": "<Plotly JSON string>",
  "error": ""
}
```

`error` is an empty string on success. On failure it contains a human-readable message and `message` is empty.

---

### `GET /graph/single/greeks`

Returns a Plotly JSON chart showing all five Black-Scholes greeks (delta, gamma, vega, theta, rho) over time for a single option contract.

**Query parameters** — same as `/graph/single/<type>` above.

The risk-free rate is fetched from the 13-week T-bill yield (`^IRX`) via yfinance. The underlying stock price is also fetched from yfinance to compute the greeks on each date.

**Response**

```json
{
  "message": "<Plotly JSON string>",
  "error": ""
}
```

---

## Options Data

### `GET /get/options/expiries/<ticker>`

Returns all future expiration dates in the database for the given ticker, sorted ascending.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `ticker` | Ticker symbol (e.g. `AAPL`) |

**Response**

```json
{
  "content": ["2026-06-18", "2026-12-18", "2027-01-15"],
  "response": "OK",
  "error": ""
}
```

Only dates that have not yet expired (strictly after today) are returned.

---

### `GET /get/options/strikes/<ticker>`

Returns all available strike prices in the database for a given ticker and expiration date, split by option type.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `ticker` | Ticker symbol |

**Query parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `expiry` | string | yes | Expiration date (`YYYY-MM-DD`) |

**Response**

```json
{
  "content": {
    "C": [150.0, 155.0, 160.0],
    "P": [150.0, 155.0, 160.0]
  },
  "response": "OK",
  "error": ""
}
```

`C` = calls, `P` = puts. Strikes are deduplicated and returned in the order they appear in the database.

---

### `GET /get/options/highest-volume/<ticker>`

Returns the top 10 option contracts by total volume over the last N trading days.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `ticker` | Ticker symbol |

**Query parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `n_days` | int | no | `5` | Number of recent trading days to sum over |

**Response**

```json
{
  "content": [
    [12500, "2026-06-18", 200.0, "C"],
    ...
  ],
  "response": "OK",
  "error": ""
}
```

Each element in `content` is `[total_volume, expiry, strike, type]`.

---

### `GET /get/options/total-volume/<ticker>`

Returns the total call volume vs put volume over the last N trading days.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `ticker` | Ticker symbol |

**Query parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `n_days` | int | no | `5` | Number of recent trading days to sum over |

**Response**

```json
{
  "content": [
    [45000, "C"],
    [32000, "P"]
  ],
  "response": "OK",
  "error": ""
}
```

Each element is `[total_volume, type]`, ordered highest volume first.

---

### `GET /get/options/atm_strangle/<ticker>`

For each upcoming expiration date, returns the combined last price of the nearest at-the-money call and put (i.e. the ATM strangle price). Uses the most recent data day in the database.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `ticker` | Ticker symbol |

**Response**

```json
{
  "content": {
    "2026-06-18": 18.45,
    "2026-12-18": 34.10
  }
}
```

Keys are expiration dates. Values are the summed last prices of the ATM call and ATM put for that expiry.

---

## Ticker Search

### `GET /search-tickers/<search>`
### `POST /search-tickers/<search>`

Searches for ticker symbols that start with the given string.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `search` | Search prefix (e.g. `APP` matches `AAPL`, `APPN`, etc.) |

**Query parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | no | `5` | Maximum number of results to return |
| `names` | bool | no | `false` | If present, also return full company names |

**Response without names**

```json
{
  "message": ["AAPL", "APPN"]
}
```

**Response with `names=true`**

```json
{
  "message": ["AAPL", "APPN"],
  "names": ["Apple Inc.", "Appian Corporation"]
}
```

---

### `GET /get/name/<company>`

Returns the full company name for a single ticker.

**URL parameters**

| Parameter | Description |
|-----------|-------------|
| `company` | Ticker symbol (case-insensitive) |

**Response**

```json
{ "status": "OK", "content": "Apple Inc." }
```

Returns HTTP 404 with `status: "ERR"` if the ticker is not in the name list.

---

### `GET /get/names`

Returns company names for a list of tickers. Accepts a JSON body.

**Request body**

```json
{ "companies": ["AAPL", "MSFT"] }
```

**Response**

```json
{ "names": ["Apple Inc.", "Microsoft Corporation"] }
```

Unknown tickers produce an empty string at the corresponding index.

---

## Misc / Visualizations

### `GET /healthcheck`

Returns `{ "status": "healthy" }`. Used for uptime monitoring.

---

### `GET /country_graph`

Returns a Plotly choropleth map (Plotly JSON) showing countries visited, colored red/white by a `lived` flag. Reads from `country_data.csv`.

**Response**

```json
{ "content": "<Plotly JSON string>" }
```

---

### `GET /f1_globe`

Returns a Plotly orthographic globe (Plotly JSON) tracing the F1 race calendar circuit path. Reads from `calendar.csv`.

**Response**

```json
{ "content": "<Plotly JSON string>" }
```

---

### `GET /f1_map`

Same as `/f1_globe` but uses a natural earth flat map projection instead of a globe.

---

### `GET /f1_min_globe`

Same as `/f1_globe` but reads from `calendar_min.csv` (a minimal/reduced calendar dataset).

---

### `GET /f1_min_map`

Same as `/f1_map` but reads from `calendar_min.csv`.
