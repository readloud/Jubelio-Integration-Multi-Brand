// SLADashboard.jsx
import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Badge, Spinner, Alert } from 'react-bootstrap';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

function SLADashboard() {
    const [metrics, setMetrics] = useState(null);
    const [dashboard, setDashboard] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000); // Refresh every minute
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        try {
            const [metricsRes, dashboardRes, alertsRes] = await Promise.all([
                fetch('/api/sla/metrics'),
                fetch('/api/sla/dashboard?days=7'),
                fetch('/api/sla/alert-history?hours=24')
            ]);

            const metricsData = await metricsRes.json();
            const dashboardData = await dashboardRes.json();
            const alertsData = await alertsRes.json();

            setMetrics(metricsData);
            setDashboard(dashboardData);
            setAlerts(alertsData.alerts);
        } catch (error) {
            console.error('Error fetching SLA data:', error);
        } finally {
            setLoading(false);
        }
    };

    const getStatusBadge = (status) => {
        const variants = {
            healthy: 'success',
            warning: 'warning',
            timeout: 'danger',
            critical: 'danger',
            failed: 'danger'
        };
        return <Badge bg={variants[status] || 'secondary'}>{status}</Badge>;
    };

    const getLevelBadge = (level) => {
        const variants = {
            critical: 'danger',
            high: 'warning',
            medium: 'info',
            low: 'secondary'
        };
        return <Badge bg={variants[level]}>{level}</Badge>;
    };

    if (loading) {
        return <Spinner animation="border" className="d-block mx-auto mt-5" />;
    }

    return (
        <div>
            <h2 className="mb-4">SLA Monitoring Dashboard</h2>

            {/* Current Metrics */}
            <Card className="mb-4">
                <Card.Header>
                    <h5>Current SLA Status</h5>
                </Card.Header>
                <Card.Body>
                    <Table striped bordered hover responsive>
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Level</th>
                                <th>Status</th>
                                <th>Last Duration</th>
                                <th>Threshold</th>
                                <th>Warning</th>
                                <th>Last Check</th>
                            </tr>
                        </thead>
                        <tbody>
                            {metrics?.current_status && Object.entries(metrics.current_status).map(([name, metric]) => (
                                <tr key={name}>
                                    <td>{name}</td>
                                    <td>{getLevelBadge(metric.level)}</td>
                                    <td>{getStatusBadge(metric.status)}</td>
                                    <td className={metric.last_duration > metric.warning_threshold ? 'text-danger' : ''}>
                                        {metric.last_duration}s
                                    </td>
                                    <td>{metric.threshold}s</td>
                                    <td>{metric.warning_threshold}s</td>
                                    <td>{new Date(metric.last_check).toLocaleTimeString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            {/* Compliance Trend */}
            <Row className="mb-4">
                <Col md={8}>
                    <Card>
                        <Card.Header>
                            <h5>SLA Compliance Trend (7 Days)</h5>
                        </Card.Header>
                        <Card.Body>
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={dashboard?.compliance_trend || []}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="date" />
                                    <YAxis domain={[0, 100]} />
                                    <Tooltip />
                                    <Legend />
                                    {[...new Set(dashboard?.compliance_trend?.map(d => d.metric) || [])].map(metric => (
                                        <Line
                                            key={metric}
                                            type="monotone"
                                            dataKey="compliance"
                                            data={dashboard.compliance_trend.filter(d => d.metric === metric)}
                                            name={metric}
                                            stroke={`#${Math.floor(Math.random() * 16777215).toString(16)}`}
                                        />
                                    ))}
                                </LineChart>
                            </ResponsiveContainer>
                        </Card.Body>
                    </Card>
                </Col>

                <Col md={4}>
                    <Card>
                        <Card.Header>
                            <h5>Top Breaches (7 Days)</h5>
                        </Card.Header>
                        <Card.Body>
                            {dashboard?.top_breaches?.length > 0 ? (
                                dashboard.top_breaches.map((breach, idx) => (
                                    <Alert key={idx} variant="danger" className="mb-2">
                                        <strong>{breach.metric}</strong><br />
                                        {breach.breaches} breaches on {breach.date}<br />
                                        Compliance: {breach.compliance.toFixed(1)}%
                                    </Alert>
                                ))
                            ) : (
                                <Alert variant="success">No SLA breaches in the last 7 days! 🎉</Alert>
                            )}
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* Recent Alerts */}
            <Card>
                <Card.Header>
                    <h5>Recent SLA Alerts (24 Hours)</h5>
                </Card.Header>
                <Card.Body>
                    {alerts.length === 0 ? (
                        <Alert variant="success">No alerts in the last 24 hours</Alert>
                    ) : (
                        <Table responsive>
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Metric</th>
                                    <th>Level</th>
                                    <th>Status</th>
                                    <th>Duration</th>
                                    <th>Threshold</th>
                                </tr>
                            </thead>
                            <tbody>
                                {alerts.slice(0, 20).map((alert, idx) => (
                                    <tr key={idx}>
                                        <td>{new Date(alert.event_time).toLocaleString()}</td>
                                        <td>{alert.metric_name}</td>
                                        <td>{getLevelBadge(alert.level)}</td>
                                        <td>{getStatusBadge(alert.status)}</td>
                                        <td>{alert.duration}s</td>
                                        <td>{alert.threshold}s</td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>
            </Card>
        </div>
    );
}

export default SLADashboard;