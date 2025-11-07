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
  // Add this with your other state variables
  const [loadingChatHistory, setLoadingChatHistory] = useState(false);
  
  
  // Upload State
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [file, setFile] = useState(null); // Kept for auto-upload logic

  // Chat/Query State
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  const [documentChats, setDocumentChats] = useState({});
  const [loadingChats, setLoadingChats] = useState(false);
   // { docName: [messages] }
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

  const handleDocumentClick = async (filename) => {
  if (selectedDocument === filename) return;
  
  console.log(`🔄 Switching from ${selectedDocument} to ${filename}`);
  
  // Save current document before switching
  if (selectedDocument && messages.length > 0) {
    await saveChatToBackend(selectedDocument, messages);
  }
  
  setLoadingChatHistory(true); // 🔥 START LOADING
  
  // Check if we have the chat in local state
  if (documentChats[filename]) {
    // Load from local state (fast)
    setMessages(documentChats[filename]);
    setLoadingChatHistory(false); // 🔥 STOP LOADING immediately for local
    console.log(`✅ Loaded ${documentChats[filename].length} messages from local state`);
  } else {
    // Load from backend (first time or page refresh)
    setLoadingChats(true);
    try {
      const loadedMessages = await loadChatFromBackend(filename);
      setMessages(loadedMessages);
      
      // Update local state with loaded messages
      if (loadedMessages.length > 0) {
        setDocumentChats(prev => ({
          ...prev,
          [filename]: loadedMessages
        }));
      }
      console.log(`✅ Loaded ${loadedMessages.length} messages from backend`);
    } catch (error) {
      console.error("Error loading chat:", error);
      setMessages([]); // Start fresh if error
    } finally {
      setLoadingChats(false);
      setLoadingChatHistory(false); // 🔥 STOP LOADING
    }
  }
  
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
    if (rateLimited) {
      const errorMessage = {
        type: "error",
        content: `Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`,
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    if (!API_KEY) {
      const errorMessage = {
        type: "error", 
        content: "Configuration Error: Missing API Key.", 
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      setQuerying(false);
      return;
    }

    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }

    if (!query.trim()) {
      const errorMessage = {
        type: "error",
        content: "Please enter a question.",
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    if (!selectedDocument) {
      const errorMessage = {
        type: "error",
        content: "Please upload and select a document first.",
        isUser: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      return;
    }

    // Add user message to chat
    const userMessage = {
      type: "user",
      content: query.trim(),
      isUser: true,
      timestamp: new Date().toISOString()
    };
    
    // Update messages and save to local state immediately
    setMessages(prev => {
      const newMessages = [...prev, userMessage];
      // Update document chats in local state
      setDocumentChats(prevChats => ({
        ...prevChats,
        [selectedDocument]: newMessages
      }));
      return newMessages;
    });
    
    setQuerying(true);
    setQuery("");

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      };

      if (userId) {
        headers["X-User-Id"] = userId;
      }

      const bodyPayload = {
        query: userMessage.content,
        top_k: 6,
        source: selectedDocument,
        use_query_rewriting: false,
      };

      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

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

      const data = await res.json();

      if (res.ok) {
        if (data.answer && !data.answer.includes("OpenAI is not configured") && !data.answer.includes("no context found")) {
          const assistantMessage = {
            type: "assistant",
            content: data.answer,
            isUser: false,
            retrieved: data.sources || data.retrieved || [],
            timestamp: new Date().toISOString()
          };
          
          // Update messages with assistant response and save to local state
          setMessages(prev => {
            const newMessages = [...prev, assistantMessage];
            // Update document chats in local state
            setDocumentChats(prevChats => ({
              ...prevChats,
              [selectedDocument]: newMessages
            }));
            return newMessages;
          });

          // Save to backend immediately after successful response
          setTimeout(() => {
            saveChatToBackend(selectedDocument, [...messages, userMessage, assistantMessage]);
          }, 100);

        } else {
          let errorMessage = "The document was uploaded but no meaningful content was extracted. ";
          errorMessage += "This could be because:\n• The PDF is scanned or image-based\n• The backend AI service is not properly configured";
          
          const errorResponse = {
            type: "error",
            content: errorMessage,
            isUser: false,
            timestamp: new Date().toISOString()
          };
          
          setMessages(prev => {
            const newMessages = [...prev, errorResponse];
            // Update document chats in local state
            setDocumentChats(prevChats => ({
              ...prevChats,
              [selectedDocument]: newMessages
            }));
            return newMessages;
          });

          // Save error message to backend
          setTimeout(() => {
            saveChatToBackend(selectedDocument, [...messages, userMessage, errorResponse]);
          }, 100);
        }
      } else {
        const errorDetail = data.detail || "Query failed";
        let userFriendlyMessage = "Query failed. Please try again.";
        
        if (errorDetail.includes("OpenAI")) {
          userFriendlyMessage = "Backend configuration error: AI service is not properly configured on the server.";
        } else if (errorDetail.includes("no context")) {
          userFriendlyMessage = "No searchable content found in the document. The PDF might be scanned or contain only images.";
        } else if (errorDetail.includes("Authentication required")) {
          userFriendlyMessage = "Authentication error: Please sign out and sign in again.";
        }
        
        const errorMessage = {
          type: "error",
          content: userFriendlyMessage,
          isUser: false,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => {
          const newMessages = [...prev, errorMessage];
          // Update document chats in local state
          setDocumentChats(prevChats => ({
            ...prevChats,
            [selectedDocument]: newMessages
          }));
          return newMessages;
        });

        // Save error to backend
        setTimeout(() => {
          saveChatToBackend(selectedDocument, [...messages, userMessage, errorMessage]);
        }, 100);
      }
    } catch (err) {
      const errorMessage = {
        type: "error",
        content: err.message.includes('Rate limited') ? err.message : `Network error: ${err.message}.`,
        isUser: false,
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => {
        const newMessages = [...prev, errorMessage];
        // Update document chats in local state
        setDocumentChats(prevChats => ({
          ...prevChats,
          [selectedDocument]: newMessages
        }));
        return newMessages;
      });

      // Save network error to backend
      setTimeout(() => {
        saveChatToBackend(selectedDocument, [...messages, userMessage, errorMessage]);
      }, 100);
    } finally {
      setQuerying(false);
    }
  };
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };
  // API functions for chat persistence
  const saveChatToBackend = async (documentName, messages) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping save - not signed in or no document selected");
      return;
    }
    
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      console.log(`💾 Saving ${messages.length} messages for: ${documentName}`);
      
      const response = await fetch(`${apiUrl}/api/query/chats/save`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          document_name: documentName,
          messages: messages
        }),
      });

      const data = await response.json();
      if (data.success) {
        console.log("✅ Chat saved successfully");
      } else {
        console.error("❌ Failed to save chat:", data.message);
      }
    } catch (error) {
      console.error("❌ Error saving chat to backend:", error);
    }
  };

  const loadChatFromBackend = async (documentName) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping load - not signed in or no document name");
      return [];
    }
    
    try {
      const headers = {
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      console.log(`📂 Loading chat for: ${documentName}`);
      
      const response = await fetch(`${apiUrl}/api/query/chats/load/${encodeURIComponent(documentName)}`, {
        method: "GET",
        headers,
      });

      const data = await response.json();
      if (data.success) {
        console.log(`✅ Loaded ${data.messages.length} messages for ${documentName}`);
        return data.messages;
      } else {
        console.error("❌ Failed to load chat:", data.message);
        return [];
      }
    } catch (error) {
      console.error("❌ Error loading chat from backend:", error);
      return [];
    }
  };

  const loadAllChatsFromBackend = async () => {
    console.log("loadAllChatsFromBackend was called")
    // if (!isSignedIn || !userId) {
    //   console.log("Skipping load all - not signed in");
    //   return {};
    // }
    
    // try {
    //   const headers = {
    //     "X-API-Key": API_KEY,
    //     "X-User-Id": userId,
    //   };

    //   console.log("📚 Loading all chats for user");
      
    //   const response = await fetch(`${apiUrl}/api/query/chats/all`, {
    //     method: "GET",
    //     headers,
    //   });

    //   const data = await response.json();
    //   if (data.success) {
    //     console.log(`✅ Loaded ${Object.keys(data.chats).length} document chats`);
    //     return data.chats;
    //   } else {
    //     console.error("❌ Failed to load all chats:", data.message);
    //     return {};
    //   }
    // } catch (error) {
    //   console.error("❌ Error loading all chats from backend:", error);
    //   return {};
    // }
  };


  // Auto-save when messages change (with debounce)
  useEffect(() => {
    if (selectedDocument && messages.length > 0) {
      // Update local state immediately
      setDocumentChats(prev => ({
        ...prev,
        [selectedDocument]: messages
      }));
      
      // Debounced save to backend
      const saveTimeout = setTimeout(() => {
        saveChatToBackend(selectedDocument, messages);
      }, 5000); // Save after 5 seconds of inactivity
      
      return () => clearTimeout(saveTimeout);
    }
  }, [messages, selectedDocument]);


  // Add this useEffect to load chat history when page loads or document changes
