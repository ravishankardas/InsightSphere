import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { ClerkProvider } from '@clerk/clerk-react';
import * as Sentry from "@sentry/react";

// Initialize Sentry
Sentry.init({
  dsn: process.env.REACT_APP_SENTRY_DSN,
  // Setting this option to true will send default PII data to Sentry.
  // For example, automatic IP address collection on events
  sendDefaultPii: true
});

// Error Fallback Component
function ErrorFallback({ error, componentStack, resetError }) {
  return (
    <div style={{ 
      padding: '40px', 
      textAlign: 'center',
      fontFamily: 'Arial, sans-serif',
      maxWidth: '500px',
      margin: '100px auto',
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      backgroundColor: '#f9f9f9'
    }}>
      <h2 style={{ color: '#e74c3c', marginBottom: '20px' }}>😅 Something went wrong</h2>
      <p style={{ marginBottom: '20px', color: '#666' }}>
        We've been notified and are working to fix this issue.
      </p>
      <button 
        onClick={resetError}
        style={{
          padding: '10px 20px',
          background: '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer',
          fontSize: '16px'
        }}
      >
        Try Again
      </button>
      <details style={{ marginTop: '20px', textAlign: 'left' }}>
        <summary style={{ cursor: 'pointer', color: '#666', fontSize: '14px' }}>
          Technical Details
        </summary>
        <pre style={{ 
          background: '#f5f5f5', 
          padding: '10px', 
          borderRadius: '5px',
          overflow: 'auto',
          fontSize: '12px',
          marginTop: '10px'
        }}>
          {error?.toString() || 'Unknown error'}
        </pre>
      </details>
    </div>
  );
}

const clerkPubKey = process.env.NODE_ENV === 'development' 
  ? process.env.REACT_APP_CLERK_PUBLISHABLE_KEY_DEV 
  : process.env.REACT_APP_CLERK_PUBLISHABLE_KEY_PROD;

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ClerkProvider publishableKey={clerkPubKey}>
      <Sentry.ErrorBoundary fallback={ErrorFallback}>
        <App />
      </Sentry.ErrorBoundary>
    </ClerkProvider>
  </React.StrictMode>
);