from flask import Flask, render_template, request, make_response, jsonify
from datetime import datetime
import datetime as dt
import pandas as pd
import os
import yfinance as yf
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import py_vollib.black_scholes.greeks.analytical as pyv
import json
import requests
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

#company_names = json.load(open('./company_names.json', 'r'))
#all_companies = json.load(open('./companies.json', 'r'))

company_names = requests.get('https://files.jcrayb.com/files/config/company_names.json').json()
all_companies = requests.get('https://files.jcrayb.com/files/config/companies.json').json()

#dev_db_folder = '/home/jcrayb/Documents/dev-db'
#dev_db_folder = '/home/chris/Documents/backups'

## DEV DB ##
#connection=sqlite3.connect(os.path.join(dev_db_folder, 'options.db'), check_same_thread=False)

## PROD DB ##
connection=sqlite3.connect('./db/options.db', check_same_thread=False)
c=connection.cursor()


##graph related stuff##

typesDict = {"lastPrice":"Closing Price",
             "volume":"Volume",
             "openInterest":"Open Interest",
             "impliedVolatility":"Implied Volatility"
        }

def getWeekdays(startDate, endDate):
    startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")

    days = 0
    while startDateDt <= endDateDt:
        if not startDateDt.weekday() in [5, 6]:
            days +=  1
        startDateDt += dt.timedelta(days=1)

    return days

def graphOptionImg(ticker, strike, exp, type_, startDate, endDate, graphType):
    print("graph function")
    ticker = ticker.upper()
    ticker = ticker.strip()
    limit = 30
    offset = 0
    modif = ''

    try:
        startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    except:
        startDateDt = ''
    try:
        endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")
    except:
        endDateDt = ''

    todayDt = dt.datetime.now()
    today = todayDt.strftime("%Y-%m-%d")
    if len(endDate) == 0:
        endDate = dt.date.today().strftime('%Y-%m-%d')
        if len(startDate) != 0:
            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'
            limit = getWeekdays(startDate, endDate)

    else:
        if endDate and startDate:
            if endDateDt < startDateDt:
                temp = endDate
                tempDt = endDateDt
                endDate = startDate
                endDateDt = startDateDt
                startDate = temp
                startDateDt = tempDt

            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'

            if endDateDt > todayDt:
                endDate = today

            offset = getWeekdays(endDate, today)-1
            limit = getWeekdays(startDate, endDate)
            if not os.path.exists(f'../../option_data/logs/{today}.txt') and offset > 0:
                offset -= 1



    dispType = typesDict[graphType]

    if type_ == 'call':
        type_ = 'C'
        typeName = 'Calls'
    else:
        type_ = 'P'
        typeName = 'Puts'
    #initialize arrays
    valueArray = []
    dateArray = []
    print("fetching db")
    dataList = c.execute(f'''
        SELECT date, {graphType} FROM options
        WHERE ticker="{ticker}" AND strike="{strike}" AND exp="{exp}" AND type="{type_}"
        ORDER BY date DESC
        LIMIT {limit} OFFSET {offset};
    ''').fetchall()

    if not dataList:
        return '', 'We seem to not have data for your request... Make sure the parameters you have entered are correct, and that the start and end dates are not equal. If you think this is a mistake, please email us at dev@jcrayb.com'
    for data in dataList:
        dateArray += [data[0]]
        valueArray += [data[1]]

    if graphType == 'lastPrice':
        modif = '$'
    print("generating graph")
    #create and configure graph
    graph = pd.DataFrame()
    graph['Date'] = dateArray
    graph[dispType] = valueArray
    graph = graph.set_index('Date')
    plot = px.line(graph,render_mode='svg')
    plot.update_layout(
        title=f"{ticker} {exp} {strike}$ {typeName} {dispType}",
        xaxis_title="Date",
        showlegend = False,
        margin = {'r':0, 'l': 0},
        yaxis_visible=False
    )
    plot.update_traces(
        hovertemplate =
        f'<i>{dispType}</i>:' + modif+'%{y:.2f}'+
        '<br><b>Date:</b>: %{x}<br>'
    )
    #make a unique path for each ticker
    chart = pio.to_json(plot)
    return chart, 'none'