// Load chat history when page loads or document changes
// Load chat history when page loads or document changes
useEffect(() => {
  const loadChatHistory = async () => {
    if (selectedDocument && userId) {
      setLoadingChatHistory(true); // 🔥 START LOADING
      try {
        const headers = {
          "X-API-Key": API_KEY,
          "X-User-Id": userId,
        };

        console.log(`📂 Loading chat for: ${selectedDocument}`);
        
        const response = await fetch(`${apiUrl}/api/query/chats/load/${encodeURIComponent(selectedDocument)}`, {
          method: "GET",
          headers,
        });

        const data = await response.json();
        if (data.success) {
          console.log(`✅ Loaded ${data.messages.length} messages for ${selectedDocument}`);
          setMessages(data.messages);
          
          // Also update local documentChats state
          setDocumentChats(prev => ({
            ...prev,
            [selectedDocument]: data.messages
          }));
        } else {
          console.log("No previous chat history found");
          setMessages([]); // Start fresh if no history
        }
      } catch (error) {
        console.log("No previous chat history found or error loading:", error);
        setMessages([]); // Start fresh on error
      } finally {
        setLoadingChatHistory(false); // 🔥 STOP LOADING (always runs)
      }
    } else {
      setMessages([]); // Clear messages if no document selected
      setLoadingChatHistory(false); // 🔥 STOP LOADING
    }
  };

  loadChatHistory();
}, [selectedDocument, userId, API_KEY, apiUrl]);



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
          loadingChats={loadingChats}
          loadingChatHistory={loadingChatHistory} // Add this line
        />
      </div>
    </div>
  );
}