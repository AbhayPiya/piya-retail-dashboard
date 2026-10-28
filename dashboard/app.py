"""Piya Retail analytical dashboard. Run with Streamlit from the project root."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
from decimal import Decimal
import pandas as pd
import plotly.express as px
from html import escape
import streamlit as st
import os
# Load Community Cloud secrets before the data module resolves its DSN.
if not os.getenv('DASHBOARD_DSN'):
    try:
        hosted_dsn = st.secrets.get('DASHBOARD_DSN')
    except FileNotFoundError:
        hosted_dsn = None
    if hosted_dsn:
        os.environ['DASHBOARD_DSN'] = hosted_dsn
from dashboard.data import metadata, load

st.set_page_config(page_title='Piya Retail | Analytics',page_icon='◈',layout='wide')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html,body,[class*="css"],.stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:#f3f5f9;color:#18243b;}
.block-container {padding-top:3rem;max-width:1600px;padding-bottom:3rem;}
header[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {background:#101d34;border-right:1px solid #20314b;}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#dbe5f3!important;}
[data-testid="stSidebar"] [data-testid="stForm"] {border-color:#34415a;background:#16253d;}
[data-testid="stSidebar"] button p {color:#263951!important;}
[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] p {color:white!important;}
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stPlotlyChart"]) {background:white;}
[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {background:#17a398;color:white;border:0;}
h1 {font-size:2.3rem!important;font-weight:700!important;letter-spacing:-.05em;}
h2,h3 {letter-spacing:-.025em;font-weight:600!important;}
[data-testid="stMetric"] {background:white;border:1px solid #e6eaf0;border-top:3px solid #14a394;
 border-radius:12px;padding:20px 18px;box-shadow:0 3px 10px #17243b04;}
[data-testid="stMetricLabel"] {color:#64748b;font-size:.8rem;}
[data-testid="stMetricValue"] {font-size:1.8rem;font-weight:600;letter-spacing:-.04em;}
[data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:14px;}
.eyebrow {color:#718099;font-size:11px;font-weight:700;letter-spacing:.16em;margin-bottom:8px;}
.report-meta {color:#748198;font-size:12px;margin-bottom:24px;}
.insight-band {background:#e8f5f1;border:1px solid #cee8df;border-radius:12px;padding:15px 20px;
 color:#24564f;font-size:13px;margin:18px 0 24px;line-height:1.7;}
.sidebar-brand {color:white;font-size:25px;font-weight:700;letter-spacing:-1px;padding:10px 0 3px;}
.sidebar-sub {color:#8fa3bf;font-size:11px;letter-spacing:.13em;margin-bottom:28px;}
</style>''',unsafe_allow_html=True)
st.markdown('<div class="eyebrow">RETAIL INTELLIGENCE / EXECUTIVE WORKSPACE</div>',unsafe_allow_html=True)
st.title('Commerce overview')

PALETTE=['#139c8d','#5976c6','#f2b45d','#9aaac4','#cf7686','#73bab0','#7c72ac','#d4dce8']
def polish(fig,height=320):
    fig.update_layout(template='plotly_white',height=height,paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',font=dict(family='DM Sans, sans-serif',size=11,color='#738199'),
        margin=dict(l=0,r=10,t=15,b=5),hovermode='x unified',
        legend=dict(orientation='h',y=-.2,x=0),hoverlabel=dict(bgcolor='#102038',font_color='white'))
    fig.update_xaxes(showgrid=False,zeroline=False,title=None)
    fig.update_yaxes(gridcolor='#edf0f5',zeroline=False,title=None)
    return fig

@st.cache_data(ttl=30,show_spinner=False)
def get_metadata(scope,include):
    return metadata(scope,include)

@st.cache_data(ttl=30,show_spinner=False)
def get_data(scope,include,start,end,statuses):
    return load(scope,include,start,end,statuses)

with st.sidebar:
    st.markdown('<div class="sidebar-brand">◈ Piya Retail</div><div class="sidebar-sub">ANALYTICS STUDIO</div>',unsafe_allow_html=True)
    st.subheader('Report filters')
    scope=st.selectbox('Dataset',['All order activity','Streaming demo'])
    include=st.checkbox('Include simulated orders',value=scope=='Streaming demo',disabled=scope=='Streaming demo')
    if scope=='Streaming demo':
        include=True
    if st.button('Refresh data',width='stretch'):
        st.cache_data.clear()
    st.caption('Auto-refresh · 60 seconds. Query cache · 30 seconds.')

try:
    meta=get_metadata(scope,include)
except Exception:
    st.error('Unable to read analytical tables. Start PostgreSQL and run streaming analytics with --force to publish the dashboard Gold models.')
    st.stop()
if meta['first_date'] is None:
    st.info('No published orders match this dataset. Enable simulated orders or wait for Gold publication.')
    st.stop()
with st.sidebar:
    date_key='dates_'+scope+str(include)
    applied_key='applied_'+date_key
    if applied_key not in st.session_state:
        previous=st.session_state.get(date_key,(meta['first_date'],meta['last_date']))
        st.session_state[applied_key]=tuple(previous) if len(previous)==2 else (meta['first_date'],meta['last_date'])
    start_key='start_'+date_key
    end_key='end_'+date_key
    if start_key not in st.session_state:
        st.session_state[start_key]=st.session_state[applied_key][0]
    if end_key not in st.session_state:
        st.session_state[end_key]=st.session_state[applied_key][1]
    with st.form('purchase_dates_'+scope+str(include),clear_on_submit=False):
        start_date=st.date_input('Start date',min_value=date(2000,1,1),max_value=date(2100,12,31),key=start_key)
        end_date=st.date_input('End date',min_value=date(2000,1,1),max_value=date(2100,12,31),key=end_key)
        apply_dates=st.form_submit_button('Apply dates',width='stretch')
    if apply_dates:
        if start_date<=end_date:
            st.session_state[applied_key]=(start_date,end_date)
        else:
            st.warning('End date must be on or after the start date. The previous range is still shown.')
    dates=st.session_state[applied_key]
    statuses=st.multiselect('Order status',meta['statuses'],default=meta['statuses'],key='statuses_'+scope+str(include))
    frequency=st.selectbox('Trend interval',['Daily','Weekly','Monthly'],index=2)
    metric=st.selectbox('Chart measure',['Delivered merchandise sales','All-order merchandise value'],
                        index=1 if scope=='Streaming demo' else 0)
    top_n=st.slider('Top products / categories',5,30,10)
if len(dates)!=2:
    st.info('Select both the start and end date.')
    st.stop()
if not statuses:
    st.info('Choose at least one order status.')
    st.stop()
@st.fragment(run_every='60s')
def render_dashboard():
    try:
        report=get_data(scope,include,dates[0],dates[1],tuple(sorted(statuses)))
    except Exception:
        st.error('Dashboard queries or SQL reconciliation failed. Refresh after checking Gold and PostgreSQL connectivity.')
        st.stop()
    totals=report['totals']
    selected='delivered_sales' if metric=='Delivered merchandise sales' else 'booked_merchandise'
    money=lambda value:f'${value:,.2f}'
    compact=lambda value:f'${value/1000000:,.2f}M' if value>=1000000 else (f'${value/1000:,.1f}K' if value>=10000 else money(value))
    st.caption(f"{dates[0]:%d %b %Y} — {dates[1]:%d %b %Y}  ·  {scope}  ·  {len(statuses)} statuses selected")
    a,b,c,d=st.columns(4)
    a.metric('Sales',compact(totals['delivered_sales']),help=money(totals['delivered_sales'])+' · Delivered merchandise, excluding freight')
    b.metric('Orders',f"{totals['orders']:,}")
    c.metric('Bookings',compact(totals['booked_merchandise']),help=money(totals['booked_merchandise'])+' · All selected statuses')
    d.metric('Delivered AOV',money(totals['delivered_sales']/totals['delivered_orders']) if totals['delivered_orders'] else '—')
    if scope=='Streaming demo':
        st.info('Streaming traffic is simulated. Approved demo orders contribute to bookings; delivered sales remain zero until an actual delivered status exists.')
    else:
        st.caption('Historical amounts use the project’s fixed BRL → USD reference conversion, not purchase-date exchange rates. Simulated payments are included only when selected.')
    if not totals['orders']:
        st.info('No orders match the selected dates and statuses.')
    else:
        daily=pd.DataFrame(report['daily']).set_index('order_date')
        daily.index=pd.to_datetime(daily.index)
        daily=daily.reindex(pd.date_range(dates[0],dates[1]),fill_value=0)
        for column in daily:
            daily[column]=pd.to_numeric(daily[column])
        rule={'Daily':'D','Weekly':'W-MON','Monthly':'MS'}[frequency]
        trends=daily.resample(rule,label='left',closed='left').sum().reset_index(names='Purchase period')
        delivered_share=totals['delivered_orders']/totals['orders']*100
        products=pd.DataFrame(report['products'])
        for field in ['booked_merchandise','delivered_sales','units']:
            products[field]=pd.to_numeric(products[field])
        leading=products.groupby('category')[selected].sum().sort_values(ascending=False)
        leader=str(leading.index[0]).replace('_',' ').title() if len(leading) and leading.iloc[0]>0 else 'No sales in this selection'
        st.markdown(f'<div class="insight-band"><b>At a glance</b> &nbsp; · &nbsp; {delivered_share:.1f}% of selected orders delivered'
                    f' &nbsp; · &nbsp; {int(totals["units"]):,} units ordered'
                    f' &nbsp; · &nbsp; Leading category: <b>{escape(leader)}</b></div>',unsafe_allow_html=True)
        left,right=st.columns([1.6,1])
        with left,st.container(border=True):
            st.subheader('Sales trajectory')
            st.caption(metric+' · '+frequency.lower()+' purchase cohorts')
            fig=px.area(trends,x='Purchase period',y=selected,color_discrete_sequence=[PALETTE[0]],
                        labels={selected:metric+' (USD)'})
            polish(fig).update_yaxes(tickprefix='$')
            fig.update_traces(line=dict(width=2),fillcolor='rgba(19,156,141,.12)')
            st.plotly_chart(fig,width='stretch',config={'displayModeBar':False})
        with right,st.container(border=True):
            st.subheader('Orders')
            st.caption('Distinct orders · identical date and status filters')
            fig=px.bar(trends,x='Purchase period',y='orders',color_discrete_sequence=[PALETTE[1]],labels={'orders':'Orders'})
            st.plotly_chart(polish(fig),width='stretch',config={'displayModeBar':False})
        left,right=st.columns([1.6,1])
        with left,st.container(border=True):
            st.subheader('What drives sales')
            group=st.radio('Performance breakdown',['Category','Product ID'],horizontal=True,label_visibility='collapsed')
            key='category' if group=='Category' else 'product_id'
            grouped=products.groupby(key,as_index=False)[[selected,'units']].sum().nlargest(top_n,selected).sort_values(selected)
            if key=='category':
                grouped[key]=grouped[key].str.replace('_',' ').str.title()
            fig=px.bar(grouped,x=selected,y=key,orientation='h',color_discrete_sequence=[PALETTE[0]],hover_data=['units'],
                       labels={selected:metric+' (USD)',key:group})
            polish(fig,360).update_xaxes(tickprefix='$')
            st.plotly_chart(fig,width='stretch',config={'displayModeBar':False})
            st.caption('Top '+str(top_n)+' shown. Reconciliation includes every filtered product.')
        with right,st.container(border=True):
            st.subheader('Order health')
            st.caption('Status distribution · order count')
            status=pd.DataFrame(report['status'])
            fig=px.pie(status,values='orders',names='order_status',hole=.73,color_discrete_sequence=PALETTE)
            polish(fig,360)
            fig.update_layout(hovermode='closest',annotations=[dict(text=f'<b>{totals["orders"]:,}</b><br>orders',
                x=.5,y=.5,font_size=20,showarrow=False,font_color='#18243b')])
            fig.update_traces(textinfo='none',hovertemplate='%{label}<br>%{value:,} orders · %{percent}<extra></extra>')
            st.plotly_chart(fig,width='stretch',config={'displayModeBar':False})
        with st.expander('Product detail and export'):
            st.dataframe(products.sort_values(selected,ascending=False),hide_index=True,width='stretch')
            st.download_button('Download filtered product CSV',products.to_csv(index=False),'retailpulse_products.csv','text/csv')
    with st.expander('Metric definitions',expanded=False):
        st.markdown('''
    - **Delivered merchandise sales:** item prices for delivered orders, excluding freight. Assigned to the purchase date; this is an analytical revenue proxy, not recognized accounting revenue.
    - **All-order merchandise:** item prices across all selected statuses, including canceled/unavailable orders. This is booking activity.
    - **Orders:** distinct order IDs after transactional/stream deduplication. One order contributes once.
    - **Delivered merchandise AOV:** delivered merchandise sales ÷ delivered order count; blank when no delivered orders exist.
    - **Product units:** one order-item row represents one unit. Product order counts cannot be summed into total orders.
    - **Filters:** dates are inclusive and apply to every KPI, status, trend, and product chart. Weekly buckets start Monday; monthly buckets start on day one.
    - **Dataset:** all-order activity combines operational USD snapshots and stream-only events. The transactional snapshot wins on overlap. Streaming demo selects orders with a published stream event. Original BRL batch results are not mixed into USD totals.
    ''')
    with st.expander('SQL validation and freshness'):
        st.success('All 8 dashboard-to-SQL reconciliation checks passed for the current filters.')
        st.dataframe(pd.DataFrame(report['checks']),hide_index=True,width='stretch')
        st.caption(f"Gold published: {report['published_at']} · Queried: {report['fetched_at']}")
        st.code('SELECT * FROM stream_gold.fct_unified_orders;\nSELECT * FROM stream_gold.fct_unified_order_items;',language='sql')

render_dashboard()
