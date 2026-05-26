# sla_api.py
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
from sla_monitor import get_sla_monitor, SLALevel
from database import Database

app = FastAPI()
sla_monitor = get_sla_monitor()
db = Database()

@app.get("/api/sla/metrics")
async def get_sla_metrics():
    """Get all SLA metrics and their current status"""
    report = sla_monitor.get_sla_report()
    return report

@app.get("/api/sla/metrics/{metric_name}")
async def get_sla_metric_detail(metric_name: str, hours: int = Query(24, ge=1, le=168)):
    """Get detailed SLA report for specific metric"""
    report = sla_monitor.get_sla_report(metric_name, hours)
    if not report["current_status"]:
        raise HTTPException(status_code=404, detail=f"Metric {metric_name} not found")
    return report

@app.post("/api/sla/metrics")
async def register_sla_metric(
    name: str,
    level: str,
    threshold_seconds: int,
    warning_threshold: int
):
    """Register new SLA metric"""
    try:
        level_enum = SLALevel(level.lower())
        sla_monitor.register_metric(name, level_enum, threshold_seconds, warning_threshold)
        return {"message": f"Metric {name} registered successfully", "status": "success"}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid SLA level: {level}")

@app.get("/api/sla/dashboard")
async def get_sla_dashboard(days: int = Query(7, ge=1, le=30)):
    """Get SLA dashboard data for visualization"""
    query = """
        SELECT 
            metric_name,
            date,
            sla_compliance_rate,
            avg_duration,
            p95_duration,
            breach_count,
            warning_count
        FROM sla_daily_summary
        WHERE date >= CURRENT_DATE - $1::interval
        ORDER BY date DESC, metric_name
    """
    
    cursor = db.execute_query(query, (f"{days} days",))
    results = cursor.fetchall()
    
    dashboard_data = {
        "period_days": days,
        "generated_at": datetime.now().isoformat(),
        "compliance_trend": [],
        "top_breaches": [],
        "metrics_summary": {}
    }
    
    for row in results:
        metric_name, date, compliance, avg_duration, p95, breaches, warnings = row
        
        if metric_name not in dashboard_data["metrics_summary"]:
            dashboard_data["metrics_summary"][metric_name] = {
                "avg_compliance": 0,
                "total_breaches": 0,
                "avg_duration": 0
            }
        
        dashboard_data["compliance_trend"].append({
            "date": date.isoformat(),
            "metric": metric_name,
            "compliance": float(compliance) if compliance else 0
        })
        
        # Track breaches
        if breaches > 0:
            dashboard_data["top_breaches"].append({
                "metric": metric_name,
                "date": date.isoformat(),
                "breaches": breaches,
                "compliance": float(compliance) if compliance else 0
            })
    
    # Sort top breaches
    dashboard_data["top_breaches"] = sorted(
        dashboard_data["top_breaches"], 
        key=lambda x: x["breaches"], 
        reverse=True
    )[:10]
    
    return dashboard_data

@app.get("/api/sla/alert-history")
async def get_sla_alert_history(
    hours: int = Query(24, ge=1, le=168),
    status: Optional[str] = Query(None, regex="^(timeout|warning)$")
):
    """Get SLA alert history"""
    query = """
        SELECT metric_name, level, duration, status, threshold, event_time
        FROM sla_events
        WHERE event_time >= NOW() - $1::interval
        AND ($2::text IS NULL OR status = $2)
        ORDER BY event_time DESC
    """
    
    cursor = db.execute_query(query, (f"{hours} hours", status))
    results = cursor.fetchall()
    
    alerts = []
    for row in results:
        alerts.append({
            "metric_name": row[0],
            "level": row[1],
            "duration": round(row[2], 2),
            "status": row[3],
            "threshold": row[4],
            "event_time": row[5].isoformat()
        })
    
    return {
        "total": len(alerts),
        "period_hours": hours,
        "alerts": alerts
    }