def returnStrikes(ticker, exp):
    data_list = c.execute(f'''
        SELECT strike, type FROM options
        WHERE ticker="{ticker}" AND exp="{exp}"
        ORDER BY date DESC
    ''').fetchall()
    
    strikes = {'P':[], 'C':[]}
    for data in data_list:
        strike = data[0]
        type_ = data[1] 

        if not strike in strikes[type_]:
            strikes[type_] += [strike]
    return strikes

def return_expiration_dates(ticker):
    data_list = c.execute(f'''
        SELECT DISTINCT exp FROM options
        WHERE ticker="{ticker}"
        ORDER BY date DESC
    ''').fetchall()
    return data_list

def getGreeks(date, expiry, stockPrice, r, sigma, strike, optionType):
    flag = optionType.lower()
    dateDt = dt.datetime.strptime(date, "%Y-%m-%d")
    expiryDt = dt.datetime.strptime(expiry, "%Y-%m-%d")

    t = (expiryDt-dateDt).days/365.25

    delta = pyv.delta(flag, stockPrice, strike, t, r, sigma)
    gamma = pyv.gamma(flag, stockPrice, strike, t, r, sigma)
    theta = pyv.theta(flag, stockPrice, strike, t, r, sigma)
    vega = pyv.vega(flag, stockPrice, strike, t, r, sigma)
    rho  = pyv.rho(flag, stockPrice, strike, t, r, sigma)
    return delta, gamma, vega, theta, rho

def verifyInput(args):
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = args['strike_price']
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')

    if not exp_date_dt.weekday() == 4:
        return 'The expiration date you have entered is not a friday. Make sure you have entered a correct date.'

    if yf.Ticker(ticker).history().empty:
        return 'The symbol you have entered is invalid. Make sure you have entered a correct symbol.'

    if not exp_date:
        return 'Please provide an expiry date.'

    if not strike_price:
        return 'Please provide a strike price.'

    if start_date == end_date and start_date and end_date:
        return 'Your start and end dates are identical. Please choose a different range.'

    return ''

def index(type_, args):
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = float(args['strike_price'])
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')
    error = verifyInput(args)

    if error:
        return '', error

    graph, error = graphOptionImg(ticker, strike_price, exp_date, put_or_call, start_date, end_date, type_)
    '''except Exception as e:
        print(e)
        graph = e'''
    return graph, error

