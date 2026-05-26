// App.js
import React, { useState, useEffect } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell 
} from 'recharts';
import { 
  Container, Navbar, Nav, Card, Row, Col, Table, 
  Button, Spinner, Alert, Form, Badge 
} from 'react-bootstrap';

const API_URL = 'http://localhost:8000/api';

function App() {
  return (
    <Router>
      <Navbar bg="dark" variant="dark" expand="lg">
        <Container>
          <Navbar.Brand as={Link} to="/">Jubelio Integration Dashboard</Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="me-auto">
              <Nav.Link as={Link} to="/">Dashboard</Nav.Link>
              <Nav.Link as={Link} to="/sync">Sync Status</Nav.Link>
              <Nav.Link as={Link} to="/export">Export Data</Nav.Link>
              <Nav.Link as={Link} to="/alerts">Alerts</Nav.Link>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <Container className="mt-4">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sync" element={<SyncStatus />} />
          <Route path="/export" element={<ExportData />} />
          <Route path="/alerts" element={<Alerts />} />
        </Routes>
      </Container>
    </Router>
  );
}

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, revenueRes] = await Promise.all([
        fetch(`${API_URL}/stats/summary`),
        fetch(`${API_URL}/stats/revenue?days=30`)
      ]);
      
      const statsData = await statsRes.json();
      const revenueData = await revenueRes.json();
      
      setStats(statsData);
      setRevenue(revenueData);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spinner animation="border" className="d-block mx-auto mt-5" />;
  }

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

  return (
    <>
      <h1 className="mb-4">Dashboard Overview</h1>
      
      <Row className="mb-4">
        {stats?.orders.map((brand, idx) => (
          <Col md={4} key={idx} className="mb-3">
            <Card>
              <Card.Body>
                <Card.Title>{brand.brand_id}</Card.Title>
                <Card.Text>
                  <h3>{brand.total_orders.toLocaleString()}</h3>
                  <small>Total Orders (30 days)</small>
                  <h4 className="text-success mt-2">
                    Rp {brand.revenue.toLocaleString()}
                  </h4>
                  <small>Revenue</small>
                  <Badge bg="info" className="mt-2 d-inline-block">
                    {brand.channels} Channels
                  </Badge>
                </Card.Text>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Row>
        <Col md={8}>
          <Card className="mb-4">
            <Card.Body>
              <Card.Title>Revenue Trend (30 Days)</Card.Title>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={revenue?.data || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="revenue" stroke="#8884d8" name="Revenue" />
                  <Line type="monotone" dataKey="orders" stroke="#82ca9d" name="Orders" />
                </LineChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={4}>
          <Card>
            <Card.Body>
              <Card.Title>Sync Success Rate</Card.Title>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={stats?.sync_success_rate || []}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.brand_id}: ${entry.rate}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="rate"
                  >
                    {(stats?.sync_success_rate || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
}

function SyncStatus() {
  const [logs, setLogs] = useState([]);
  const [brandFilter, setBrandFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, [brandFilter]);

  const fetchLogs = async () => {
    setLoading(true);
    const url = brandFilter 
      ? `${API_URL}/sync/status?brand_id=${brandFilter}&limit=50`
      : `${API_URL}/sync/status?limit=50`;
    
    const response = await fetch(url);
    const data = await response.json();
    setLogs(data.logs || []);
    setLoading(false);
  };

  const triggerSync = async (brandId) => {
    await fetch(`${API_URL}/sync/trigger/${brandId}`, { method: 'POST' });
    alert(`Sync triggered for ${brandId}`);
    setTimeout(fetchLogs, 2000);
  };

  if (loading) return <Spinner animation="border" />;

  return (
    <>
      <h1 className="mb-4">Sync Status</h1>
      
      <Form.Group className="mb-3">
        <Form.Label>Filter by Brand</Form.Label>
        <Form.Select value={brandFilter} onChange={(e) => setBrandFilter(e.target.value)}>
          <option value="">All Brands</option>
          <option value="brand_a">Brand A</option>
          <option value="brand_b">Brand B</option>
          <option value="brand_c">Brand C</option>
        </Form.Select>
      </Form.Group>

      <Button variant="primary" onClick={() => fetchLogs()} className="mb-3">
        Refresh
      </Button>

      <Table striped bordered hover responsive>
        <thead>
          <tr>
            <th>Brand</th>
            <th>Data Type</th>
            <th>Status</th>
            <th>Records</th>
            <th>Started At</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, idx) => (
            <tr key={idx}>
              <td>{log.brand_id}</td>
              <td>{log.data_type}</td>
              <td>
                <Badge bg={log.status === 'success' ? 'success' : 'danger'}>
                  {log.status}
                </Badge>
              </td>
              <td>{log.records_count}</td>
              <td>{new Date(log.started_at).toLocaleString()}</td>
              <td>
                <Button 
                  size="sm" 
                  variant="outline-primary"
                  onClick={() => triggerSync(log.brand_id)}
                >
                  Sync Now
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}

function ExportData() {
  const [brandId, setBrandId] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [format, setFormat] = useState('csv');
  const [exporting, setExporting] = useState(false);

  const handleExport = async (type) => {
    setExporting(true);
    
    let url = `${API_URL}/export/${type}?`;
    if (brandId) url += `brand_id=${brandId}&`;
    if (startDate) url += `start_date=${startDate}&`;
    if (endDate) url += `end_date=${endDate}&`;
    url += `format=${format}`;
    
    window.open(url, '_blank');
    
    setTimeout(() => setExporting(false), 2000);
  };

  return (
    <>
      <h1 className="mb-4">Export Data</h1>
      
      <Card className="mb-4">
        <Card.Body>
          <Card.Title>Export Filters</Card.Title>
          
          <Row>
            <Col md={3}>
              <Form.Group className="mb-3">
                <Form.Label>Brand</Form.Label>
                <Form.Select value={brandId} onChange={(e) => setBrandId(e.target.value)}>
                  <option value="">All Brands</option>
                  <option value="brand_a">Brand A</option>
                  <option value="brand_b">Brand B</option>
                  <option value="brand_c">Brand C</option>
                </Form.Select>
              </Form.Group>
            </Col>
            
            <Col md={3}>
              <Form.Group className="mb-3">
                <Form.Label>Start Date</Form.Label>
                <Form.Control 
                  type="date" 
                  value={startDate} 
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </Form.Group>
            </Col>
            
            <Col md={3}>
              <Form.Group className="mb-3">
                <Form.Label>End Date</Form.Label>
                <Form.Control 
                  type="date" 
                  value={endDate} 
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </Form.Group>
            </Col>
            
            <Col md={3}>
              <Form.Group className="mb-3">
                <Form.Label>Format</Form.Label>
                <Form.Select value={format} onChange={(e) => setFormat(e.target.value)}>
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="xlsx">Excel (XLSX)</option>
                </Form.Select>
              </Form.Group>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Row>
        <Col md={6}>
          <Card className="text-center">
            <Card.Body>
              <Card.Title>Export Orders</Card.Title>
              <Button 
                variant="primary" 
                onClick={() => handleExport('orders')}
                disabled={exporting}
              >
                {exporting ? <Spinner size="sm" /> : 'Export Orders'}
              </Button>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={6}>
          <Card className="text-center">
            <Card.Body>
              <Card.Title>Export Products</Card.Title>
              <Button 
                variant="success" 
                onClick={() => handleExport('products')}
                disabled={exporting}
              >
                {exporting ? <Spinner size="sm" /> : 'Export Products'}
              </Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
}

function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchAlerts = async () => {
    const response = await fetch(`${API_URL}/alerts/recent?limit=20`);
    const data = await response.json();
    setAlerts(data.alerts || []);
    setLoading(false);
  };

  if (loading) return <Spinner animation="border" />;

  return (
    <>
      <h1 className="mb-4">Recent Alerts</h1>
      
      {alerts.length === 0 ? (
        <Alert variant="success">No alerts found. System is healthy!</Alert>
      ) : (
        alerts.map((alert, idx) => (
          <Alert key={idx} variant="danger">
            <Alert.Heading>
              {alert.brand_id} - {alert.data_type}
            </Alert.Heading>
            <p>{alert.error_message}</p>
            <small>{new Date(alert.started_at).toLocaleString()}</small>
          </Alert>
        ))
      )}
    </>
  );
}

export default App;