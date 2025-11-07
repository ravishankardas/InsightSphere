// src/App.js
import React, { useState, useEffect, useCallback } from "react";
import { SignedIn, SignedOut, useUser } from "@clerk/clerk-react";
import "./App.css";

// Components
import TopNav from "./components/TopNav";
import SettingsPanel from "./components/SettingsPanel";
import DocumentsPanel from "./components/DocumentsPanel";
import ChatPanel from "./components/ChatPanel";
import AuthModal from "./components/AuthModal";
import DeleteConfirmationModal from './components/DeleteConfirmationModal';

export default function App() {
  const API_KEY = process.env.REACT_APP_API_KEY;
  const NUM_QUERIES_ALLOWED = process.env.REACT_APP_NUM_QUERIES_ALLOWED || 2;

  const { user, isSignedIn } = useUser();
  const userId = user?.primaryEmailAddress?.emailAddress || user?.id || null;

  // --- State Variables ---
  // API Config
  const [apiUrl, setApiUrl] = useState(
    process.env.NODE_ENV === 'development'
      ? process.env.REACT_APP_BACKEND_URL_DEV
      : process.env.REACT_APP_BACKEND_URL_PROD
  );
  
  // UI & Auth State
  const [showSettings, setShowSettings] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("signup");

  // Document State
  const [documents, setDocuments] = useState([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [deletingDoc, setDeletingDoc] = useState(null);
  
  // Upload State
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [file, setFile] = useState(null); // Kept for auto-upload logic

  // Chat/Query State
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  const [documentChats, setDocumentChats] = useState({}); // { docName: [messages] }
  const [messages, setMessages] = useState([]); // Current doc messages
  const [rateLimited, setRateLimited] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);
  
  // Delete Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [docToDelete, setDocToDelete] = useState(null);


  // --- Helper & Utility Functions ---
  const testBackendConnection = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/health`);
      if (res.ok) {
        console.log("Backend is reachable");
        return true;
      }
    } catch (err) {
      console.error("Backend connection failed:", err);
    }
    return false;
  }, [apiUrl]);

  // ---- Document Functions ----
  const loadDocuments = useCallback(async () => {
    if (!userId) return;

    setLoadingDocuments(true);
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents`, { method: "GET", headers });

      if (res.ok) {
        const data = await res.json();
        setDocuments(data || []);

        if (!selectedDocument && data && data.length > 0) {
          const first = data[0];
          const firstName = typeof first === "string" ? first : (first.source || first.name || first.file || "");
          if (firstName) setSelectedDocument(firstName);
        }
      } else {
        setUploadStatus({ type: "error", message: `Failed to load documents: ${res.status}` });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Failed to load documents: ${err.message}` });
    } finally {
      setLoadingDocuments(false);
    }
  }, [userId, API_KEY, apiUrl, selectedDocument]);

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    setDeletingDoc(docToDelete);
    setShowDeleteModal(false);
    
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(docToDelete)}`, { method: "DELETE", headers });

      if (res.ok) {
        setDocuments(documents.filter(doc => doc !== docToDelete));
        if (selectedDocument === docToDelete) setSelectedDocument(null);
        setUploadStatus({ type: "success", message: `Document "${docToDelete}" deleted successfully.` });
      } else {
        const data = await res.json();
        setUploadStatus({ type: "error", message: data.detail || "Failed to delete document." });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Network error: ${err.message}` });
    } finally {
      setDeletingDoc(null);
      setDocToDelete(null);
    }
  };

  const handleDocumentClick = (filename) => {
    if (selectedDocument === filename) return;

    // Save current document's chat history before switching
    if (selectedDocument && messages.length > 0) {
      setDocumentChats(prev => ({ ...prev, [selectedDocument]: messages }));
    }

    // Load the new document's chat history
    const newDocumentMessages = documentChats[filename] || [];
    setMessages(newDocumentMessages);
    setSelectedDocument(filename);
  };

  // ---- Upload & Query Handlers ---

  const handleUpload = async (selectedFile) => {
    if (!API_KEY || !isSignedIn || !selectedFile) {
      if (!isSignedIn) { setAuthMode("signup"); setShowAuthModal(true); }
      return;
    }

    setUploading(true);
    setUploadStatus({ type: "info", message: "Uploading and processing document..." });
    
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const headers = { "X-API-Key": API_KEY };
      if (userId) headers["X-User-Id"] = userId;
      
      const res = await fetch(`${apiUrl}/api/upload/pdf/auto?preset=balanced`, { method: "POST", headers, body: formData });
      const data = await res.json();
      
      if (res.ok) {
        const chunks = data.text_chunks || data.indexed_chunks || 0;
        const tables = data.tables || 0;
        const images = data.images || 0;
        let message = `✅ Document uploaded successfully! Processed ${chunks} text chunks`;
        if (tables > 0 || images > 0) {
          const parts = [];
          if (tables > 0) parts.push(`${tables} tables`);
          if (images > 0) parts.push(`${images} images`);
          message += ` and extracted ${parts.join(', ')}`;
        }
        setUploadStatus({ type: "success", message: message });

        setTimeout(() => { loadDocuments(); }, 2000); // Reload docs
        const returnedName = data?.file?.source || data?.source || selectedFile?.name;
        if (returnedName) setSelectedDocument(returnedName);
        
        // Clear file input
        const fileInput = document.getElementById('file-upload');
        if (fileInput) fileInput.value = '';

      } else {
        const errorMsg = data.detail || "Upload failed";
        setUploadStatus({ type: "error", message: `Upload failed: ${errorMsg}` });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Network error: ${err.message}.` });
    } finally {
      setUploading(false);
      setFile(null); // Clear file state
    }
  };

  const handleFileChange = async (e) => {
    if (!isSignedIn) { setAuthMode("signup"); setShowAuthModal(true); return; }
    
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    
    if (selectedFile.type !== "application/pdf") {
      setUploadStatus({ type: "error", message: "Please select a PDF file." });
      return;
    }

    setFile(selectedFile);
    setUploadStatus(null);
    await handleUpload(selectedFile);
  };

  const handleQuery = async () => {
    // ... [Copy the full logic for handleQuery from original App.js] ...
    if (rateLimited) {
      setMessages(prev => [...prev, {
        type: "error",
        content: `Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`,
        isUser: false
      }]);
      return;
    }
    if (!API_KEY) {
      setMessages(prev => [...prev, { type: "error", content: "Configuration Error: Missing API Key.", isUser: false }]);
      setQuerying(false);
      return;
    }
    if (!isSignedIn) { setAuthMode("signup"); setShowAuthModal(true); return; }
    if (!query.trim()) { setMessages(prev => [...prev, { type: "error", content: "Please enter a question.", isUser: false }]); return; }
    if (!selectedDocument) { setMessages(prev => [...prev, { type: "error", content: "Please upload and select a document first.", isUser: false }]); return; }
  
    // Add user message to chat
    const userMessage = { type: "user", content: query.trim(), isUser: true, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setQuerying(true);
    setQuery("");
  
    try {
      const headers = { "Content-Type": "application/json", "X-API-Key": API_KEY };
      if (userId) headers["X-User-Id"] = userId;
  
      const bodyPayload = {
        query: userMessage.content,
        top_k: 6,
        source: selectedDocument,
        use_query_rewriting: false,
      };
  
      const res = await fetch(`${apiUrl}/api/query`, { method: "POST", headers, body: JSON.stringify(bodyPayload) });
      const data = await res.json();
  
       if (res.status === 429) {
        const retryAfterHeader = res.headers.get('Retry-After');
        const waitTime = retryAfterHeader ? parseInt(retryAfterHeader) : 60;
        
        setRateLimited(true);
        setRetryAfter(waitTime);
        
        // Start countdown
        const interval = setInterval(() => {
          setRetryAfter(prev => {
            if (prev <= 1) {
              clearInterval(interval);
              setRateLimited(false);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
  
        throw new Error(`Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`);
      }
  
      if (res.ok) {
        if (data.answer && !data.answer.includes("OpenAI is not configured") && !data.answer.includes("no context found")) {
          const assistantMessage = {
            type: "assistant",
            content: data.answer,
            isUser: false,
            retrieved: data.sources || data.retrieved || [],
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, assistantMessage]);
        } else {
          let errorMessage = "The document was uploaded but no meaningful content was extracted. ";
          errorMessage += "This could be because:\n• The PDF is scanned or image-based\n• The backend AI service is not properly configured";
          const errorResponse = { type: "error", content: errorMessage, isUser: false, timestamp: new Date().toISOString() };
          setMessages(prev => [...prev, errorResponse]);
        }
      } else {
        const errorDetail = data.detail || "Query failed";
        let userFriendlyMessage = "Query failed. Please try again.";
        if (errorDetail.includes("OpenAI")) userFriendlyMessage = "Backend configuration error: AI service is not properly configured on the server.";
        else if (errorDetail.includes("no context")) userFriendlyMessage = "No searchable content found in the document. The PDF might be scanned or contain only images.";
        else if (errorDetail.includes("Authentication required")) userFriendlyMessage = "Authentication error: Please sign out and sign in again.";
        
        const errorMessage = { type: "error", content: userFriendlyMessage, isUser: false, timestamp: new Date().toISOString() };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (err) {
      const errorMessage = {
        type: "error",
        content: err.message.includes('Rate limited') ? err.message : `Network error: ${err.message}.`,
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setQuerying(false);
    }
    // ... [End of handleQuery logic] ...
  };
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  // --- Effects ---
  useEffect(() => { // Auto-save chat history
    if (selectedDocument && messages.length > 0) {
      setDocumentChats(prev => ({ ...prev, [selectedDocument]: messages }));
    }
  }, [messages, selectedDocument]);

  useEffect(() => { // Auto-scroll to bottom
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }, [messages, querying]); 

  useEffect(() => { // Auto-dismiss success messages
    if (uploadStatus?.type === 'success') {
      const timer = setTimeout(() => setUploadStatus(null), 4000);
      return () => clearTimeout(timer);
    }
    if (uploadStatus?.type === 'success' && !uploading && selectedDocument) {
      setTimeout(() => {
        const chatMessages = document.querySelector('.chat-messages');
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 100);
    }
  }, [uploadStatus, uploading, selectedDocument]);

  useEffect(() => { // Load documents on sign in
    if (isSignedIn && userId) {
      loadDocuments();
    } else {
      setDocuments([]);
      setSelectedDocument(null);
    }
  }, [isSignedIn, userId, loadDocuments]);

  useEffect(() => { // Initial connection test
    testBackendConnection();
  }, [apiUrl, testBackendConnection]);


  const openSignUp = () => { setAuthMode("signup"); setShowAuthModal(true); };
  const openSignIn = () => { setAuthMode("signin"); setShowAuthModal(true); };
  const handleDeleteClick = (filename) => { setDocToDelete(filename); setShowDeleteModal(true); };
  const handleDeleteCancel = () => { setShowDeleteModal(false); setDocToDelete(null); };

  return (
    <div className="app-container">
      <DeleteConfirmationModal
        show={showDeleteModal}
        filename={docToDelete}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      <AuthModal 
        showAuthModal={showAuthModal}
        authMode={authMode}
        setShowAuthModal={setShowAuthModal}
        setAuthMode={setAuthMode}
      />

      <TopNav
        showSettings={showSettings}
        setShowSettings={setShowSettings}
        openSignIn={openSignIn}
        openSignUp={openSignUp}
      />

      {showSettings && (
        <SettingsPanel 
          apiUrl={apiUrl} 
          setApiUrl={setApiUrl} 
          testBackendConnection={testBackendConnection} 
        />
      )}

      <div className="main-content two-column">
        <DocumentsPanel
          documents={documents}
          loadingDocuments={loadingDocuments}
          selectedDocument={selectedDocument}
          deletingDoc={deletingDoc}
          handleDocumentClick={handleDocumentClick}
          handleDeleteClick={handleDeleteClick}
        />

        <ChatPanel
          selectedDocument={selectedDocument}
          messages={messages}
          query={query}
          setQuery={setQuery}
          handleQuery={handleQuery}
          handleKeyPress={handleKeyPress}
          handleFileChange={handleFileChange}
          querying={querying}
          uploading={uploading}
          uploadStatus={uploadStatus}
          rateLimited={rateLimited}
          numQueriesAllowed={NUM_QUERIES_ALLOWED}
        />
      </div>
    </div>
  );
}