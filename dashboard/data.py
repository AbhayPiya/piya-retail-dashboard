"""Read-only analytical queries. Money remains Decimal until chart rendering."""
from datetime import date
from decimal import Decimal
import os
import psycopg
from psycopg.rows import dict_row

DSN=os.getenv('DASHBOARD_DSN',os.getenv('STREAMING_ANALYTICS_DSN',
              'postgresql://localhost:5433/retailpulse_analytics'))


def where(scope,include_simulated,start=None,end=None,statuses=None):
    parts=["currency='USD'"]
    args=[]
    if scope=='Streaming demo':
        parts.append('has_stream_event')
    if not include_simulated:
        parts.append("payment_type<>'simulated'")
    if start is not None:
        parts.append('order_date BETWEEN %s AND %s')
        args.extend((start,end))
    if statuses is not None:
        parts.append('order_status=ANY(%s)')
        args.append(list(statuses))
    return ' AND '.join(parts),args


def connect():
    db=psycopg.connect(DSN,row_factory=dict_row,connect_timeout=5)
    db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    db.execute("SET LOCAL statement_timeout='20s'")
    return db


def metadata(scope,include_simulated):
    clause,args=where(scope,include_simulated)
    with connect() as db:
        result=db.execute('''SELECT min(order_date) AS first_date,max(order_date) AS last_date,
            array_agg(DISTINCT order_status ORDER BY order_status) AS statuses
            FROM stream_gold.fct_unified_orders WHERE '''+clause,args).fetchone()
    return result


def load(scope,include_simulated,start,end,statuses):
    clause,args=where(scope,include_simulated,start,end,statuses)
    prefix='WITH filtered AS (SELECT * FROM stream_gold.fct_unified_orders WHERE '+clause+') '
    with connect() as db:
        totals=db.execute(prefix+'''SELECT count(*) AS orders,
            count(*) FILTER(WHERE order_status='delivered') AS delivered_orders,
            coalesce(sum(merchandise_value) FILTER(WHERE order_status='delivered'),0) AS delivered_sales,
            coalesce(sum(merchandise_value),0) AS booked_merchandise,
            coalesce(sum(freight_value),0) AS freight,
            coalesce(sum(payment_value),0) AS payments,
            coalesce(sum(item_count),0) AS units
            FROM filtered''',args).fetchone()
        daily=db.execute(prefix+'''SELECT order_date,count(*) AS orders,
            coalesce(sum(merchandise_value),0) AS booked_merchandise,
            coalesce(sum(merchandise_value) FILTER(WHERE order_status='delivered'),0) AS delivered_sales
            FROM filtered GROUP BY order_date ORDER BY order_date''',args).fetchall()
        status=db.execute(prefix+'''SELECT order_status,count(*) AS orders,
            sum(merchandise_value) AS booked_merchandise
            FROM filtered GROUP BY order_status ORDER BY orders DESC''',args).fetchall()
        products=db.execute(prefix+'''SELECT i.product_id,i.category,count(*) AS units,
            count(DISTINCT i.order_id) AS orders,sum(i.price) AS booked_merchandise,
            coalesce(sum(i.price) FILTER(WHERE o.order_status='delivered'),0) AS delivered_sales
            FROM stream_gold.fct_unified_order_items i JOIN filtered o USING(order_id)
            GROUP BY i.product_id,i.category''',args).fetchall()
        # Independently aggregate the published order fact for SQL comparison.
        reference=db.execute('''SELECT count(DISTINCT order_id) AS orders,
            coalesce(sum(merchandise_value) FILTER(WHERE order_status='delivered'),0) AS delivered_sales,
            coalesce(sum(merchandise_value),0) AS booked_merchandise,
            coalesce(sum(item_count),0) AS units
            FROM stream_gold.fct_unified_orders WHERE '''+clause,args).fetchone()
        publication=db.execute("SELECT finished_at FROM stream_silver.pipeline_runs WHERE status='success' ORDER BY finished_at DESC LIMIT 1").fetchone()
        fetched_at=db.execute('SELECT now() AS at').fetchone()['at']
    checks=[]
    def check(label,actual,expected):
        checks.append(dict(metric=label,dashboard=str(actual),sql=str(expected),passed=actual==expected))
    check('Daily orders',sum(r['orders'] for r in daily),reference['orders'])
    check('Status orders',sum(r['orders'] for r in status),reference['orders'])
    check('Daily delivered merchandise',sum((r['delivered_sales'] for r in daily),Decimal(0)),reference['delivered_sales'])
    check('Daily booked merchandise',sum((r['booked_merchandise'] for r in daily),Decimal(0)),reference['booked_merchandise'])
    check('Product booked merchandise',sum((r['booked_merchandise'] for r in products),Decimal(0)),reference['booked_merchandise'])
    check('Product delivered merchandise',sum((r['delivered_sales'] for r in products),Decimal(0)),reference['delivered_sales'])
    check('Product units',sum(r['units'] for r in products),reference['units'])
    check('Unique order count',totals['orders'],reference['orders'])
    if not all(r['passed'] for r in checks):
        raise ValueError('Dashboard totals do not reconcile with SQL; refresh after checking Gold publication')
    return dict(totals=totals,daily=daily,status=status,products=products,checks=checks,
                fetched_at=fetched_at,published_at=publication['finished_at'] if publication else None)
