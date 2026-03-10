import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu, Button } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import AgentList from './pages/AgentList';
import AgentDetail from './pages/AgentDetail';
import RelationshipManager from './pages/RelationshipManager';
import SimulationDesigner from './pages/SimulationDesigner';
import WorldDesigner from './pages/WorldDesigner';
import LLMReplacementExperiment from './pages/LLMReplacementExperiment';
import { AuthProvider, useAuth } from './context/AuthContext';
import { SimulationProvider } from './context/SimulationContext';

const { Header, Content, Footer } = Layout;

// Error Boundary for component-level error handling
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Component Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Component Loading Error</h2>
          <p>This component failed to load. Please try refreshing the page.</p>
          <pre style={{ backgroundColor: '#f5f5f5', padding: '10px', borderRadius: '4px' }}>
            {this.state.error?.toString()}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

// Enable authentication check
const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token } = useAuth();
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { logout, isAuthenticated } = useAuth();
  const location = useLocation();
  
  const getSelectedKey = () => {
    if (location.pathname === '/') return ['1'];
    if (location.pathname.startsWith('/agent')) return ['1'];
    if (location.pathname === '/relationships') return ['2'];
    if (location.pathname === '/simulation') return ['3'];
    if (location.pathname === '/world') return ['4'];
    if (location.pathname === '/llm-experiment') return ['5'];
    return ['1'];
  };

  const menuItems = [
    { key: '1', label: <Link to="/">Agents</Link> },
    { key: '2', label: <Link to="/relationships">Relationships</Link> },
    { key: '3', label: <Link to="/simulation">Simulation</Link> },
    { key: '4', label: <Link to="/world">World</Link> },
    { key: '5', label: <Link to="/llm-experiment">LLM实验</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ 
          color: 'white', 
          fontSize: '18px', 
          fontWeight: 'bold', 
          marginRight: '24px',
          minWidth: '200px'
        }}>
          AI Simulation Platform
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={getSelectedKey()}
          items={menuItems}
          style={{ flex: 1 }}
        />
        {isAuthenticated ? (
          <Button type="link" style={{ color: 'white' }} onClick={logout}>
            Logout
          </Button>
        ) : (
          <div>
            <Link to="/login">
              <Button type="link" style={{ color: 'white', marginRight: '8px' }}>
                Login
              </Button>
            </Link>
            <Link to="/register">
              <Button type="link" style={{ color: 'white' }}>
                Register
              </Button>
            </Link>
          </div>
        )}
      </Header>
      
      <Content style={{ padding: '0 50px', marginTop: '16px' }}>
        <div style={{ 
          background: 'white', 
          padding: '24px', 
          minHeight: 'calc(100vh - 134px)',
          borderRadius: '8px'
        }}>
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </div>
      </Content>
      
      <Footer style={{ textAlign: 'center' }}>
        AI Simulation Platform ©{new Date().getFullYear()}
      </Footer>
    </Layout>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <ErrorBoundary>
        <AuthProvider>
          <SimulationProvider>
            <AppLayout>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={
                  <ErrorBoundary>
                    <Login />
                  </ErrorBoundary>
                } />
                <Route path="/register" element={
                  <ErrorBoundary>
                    <Register />
                  </ErrorBoundary>
                } />
                
                {/* Protected routes */}
                <Route path="/" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <AgentList />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="/agent/:id" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <AgentDetail />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="/relationships" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <RelationshipManager />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="/simulation" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <SimulationDesigner />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="/world" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <WorldDesigner />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="/llm-experiment" element={
                  <PrivateRoute>
                    <ErrorBoundary>
                      <LLMReplacementExperiment />
                    </ErrorBoundary>
                  </PrivateRoute>
                } />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppLayout>
          </SimulationProvider>
        </AuthProvider>
      </ErrorBoundary>
    </Router>
  );
};

export default App;