def graphGreeks(args):
    args = request.args
    ticker = args['ticker']
    exp_date = args['exp_date']
    start_date = args['start_date']
    end_date = args['end_date']
    strike_price = float(args['strike_price'])
    put_or_call = args['put_or_call']
    exp_date_dt = dt.datetime.strptime(exp_date, '%Y-%m-%d')

    error = verifyInput(args)
    if error:
        return '', error

    startDate = start_date
    endDate = end_date

    ticker = ticker.upper()
    ticker = ticker.strip()
    limit = 30
    offset = 0
    modif = ''

    try:
        startDateDt = dt.datetime.strptime(startDate, "%Y-%m-%d")
    except:
        startDateDt = ''
    try:
        endDateDt = dt.datetime.strptime(endDate, "%Y-%m-%d")
    except:
        endDateDt = ''

    todayDt = dt.datetime.now()
    today = todayDt.strftime("%Y-%m-%d")
    if len(endDate) == 0:
        endDate = dt.date.today().strftime('%Y-%m-%d')
        if len(startDate) != 0:
            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'
            limit = getWeekdays(startDate, endDate)

    else:
        if endDate and startDate:
            if endDateDt < startDateDt:
                temp = endDate
                tempDt = endDateDt
                endDate = startDate
                endDateDt = startDateDt
                startDate = temp
                startDateDt = tempDt

            if startDateDt > todayDt:
                return '', 'Your start date is in the future. Please choose a different start date.'

            if endDateDt > todayDt:
                endDate = today

            offset = getWeekdays(endDate, today)-1
            limit = getWeekdays(startDate, endDate)
            if not os.path.exists(f'../../option_data/logs/{today}.txt') and offset > 0:
                offset -= 1

    if put_or_call == 'call':
        type_ = 'C'
        typeName = 'Calls'
    else:
        type_ = 'P'
        typeName = 'Puts'
    #initialize arrays
    valueArray = []
    dateArray = []

    dataList = c.execute(f'''
        SELECT date, impliedVolatility FROM options
        WHERE ticker="{ticker}" AND strike="{strike_price}" AND exp="{exp_date}" AND type="{type_}"
        ORDER BY date DESC
        LIMIT {limit} OFFSET {offset};
    ''').fetchall()

    if not dataList:
        return '', 'We seem to not have data for your request... Make sure the parameters you have entered are correct, and that the start and end dates are not equal. If you think this is a mistake, please email us at dev@jcrayb.com'

    hist = yf.Ticker(ticker).history(start=startDate)['Close']
    deltaArray = []
    gammaArray = []
    vegaArray = []
    thetaArray = []
    rhoArray = []
    dateArray = []
    for data in dataList:
        date = data[0]
        try:
            r = yf.Ticker('^IRX').history(start=startDate)['Close'][date]/100
            stockPrice = hist[date]
            dateArray += [date]
        except:
            continue
        sigma = data[1]
        delta, gamma, vega, theta, rho = getGreeks(date, exp_date, stockPrice, r, sigma, strike_price, type_)
        deltaArray += [delta]
        gammaArray += [gamma]
        vegaArray += [vega]
        thetaArray += [theta]
        rhoArray += [rho]

    graph = pd.DataFrame()
    graph['Date'] = dateArray
    graph['Delta'] = deltaArray
    graph['Gamma'] = gammaArray
    graph['Vega'] = vegaArray
    graph['Theta'] = thetaArray
    graph['Rho'] = rhoArray
    graph = graph.set_index('Date')
    plot = px.line(graph,render_mode='svg')
    plot.update_layout(
        title=f"{ticker} {exp_date} {strike_price}$ {typeName} greeks",
        xaxis_title="Date",
        showlegend = True,
        margin = {'r':0, 'l': 0},
        yaxis_visible=False
    )
    chart = pio.to_json(plot)
    return chart, 'none'

## GRAPH ROUTES ##
@app.route('/graph/single/', defaults={'type_':''}, methods=['GET'])
@app.route('/graph/single/<type_>', methods=['GET', 'POST'])
def singlePrice(type_):
    print("received request")
    if not type_:
        return render_template('single/graph.html')
    args = request.args
    graph, error = index(type_, args)
    return {'message': graph , 'error':error}

@app.route('/graph/single/greeks', methods=['GET'])
def singleGreeks():
    args = request.args
    graph, error = graphGreeks(args)
    return {'message':graph, 'error':error}
##GRAPH ROUTES ##
##Graph related stuff##

@app.route('/get/options/strikes/<ticker>', methods=['GET'])
def route_get_options_strikes(ticker) -> dict:
    try:
        expiry = request.args['expiry'] #str
    except KeyError:
        error = 'Please provide an expiry date.' 
        return {'content': '', 'response':'ERROR', 'error':error}
    
    strikes = returnStrikes(ticker, expiry) #dict
    
    response = cors_response({'content': strikes, 'response':'OK', 'error':''})
    return response

@app.route('/get/options/expiries/<ticker>', methods=['GET'])
def route_get_options_expiries(ticker) -> dict:
    if not ticker:
        error = 'Please provide a symbol.' 
        return {'content': '', 'response':'ERROR', 'error':error}

    data_list = return_expiration_dates(ticker) #list
    expiries = [] #list
    for data in data_list:
        exp = data[0]
        if dt.datetime.strptime(exp, '%Y-%m-%d')+dt.timedelta(days=1)>=dt.datetime.today():
            expiries += [exp]
    expiries.sort(key=lambda t: datetime.strptime(t, '%Y-%m-%d'))
    response = {'content': expiries, 'response':'OK', 'error':''}
    return response

@app.route('/search-tickers', defaults={'search': ''}, methods=['GET', 'POST'])
@app.route('/search-tickers/<search>', methods=['GET', 'POST'])
def search_tickers(search):
    if not search:
        return {'message':['']}
    try:
        limit = int(request.args['limit'])
    except:
        limit = 5 
    try:
        names = bool(request.args['names'])
    except KeyError:
        names = False

    result = [company for company in all_companies if company.startswith(search.upper())]
    result.sort()
    result = result[:min(limit, len(result))]
    if names:
        try:
            names = [company_names[company] if company in company_names else '' for company in result]
            return {'message':result, 'names':names}
        except Exception as e:
            print(e)
            return {'message':result}
    #names = [yf.Ticker(r).info['shortName'] for r in result]
    return {'message':result}

