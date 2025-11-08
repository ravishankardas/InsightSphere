// src/App.js
import React, { useState, useEffect, useCallback, useRef } from "react";
import { useUser } from "@clerk/clerk-react"; // Removed unused SignedIn, SignedOut
import "./App.css";

// Components
import TopNav from "./components/TopNav";
import DocumentsPanel from "./components/DocumentsPanel";
import ChatPanel from "./components/ChatPanel";
import AuthModal from "./components/AuthModal";
import DeleteConfirmationModal from './components/DeleteConfirmationModal';

export default function App() {
  const API_KEY = process.env.REACT_APP_API_KEY;
  const NUM_QUERIES_ALLOWED = process.env.REACT_APP_NUM_QUERIES_ALLOWED || 2;

  const { user, isSignedIn } = useUser();
  const userId = user?.primaryEmailAddress?.emailAddress || user?.id || null;
  
  // Refs for cleanup and debouncing
  const saveTimeoutRef = useRef(null);
  const rateLimitIntervalRef = useRef(null);

  
  // --- State Variables ---
  // API Config
  const [apiUrl] = useState(
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
  const [loadingChatHistory, setLoadingChatHistory] = useState(false);
  
  // Upload State
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  // Removed unused 'file' state

  // Chat/Query State
  const [query, setQuery] = useState("");
  const [querying, setQuerying] = useState(false);
  // Removed unused 'documentChats' and 'setLoadingChats' states
  const [messages, setMessages] = useState([]);
  const [rateLimited, setRateLimited] = useState(false);
  // Removed unused 'retryAfter' state
  
  // Delete Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [docToDelete, setDocToDelete] = useState(null);

  // Dark Mode
  const [darkMode, setDarkMode] = useState(false);

  // ---- API functions for chat persistence ----
  const saveChatToBackend = useCallback(async (documentName, messages) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping save - not signed in or no document selected");
      return;
    }
    
    // Don't save if we're just creating an empty record
    if (messages.length === 0) {
      console.log("Skipping save - no messages to save");
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
  }, [API_KEY, apiUrl, isSignedIn, userId]);

  const loadChatFromBackend = useCallback(async (documentName) => {
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
  }, [API_KEY, apiUrl, isSignedIn, userId]);

  // --- Helper & Utility Functions ---
  const testBackendConnection = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/health`);
      if (res.ok) {
        console.log("✅ Backend is reachable");
        return true;
      }
    } catch (err) {
      console.error("❌ Backend connection failed:", err);
    }
    return false;
  }, [apiUrl]);

  // ---- Cache Management Functions ----
  const getCachedChats = useCallback(() => {
    if (!userId) return {};
    try {
      return JSON.parse(localStorage.getItem(`chatHistory_${userId}`) || '{}');
    } catch (error) {
      console.error("❌ Error reading cache:", error);
      return {};
    }
  }, [userId]);

  const updateCache = useCallback((documentName, messages) => {
    if (!userId || !documentName) return;
    
    const cachedChats = getCachedChats();
    const updatedCache = {
      ...cachedChats,
      [documentName]: messages
    };
    
    localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(updatedCache));
    // Removed setDocumentChats since it's no longer used
  }, [userId, getCachedChats]);

  const clearCache = useCallback(() => {
    if (userId) {
      localStorage.removeItem(`chatHistory_${userId}`);
    }
    setMessages([]);
  }, [userId]);

  // Helper function to extract document name
  const getDocumentName = useCallback((doc) => {
    return typeof doc === "string" ? doc : (doc.source || doc.name || doc.file || "");
  }, []);

  // ---- Document Functions ----
  const loadDocuments = useCallback(async () => {
    if (!userId) return;

    setLoadingDocuments(true);
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents`, { method: "GET", headers });

      if (res.ok) {
        const data = await res.json();
        const normalizedDocuments = data || [];
        setDocuments(normalizedDocuments);

        // Auto-select first document if none selected
        if (!selectedDocument && normalizedDocuments.length > 0) {
          const firstDoc = normalizedDocuments[0];
          const firstName = getDocumentName(firstDoc);
          if (firstName) {
            setSelectedDocument(firstName.toLowerCase());
          }
        }
      } else {
        setUploadStatus({ type: "error", message: `Failed to load documents: ${res.status}` });
      }
    } catch (err) {
      setUploadStatus({ type: "error", message: `Failed to load documents: ${err.message}` });
    } finally {
      setLoadingDocuments(false);
    }
  }, [userId, API_KEY, apiUrl, selectedDocument, getDocumentName]);


  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode) {
      setDarkMode(JSON.parse(savedDarkMode));
    }
  }, []);

  // src/App.js (inside the component, after you declare darkMode state)
  useEffect(() => {
    // keep theme on html root for predictable scoping
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
    }
  }, [darkMode]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);



  const toggleDarkMode = () => {
     const htmlElement = document.documentElement;
    const currentTheme = htmlElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    htmlElement.setAttribute('data-theme', newTheme); 
    localStorage.setItem('theme', newTheme);
  };

  // ---- Load Documents AND Chat History on Login ----
  useEffect(() => {
    const loadDocumentsAndChats = async () => {
      if (isSignedIn && userId) {
        try {
          setLoadingDocuments(true);
          setLoadingChatHistory(true);
          
          console.log("📚 Loading documents and chat history...");
          
          // 1. Load documents first
          const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
          const res = await fetch(`${apiUrl}/api/documents`, { method: "GET", headers });

          if (res.ok) {
            const documentsData = await res.json();
            const normalizedDocuments = documentsData || [];
            setDocuments(normalizedDocuments);
            console.log(`✅ Loaded ${normalizedDocuments.length} documents`);

            // 2. Load chat history for ALL documents
            if (normalizedDocuments.length > 0) {
              const allChats = {};
              let loadedCount = 0;
              
              for (const doc of normalizedDocuments) {
                const docName = getDocumentName(doc);
                if (docName) {
                  try {
                    const normalizedDocName = docName.toLowerCase();
                    const messages = await loadChatFromBackend(normalizedDocName);
                    allChats[normalizedDocName] = messages;
                    loadedCount++;
                    console.log(`✅ Cached ${messages.length} messages for ${normalizedDocName}`);
                  } catch (error) {
                    console.error(`❌ Failed to load chat for ${docName}:`, error);
                    allChats[docName.toLowerCase()] = [];
                  }
                }
              }
              
              // Store in localStorage for fast access
              localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(allChats));
              
              // 3. Auto-select first document and load its messages
              const firstDoc = normalizedDocuments[0];
              const firstName = getDocumentName(firstDoc);
              if (firstName) {
                const normalizedFirstName = firstName.toLowerCase();
                setSelectedDocument(normalizedFirstName);
                setMessages(allChats[normalizedFirstName] || []);
              }
              
              console.log(`🎉 Loaded ${loadedCount} document chats to cache`);
            } else {
              console.log("No documents found for user");
            }
          } else {
            console.error("Failed to load documents:", res.status);
            setUploadStatus({ type: "error", message: `Failed to load documents: ${res.status}` });
          }
        } catch (error) {
          console.error("Error loading documents and chats:", error);
          setUploadStatus({ type: "error", message: `Error loading data: ${error.message}` });
        } finally {
          setLoadingDocuments(false);
          setLoadingChatHistory(false);
        }
      }
    };

    if (isSignedIn && userId) {
      loadDocumentsAndChats();
    } else {
      // Clear everything on logout
      setDocuments([]);
      setSelectedDocument(null);
      setMessages([]);
    }
  }, [isSignedIn, userId, API_KEY, apiUrl, getDocumentName, loadChatFromBackend]);

  // ---- Delete Functions ----
  const deleteChatHistoryFromBackend = useCallback(async (documentName) => {
    if (!isSignedIn || !userId || !documentName) {
      console.log("Skipping chat history deletion - not signed in");
      return;
    }
    
    try {
      const headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "X-User-Id": userId,
      };

      console.log(`🗑️ Deleting chat AND document for: ${documentName}`);
      
      const response = await fetch(`${apiUrl}/api/query/chats/delete/${encodeURIComponent(documentName)}`, {
        method: "DELETE",
        headers,
      });

      const data = await response.json();
      if (data.success) {
        console.log("✅ Chat history AND document content deleted from backend");
        if (data.chroma_deleted !== undefined) {
          console.log(`📊 ChromaDB deletion: ${data.chroma_deleted ? 'Success' : 'Not found'}`);
        }
      } else {
        console.error("❌ Failed to delete chat history and document:", data.message);
      }
    } catch (error) {
      console.error("❌ Error deleting chat history and document:", error);
    }
  }, [API_KEY, apiUrl, isSignedIn, userId]);

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    setDeletingDoc(docToDelete);
    setShowDeleteModal(false);
    
    try {
      const headers = { "X-API-Key": API_KEY, "X-User-Id": userId };
      const res = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(docToDelete)}`, { 
        method: "DELETE", 
        headers 
      });

      if (res.ok) {
        // 1. Remove document from documents list
        setDocuments(documents.filter(doc => doc !== docToDelete));
        
        // 2. Clear chat history from localStorage cache
        const cachedChats = getCachedChats();
        delete cachedChats[docToDelete];
        localStorage.setItem(`chatHistory_${userId}`, JSON.stringify(cachedChats));
        
        // 3. Clear current messages if viewing the deleted document
        if (selectedDocument === docToDelete) {
          setSelectedDocument(null);
          setMessages([]);
        }
        
        // 4. Also delete from backend database
        await deleteChatHistoryFromBackend(docToDelete);
        
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

  // ---- Document Selection Handler ----
  const handleDocumentClick = async (filename) => {
    const normalizedFilename = filename.toLowerCase();
    
    if (selectedDocument === normalizedFilename) return;
    
    console.log(`🔄 Switching from ${selectedDocument} to ${normalizedFilename}`);
    
    // Save current document before switching
    if (selectedDocument && messages.length > 0) {
      await saveChatToBackend(selectedDocument, messages);
    }
    
    setLoadingChatHistory(true);
    
    // Try to load from cache FIRST (instant)
    const cachedChats = getCachedChats();
    
    if (cachedChats[normalizedFilename]) {
      setMessages(cachedChats[normalizedFilename]);
      setLoadingChatHistory(false);
      console.log(`⚡ Loaded ${cachedChats[normalizedFilename].length} messages from cache`);
    } else {
      // Fallback to API
      try {
        const loadedMessages = await loadChatFromBackend(normalizedFilename);
        setMessages(loadedMessages);
        
        // Update cache for next time
        updateCache(normalizedFilename, loadedMessages);
        console.log(`✅ Loaded ${loadedMessages.length} messages from backend and cached`);
      } catch (error) {
        console.error("Error loading chat:", error);
        setMessages([]);
      } finally {
        setLoadingChatHistory(false);
      }
    }
    
    setSelectedDocument(normalizedFilename);
  };

  // ---- Upload & Query Handlers ----
  const handleUpload = async (selectedFile) => {
    if (!API_KEY || !isSignedIn || !selectedFile) {
      if (!isSignedIn) { 
        setAuthMode("signup"); 
        setShowAuthModal(true); 
      }
      return;
    }

    setUploading(true);
    setUploadStatus({ type: "info", message: "Uploading and processing document..." });
    
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const headers = { "X-API-Key": API_KEY };
      if (userId) headers["X-User-Id"] = userId;
      
      const res = await fetch(`${apiUrl}/api/upload/pdf/auto?preset=balanced`, { 
        method: "POST", 
        headers, 
        body: formData 
      });
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

        // Save current chat before switching to new document
        if (selectedDocument && messages.length > 0) {
          await saveChatToBackend(selectedDocument, messages);
        }

        const returnedName = data?.file?.source || data?.source || selectedFile?.name;
        if (returnedName) {
          const normalizedName = returnedName.toLowerCase();
          
          // Check if this document already has chat history
          setLoadingChatHistory(true);
          try {
            const existingChat = await loadChatFromBackend(normalizedName);
            
            if (existingChat && existingChat.length > 0) {
              // Document has existing chat history - load it
              setMessages(existingChat);
              updateCache(normalizedName, existingChat);
              console.log(`📖 Loaded existing chat history (${existingChat.length} messages) for ${normalizedName}`);
            } else {
              // New document - clear chat area
              setMessages([]);
              console.log(`🆕 New document - chat area cleared for ${normalizedName}`);
              
              // Create empty chat record for new document
              await saveChatToBackend(normalizedName, []);
            }
          } catch (error) {
            console.error("Error checking chat history:", error);
            // If there's an error, assume it's a new document
            setMessages([]);
            await saveChatToBackend(normalizedName, []);
          } finally {
            setLoadingChatHistory(false);
          }
          
          setSelectedDocument(normalizedName);
        }
        
        // Refresh documents list
        setTimeout(() => { loadDocuments(); }, 2000);
        
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
    }
  };

  const handleFileChange = async (e) => {
    if (!isSignedIn) { 
      setAuthMode("signup"); 
      setShowAuthModal(true); 
      return; 
    }
    
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    
    if (selectedFile.type !== "application/pdf") {
      setUploadStatus({ type: "error", message: "Please select a PDF file." });
      return;
    }

    setUploadStatus(null);
    await handleUpload(selectedFile);
  };

  // Helper functions for query handling
  const createMessage = (type, content, isUser, retrieved = []) => {
    return {
      type,
      content,
      isUser,
      retrieved,
      timestamp: new Date().toISOString()
    };
  };

  const addErrorMessage = (message) => {
    const errorMessage = createMessage("error", message, false);
    setMessages(prev => [...prev, errorMessage]);
  };

  const updateMessagesAndCache = (newMessage) => {
    setMessages(prev => {
      const newMessages = [...prev, newMessage];
      updateCache(selectedDocument, newMessages);
      return newMessages;
    });
  };

  const handleRateLimit = (res) => {
    const retryAfterHeader = res.headers.get('Retry-After');
    const waitTime = retryAfterHeader ? parseInt(retryAfterHeader) : 60;
    
    setRateLimited(true);
    
    // Clear any existing interval
    if (rateLimitIntervalRef.current) {
      clearInterval(rateLimitIntervalRef.current);
    }
    
    rateLimitIntervalRef.current = setInterval(() => {
      setRateLimited(false);
      clearInterval(rateLimitIntervalRef.current);
    }, waitTime * 1000);
  };

  const handleEmptyResponse = (userMessage) => {
    let errorMessage = "The document was uploaded but no meaningful content was extracted. ";
    errorMessage += "This could be because:\n• The PDF is scanned or image-based\n• The backend AI service is not properly configured";
    
    const errorResponse = createMessage("error", errorMessage, false);
    updateMessagesAndCache(errorResponse);
    scheduleBackendSave([...messages, userMessage, errorResponse]);
  };

  const handleQueryError = (data, userMessage) => {
    const errorDetail = data.detail || "Query failed";
    let userFriendlyMessage = "Query failed. Please try again.";
    
    if (errorDetail.includes("OpenAI")) {
      userFriendlyMessage = "Backend configuration error: AI service is not properly configured on the server.";
    } else if (errorDetail.includes("no context")) {
      userFriendlyMessage = "No searchable content found in the document. The PDF might be scanned or contain only images.";
    } else if (errorDetail.includes("Authentication required")) {
      userFriendlyMessage = "Authentication error: Please sign out and sign in again.";
    }
    
    const errorMessage = createMessage("error", userFriendlyMessage, false);
    updateMessagesAndCache(errorMessage);
    scheduleBackendSave([...messages, userMessage, errorMessage]);
  };

  const handleQueryException = (err, userMessage) => {
    const errorMessage = createMessage(
      "error", 
      err.message.includes('Rate limited') ? err.message : `Network error: ${err.message}.`, 
      false
    );
    
    updateMessagesAndCache(errorMessage);
    scheduleBackendSave([...messages, userMessage, errorMessage]);
  };

  const scheduleBackendSave = (messagesToSave) => {
    setTimeout(() => {
      saveChatToBackend(selectedDocument, messagesToSave);
    }, 100);
  };

  const handleQuery = async () => {
    // Validation checks
    if (rateLimited) {
      addErrorMessage(`Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`);
      return;
    }

    if (!API_KEY) {
      addErrorMessage("Configuration Error: Missing API Key.");
      setQuerying(false);
      return;
    }

    if (!isSignedIn) {
      setAuthMode("signup");
      setShowAuthModal(true);
      return;
    }

    if (!query.trim()) {
      addErrorMessage("Please enter a question.");
      return;
    }

    if (!selectedDocument) {
      addErrorMessage("Please upload and select a document first.");
      return;
    }

    // Add user message to chat
    const userMessage = createMessage("user", query.trim(), true);
    updateMessagesAndCache(userMessage);
    
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
        query: getConversationContext(userMessage.content),
        top_k: 6,
        source: selectedDocument.toLowerCase(),
        use_query_rewriting: false,
      };

      const res = await fetch(`${apiUrl}/api/query`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

      if (res.status === 429) {
        handleRateLimit(res);
        throw new Error(`Rate limited. Only allowed ${NUM_QUERIES_ALLOWED} queries per day.`);
      }

      const data = await res.json();

      if (res.ok) {
        if (data.answer && !data.answer.includes("OpenAI is not configured") && !data.answer.includes("no context found")) {
          const assistantMessage = createMessage(
            "assistant", 
            data.answer, 
            false, 
            data.sources || data.retrieved || []
          );
          
          updateMessagesAndCache(assistantMessage);
          scheduleBackendSave([...messages, userMessage, assistantMessage]);

        } else {
          handleEmptyResponse(userMessage);
        }
      } else {
        handleQueryError(data, userMessage);
      }
    } catch (err) {
      handleQueryException(err, userMessage);
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

  // Conversation memory helper
  const getConversationContext = (currentQuery) => {
    if (!selectedDocument || !userId) return currentQuery;
    
    // Check if this query needs conversation context
    const needsMemory = 
      currentQuery.toLowerCase().includes('what was') ||
      currentQuery.toLowerCase().includes('previous') ||
      currentQuery.toLowerCase().includes('again') ||
      currentQuery.toLowerCase().includes('earlier') ||
      currentQuery.toLowerCase().includes('before');
    
    if (!needsMemory) return currentQuery;
    
    // Get recent messages from localStorage cache
    const cachedChats = getCachedChats();
    const currentChat = cachedChats[selectedDocument] || [];
    
    if (currentChat.length < 2) return currentQuery;
    
    // Get last 2 Q&A pairs for context
    const recentPairs = [];
    for (let i = Math.max(0, currentChat.length - 4); i < currentChat.length; i += 2) {
      if (currentChat[i] && currentChat[i + 1]) {
        recentPairs.push({
          question: currentChat[i].content,
          answer: currentChat[i + 1].content
        });
      }
    }
    
    if (recentPairs.length === 0) return currentQuery;
    
    // Build enhanced query with context
    let context = "Previous conversation:\n";
    recentPairs.forEach((pair, index) => {
      context += `Q: ${pair.question}\nA: ${pair.answer}\n\n`;
    });
    
    return `${context}Current question: ${currentQuery}`;
  };

  // Auto-save when messages change (with debounce)
  useEffect(() => {
    if (selectedDocument && messages.length > 0) {
      // Update cache immediately
      updateCache(selectedDocument, messages);
      
      // Clear any existing timeout
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      
      // Debounced save to backend
      saveTimeoutRef.current = setTimeout(() => {
        saveChatToBackend(selectedDocument, messages);
      }, 5000);
      
      return () => {
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current);
        }
      };
    }
  }, [messages, selectedDocument, updateCache, saveChatToBackend]);

  // Clear cache and intervals on logout
  useEffect(() => {
    if (!isSignedIn) {
      clearCache();
    }
    
    return () => {
      // Cleanup intervals on unmount
      if (rateLimitIntervalRef.current) {
        clearInterval(rateLimitIntervalRef.current);
      }
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [isSignedIn, clearCache]);

  // Load initial chat from cache when document is selected
  useEffect(() => {
    if (selectedDocument && userId) {
      const cachedChats = getCachedChats();
      if (cachedChats[selectedDocument]) {
        setMessages(cachedChats[selectedDocument]);
        console.log(`⚡ Loaded ${cachedChats[selectedDocument].length} messages from cache for ${selectedDocument}`);
      } else {
        // If not in cache, load from backend
        const loadFromBackend = async () => {
          setLoadingChatHistory(true);
          try {
            const loadedMessages = await loadChatFromBackend(selectedDocument);
            setMessages(loadedMessages);
            updateCache(selectedDocument, loadedMessages);
          } catch (error) {
            console.error("Error loading chat:", error);
            setMessages([]);
          } finally {
            setLoadingChatHistory(false);
          }
        };
        loadFromBackend();
      }
    }
  }, [selectedDocument, userId, getCachedChats, updateCache, loadChatFromBackend]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }, [messages, querying]);

  // Auto-clear success messages
  useEffect(() => {
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

  // Test backend connection on mount
  useEffect(() => {
    testBackendConnection();
  }, [apiUrl, testBackendConnection]);

  // UI Handlers
  const openSignUp = () => { setAuthMode("signup"); setShowAuthModal(true); };
  const openSignIn = () => { setAuthMode("signin"); setShowAuthModal(true); };
  const handleDeleteClick = (filename) => { setDocToDelete(filename); setShowDeleteModal(true); };
  const handleDeleteCancel = () => { setShowDeleteModal(false); setDocToDelete(null); };

  return (
    <div className="app-container" data-theme={darkMode ? 'dark' : 'light'}>
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
      darkMode={darkMode}
      toggleDarkMode={toggleDarkMode}
    />

      {/* {showSettings && (
        <SettingsPanel 
          apiUrl={apiUrl} 
          setApiUrl={setApiUrl} 
          testBackendConnection={testBackendConnection} 
        />
      )} */}

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
          loadingChatHistory={loadingChatHistory}
        />
      </div>
    </div>
  );
}