@app.route('/get/names', methods=['GET'])
def get_names():
    companies = request.json['companies']
    print(companies)
    names = [company_names[company] if company in company_names else '' for company in companies ]
    return {'names':names}

@app.route('/get/name/<company>', methods=['GET'])
def get_company_name(company):
    company = company.upper()
    if not company in company_names:
        return {'status':'ERR', 'content': 'Ticker not in our list'}, 404
    return {'status':'OK', 'content': company_names[company]}

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return {'status':'healthy'}

def cors_response(data):
    response = make_response(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def last_n_days(n: int) -> list:
    logs =  os.listdir(f'./db/logs')
    #logs =  os.listdir(f'./logs')
    logs.sort(reverse=True)
    
    last_days = [log.split('.')[0] for log in logs]
    return last_days[:n]

@app.route('/get/options/highest-volume/', defaults={'ticker':''}, methods=['GET'])
@app.route('/get/options/highest-volume/<ticker>', methods=['GET'])
def route_get_options_highest_volume(ticker) -> dict:
    if not ticker:
        error = 'Please provide a symbol.' 
        return {'content': '', 'response':'ERROR', 'error':error}
    if not 'n_days' in request.args:
        n_days = 5
    else:
        n_days = int(request.args['n_days'])

    ticker = ticker.upper()

    days = last_n_days(n_days)

    cond_str = f'(date = "{days[0]}"'
    for day in days[1:]:
        cond_str += f' OR date = "{day}"'
    cond_str += ")"

    data = c.execute(f'''
        SELECT SUM(volume) AS total, exp, strike, type FROM options 
        WHERE ticker="{ticker}" AND {cond_str} 
        GROUP BY exp, strike, type
        ORDER BY total DESC
        LIMIT 10;
    ''').fetchall()

    response = cors_response({'content': data, 'response':'OK', 'error':''})
    return response

@app.route('/get/options/total-volume/', defaults={'ticker':''}, methods=['GET'])
@app.route('/get/options/total-volume/<ticker>', methods=['GET'])
def route_get_options_total_volume(ticker) -> dict:
    if not ticker:
        error = 'Please provide a symbol.' 
        return {'content': '', 'response':'ERROR', 'error':error}
    if not 'n_days' in request.args:
        n_days = 5
    else:
        n_days = int(request.args['n_days'])

    ticker = ticker.upper()

    days = last_n_days(n_days)

    cond_str = f'(date = "{days[0]}"'
    for day in days[1:]:
        cond_str += f' OR date = "{day}"'
    cond_str += ")"

    data = c.execute(f'''
        SELECT SUM(volume) AS total, type FROM options 
        WHERE ticker="{ticker}" AND {cond_str} 
        GROUP BY type
        ORDER BY total DESC
        LIMIT 10;
    ''').fetchall()

    response = {'content': data, 'response':'OK', 'error':''}
    return response

@app.route('/get/options/atm_strangle/<ticker>')
def atm_strangle(ticker):
    expiries = route_get_options_expiries(ticker)['content']
    current_stock_price = yf.Ticker(ticker).history().iloc[-1].Close

    last_day = last_n_days(1)[0]

    cond_str = f'(exp = "{expiries[0]}"'
    for day in expiries[1:]:
        cond_str += f' OR exp = "{day}"'
    cond_str += ")"

   # print(cond_str)

    atm_vol = c.execute(f'''
    SELECT strike, exp, lastPrice, type FROM options
    WHERE ticker="{ticker}" AND {cond_str} AND date="{last_day}"
    ORDER BY ABS(strike-{current_stock_price}), exp
    ''').fetchall()

    exps = []
    values = []
    strangle_prices = {}

    for val in atm_vol:
        if not val[1]+val[3] in exps:
            exps += [val[1]+val[3]] 
            
            if not val[1] in strangle_prices:
                strangle_prices[val[1]] = val[2]
            else:
                strangle_prices[val[1]] += val[2]

    return {'content':strangle_prices}

@app.route('/country_graph')
def country_graph():
    country_df = pd.read_csv('country_data.csv')

    fig = px.choropleth(country_df, locations=country_df['index'],
                    color="lived",
                    range_color = (0, 1),
                    color_continuous_scale=['white', 'red'],
                    width= 1000,
                    height=600,
                    hover_name='name',
                    hover_data={'lived':False, 'name':False, 'index':False}
                   )

    fig.update_layout(showlegend=False, coloraxis_showscale=False, margin={'r':0, 't':0, 'l':0, 'b':0})
    return {'content':fig.to_json()}

@app.route('/f1_globe')
def f1_globe():
    df = pd.read_csv('calendar.csv')

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat = df.lat,
        lon = df.lon,
        text= df.fancy_name,
        mode = 'lines',
        line = dict(width = 1, color = '#000000')
    ))

    fig.update_layout(
        showlegend = False,
        geo = dict(
            showland = True,
            showcountries = True,
            showocean = True,
            countrywidth = 0.5,
            landcolor = '#55802e',
            lakecolor = '#276488',
            oceancolor = '#276488',
            projection = dict(
                type = 'orthographic',
                rotation = dict(
                    lon = 0,
                    lat = 40,
                    roll = 0
                )
            ),
            lonaxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            ),
            lataxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            )
        ),
        margin=dict(l=20, r=20, t=20, b=20)
    )   

    return {'content':fig.to_json()}

@app.route('/f1_map')
def f1_map():
    df = pd.read_csv('calendar.csv')

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat = df.lat,
        lon = df.lon,
        text= df.fancy_name,
        mode = 'lines',
        line = dict(width = 1, color = '#000000')
    ))

    fig.update_layout(
        showlegend = False,
        geo = dict(
            showland = True,
            showcountries = True,
            showocean = True,
            countrywidth = 0.5,
            landcolor = '#55802e',
            lakecolor = '#276488',
            oceancolor = '#276488',
            projection = dict(
                type = 'natural earth',
                rotation = dict(
                    lon = 0,
                    lat = 40,
                    roll = 0
                )
            ),
            lonaxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            ),
            lataxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            )
        ),
        margin=dict(l=20, r=20, t=20, b=20)
    )   

    return {'content':fig.to_json()}

@app.route('/f1_min_globe')
def f1_min_globe():
    df = pd.read_csv('calendar_min.csv')

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat = df.lat,
        lon = df.lon,
        text= df.fancy_name,
        mode = 'lines',
        line = dict(width = 1, color = '#000000')
    ))

    fig.update_layout(
        showlegend = False,
        geo = dict(
            showland = True,
            showcountries = True,
            showocean = True,
            countrywidth = 0.5,
            landcolor = '#55802e',
            lakecolor = '#276488',
            oceancolor = '#276488',
            projection = dict(
                type = 'orthographic',
                rotation = dict(
                    lon = 0,
                    lat = 40,
                    roll = 0
                )
            ),
            lonaxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            ),
            lataxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            )
        ),
        margin=dict(l=20, r=20, t=20, b=20)
    )   

    return {'content':fig.to_json()}

@app.route('/f1_min_map')
def f1_min_map():
    df = pd.read_csv('calendar_min.csv')

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat = df.lat,
        lon = df.lon,
        text= df.fancy_name,
        mode = 'lines',
        line = dict(width = 1, color = '#000000')
    ))

    fig.update_layout(
        showlegend = False,
        geo = dict(
            showland = True,
            showcountries = True,
            showocean = True,
            countrywidth = 0.5,
            landcolor = '#55802e',
            lakecolor = '#276488',
            oceancolor = '#276488',
            projection = dict(
                type = 'natural earth',
                rotation = dict(
                    lon = 0,
                    lat = 40,
                    roll = 0
                )
            ),
            lonaxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            ),
            lataxis = dict(
                showgrid = True,
                gridcolor = 'rgb(102, 102, 102)',
                gridwidth = 0.5
            )
        ),
        margin=dict(l=20, r=20, t=20, b=20)
    )   

    return {'content':fig.to_json()}


if __name__ == '__main__':
    #app.run(host="0.0.0.0", port="8080", debug=True)
    app.run(host="0.0.0.0", port="8080")
