"use client";

import React, { useState, useRef, useEffect, Suspense } from "react";
import { useAuth, WalletAuth, cookieUtils, TopUpModal } from "@compute3/shared-ui";
import { useRouter, useSearchParams } from "next/navigation";
import { marked } from "marked";

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Chat {
  id: string;
  title: string;
  messages: Message[];
  timestamp: number;
}

interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

// Configure marked
marked.setOptions({
  breaks: true,
  gfm: true,
});

function ChatPageContent() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [initialMessageSent, setInitialMessageSent] = useState(false);

  // Theme
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  // Chats
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  // Models
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [loadingModels, setLoadingModels] = useState(true);

  // UI State
  const [message, setMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Balance
  interface Balance {
    user_id: string;
    balance: string;
    balance_units: number;
    rewards_balance: string;
    rewards_balance_units: number;
    total_balance: string;
    total_balance_units: number;
    currency: string;
    decimals: number;
  }
  const [balance, setBalance] = useState<Balance | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('c3_chat_theme') as 'light' | 'dark' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    }
  }, []);

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('c3_chat_theme', theme);
  }, [theme]);

  // Load chats from localStorage
  useEffect(() => {
    const storedChats = localStorage.getItem('c3_chats');
    if (storedChats) {
      const parsedChats = JSON.parse(storedChats) as Chat[];
      setChats(parsedChats);
      if (parsedChats.length > 0) {
        setCurrentChatId(parsedChats[0].id);
        setMessages(parsedChats[0].messages);
      }
    }
  }, []);

  // Save chats to localStorage
  useEffect(() => {
    if (chats.length > 0) {
      localStorage.setItem('c3_chats', JSON.stringify(chats));
    }
  }, [chats]);

  // Redirect if not authenticated (but skip if we have ?message= - will create free user)
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const hasMessage = searchParams.get('message');
      if (!hasMessage) {
        router.push('/');
      }
    }
  }, [isLoading, isAuthenticated, router, searchParams]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const authToken = document.cookie
          .split('; ')
          .find(row => row.startsWith('auth_token='))
          ?.split('=')[1];

        if (!authToken) {
          setLoadingModels(false);
          return;
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_LLM_API_URL}/models`, {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });

        if (!response.ok) throw new Error('Failed to fetch models');

        const data = await response.json();
        const modelList = data.data || [];
        setModels(modelList);

        if (modelList.length > 0) {
          const savedModel = localStorage.getItem('c3_chat_model');
          if (savedModel && modelList.find((m: Model) => m.id === savedModel)) {
            setSelectedModel(savedModel);
          } else {
            setSelectedModel(modelList[0].id);
          }
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      } finally {
        setLoadingModels(false);
      }
    };

    if (isAuthenticated) {
      fetchModels();
    }
  }, [isAuthenticated]);

  // Fetch balance
  const fetchBalance = async () => {
    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) return;

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/balance`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setBalance(data);
      }
    } catch (error) {
      console.error('Error fetching balance:', error);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchBalance();
    }
  }, [isAuthenticated]);

  // Handle initial message from URL param - auto-create free user if needed
  useEffect(() => {
    if (initialMessageSent || isLoading) return;

    const encodedMessage = searchParams.get('message');
    if (!encodedMessage) return;

    let decodedMessage: string;
    try {
      decodedMessage = atob(encodedMessage);
      if (!decodedMessage.trim()) return;
    } catch (e) {
      console.error('Failed to decode message:', e);
      return;
    }

    // Store message for later
    localStorage.setItem('c3_pending_chat_message', decodedMessage);

    // If not authenticated, create a free user
    if (!isAuthenticated) {
      const createFreeUser = async () => {
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/auth/free`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });

          if (!response.ok) throw new Error('Failed to create free user');

          const data = await response.json();
          // Store JWT token in cookie
          document.cookie = `auth_token=${data.token}; path=/; max-age=${data.expires_in}; SameSite=Lax`;
          // Clear URL param and reload to trigger auth
          router.replace('/');
          window.location.reload();
        } catch (e) {
          console.error('Failed to create free user:', e);
          // Fall back to showing login
          localStorage.removeItem('c3_pending_chat_message');
        }
      };
      createFreeUser();
    } else {
      // Already authenticated, clear URL param
      router.replace('/');
    }
  }, [searchParams, initialMessageSent, isLoading, isAuthenticated, router]);

  // Load pending message once authenticated and ready
  useEffect(() => {
    if (!isAuthenticated || loadingModels || !selectedModel || initialMessageSent) return;

    const pendingMsg = localStorage.getItem('c3_pending_chat_message');
    if (pendingMsg) {
      localStorage.removeItem('c3_pending_chat_message');
      setInitialMessageSent(true);
      setMessage(pendingMsg);
    }
  }, [isAuthenticated, loadingModels, selectedModel, initialMessageSent]);

  const handleModelChange = (modelId: string) => {
    setSelectedModel(modelId);
    localStorage.setItem('c3_chat_model', modelId);
  };

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const startNewChat = () => {
    const newChat: Chat = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      messages: [],
      timestamp: Date.now()
    };
    setChats(prev => [newChat, ...prev]);
    setCurrentChatId(newChat.id);
    setMessages([]);
  };

  const selectChat = (chatId: string) => {
    const chat = chats.find(c => c.id === chatId);
    if (chat) {
      setCurrentChatId(chatId);
      setMessages(chat.messages);
    }
  };

  const deleteChat = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updatedChats = chats.filter(c => c.id !== chatId);
    setChats(updatedChats);

    if (currentChatId === chatId) {
      if (updatedChats.length > 0) {
        setCurrentChatId(updatedChats[0].id);
        setMessages(updatedChats[0].messages);
      } else {
        setCurrentChatId(null);
        setMessages([]);
      }
    }

    if (updatedChats.length === 0) {
      localStorage.removeItem('c3_chats');
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim() || isStreaming || !selectedModel) return;

    const userMessage = message.trim();
    setMessage('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Create chat if needed
    let chatId = currentChatId;
    if (!chatId) {
      chatId = crypto.randomUUID();
      const newChat: Chat = {
        id: chatId,
        title: userMessage.substring(0, 30),
        messages: [],
        timestamp: Date.now()
      };
      setChats(prev => [newChat, ...prev]);
      setCurrentChatId(chatId);
    }

    // Add user message
    const updatedMessages: Message[] = [...messages, { role: 'user', content: userMessage }];
    setMessages(updatedMessages);
    setIsStreaming(true);

    // Add empty assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) throw new Error('No auth token');

      const response = await fetch(`${process.env.NEXT_PUBLIC_LLM_API_URL}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          model: selectedModel,
          messages: updatedMessages,
          temperature: 0.7,
          stream: true
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Error ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let fullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '' || !line.startsWith('data: ')) continue;

          const data = line.slice(6);
          if (data === '[DONE]') break;

          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content;
            if (content) {
              fullResponse += content;
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages[newMessages.length - 1] = {
                  role: 'assistant',
                  content: fullResponse
                };
                return newMessages;
              });
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }

      // Update chat in state
      const finalMessages: Message[] = [
        ...updatedMessages,
        { role: 'assistant', content: fullResponse }
      ];

      setChats(prev => prev.map(chat =>
        chat.id === chatId
          ? {
              ...chat,
              messages: finalMessages,
              title: chat.title === 'New Chat' ? userMessage.substring(0, 30) : chat.title
            }
          : chat
      ));

    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = {
          role: 'assistant',
          content: `Error: ${errorMessage}`
        };
        return newMessages;
      });
    } finally {
      setIsStreaming(false);
      fetchBalance();
    }
  };

  const renderMarkdown = (content: string) => {
    const html = marked.parse(content) as string;
    return { __html: html };
  };

  // Check if we're creating a free user (has ?message= param)
  const hasMessageParam = searchParams.get('message');

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-text)] text-xl">Loading...</div>
      </div>
    );
  }

  // If not authenticated and no message param, show login
  // (If has message param, free user creation is in progress)
  if (!isAuthenticated && !hasMessageParam) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[var(--color-bg)]">
        <WalletAuth
          onAuthSuccess={(jwt, userId) => {
            console.log('Auth success:', { userId });
            // Reload the page to let AuthProvider detect the auth_token cookie
            window.location.reload();
          }}
        />
      </div>
    );
  }

  // Show loading while creating free user
  if (!isAuthenticated && hasMessageParam) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-text)] text-xl">Setting up your chat...</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex overflow-hidden bg-[var(--color-bg)]">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-72' : 'w-0'} transition-all duration-300 flex-shrink-0 border-r border-[var(--color-border)] flex flex-col overflow-hidden bg-[var(--color-bg-secondary)]`}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-[var(--color-border)]">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-bold text-[var(--color-primary)]">COMPUTE3 CHAT</h1>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-[var(--color-border)] transition-colors"
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              )}
            </button>
          </div>
          <button
            onClick={startNewChat}
            className="w-full py-2.5 px-4 border border-[var(--color-primary)] text-[var(--color-primary)] rounded-lg hover:bg-[var(--color-primary)] hover:text-white transition-colors font-medium"
          >
            + New Chat
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          <h3 className="text-xs font-semibold text-[var(--color-primary)] uppercase tracking-wider mb-3">History</h3>
          <div className="space-y-2">
            {chats.map(chat => (
              <div
                key={chat.id}
                onClick={() => selectChat(chat.id)}
                className={`group relative p-3 rounded-lg cursor-pointer transition-colors ${
                  currentChatId === chat.id
                    ? 'bg-[var(--color-primary)] bg-opacity-20 border border-[var(--color-primary)]'
                    : 'hover:bg-[var(--color-border)]'
                }`}
              >
                <span className="block truncate pr-6 text-sm">{chat.title || 'New Chat'}</span>
                <button
                  onClick={(e) => deleteChat(chat.id, e)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500 hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[var(--color-border)] space-y-4">
          {/* Balance Section */}
          {balance && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-[var(--color-text)] opacity-70 uppercase tracking-wider">
                  Balance
                </h3>
                <button
                  onClick={() => setShowTopUpModal(true)}
                  className="text-xs font-semibold text-[var(--color-primary)] hover:underline"
                >
                  Top Up
                </button>
              </div>
              <div className="bg-[var(--color-bg-secondary)] p-3 rounded-lg">
                <p className="text-2xl font-bold text-[var(--color-text)]">${balance.balance}</p>
                {balance.rewards_balance && parseFloat(balance.rewards_balance) > 0 && (
                  <p className="text-xs text-[var(--color-text)] opacity-50 mt-1">
                    Rewards: ${balance.rewards_balance}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Logout Button */}
          <button
            onClick={() => {
              // Remove auth token cookie
              cookieUtils.remove('auth_token');
              // Clear local storage
              localStorage.removeItem('c3_chats');
              // Reload page to trigger auth check
              window.location.reload();
            }}
            className="w-full py-2 px-4 text-sm text-red-500 hover:bg-red-500 hover:text-white rounded-lg transition-colors"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="p-4 border-b border-[var(--color-border)] flex items-center gap-4">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-[var(--color-border)] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <select
            value={selectedModel}
            onChange={(e) => handleModelChange(e.target.value)}
            disabled={loadingModels}
            className="flex-1 max-w-xs px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] text-sm focus:outline-none focus:border-[var(--color-primary)]"
          >
            {loadingModels ? (
              <option>Loading models...</option>
            ) : models.length === 0 ? (
              <option>No models available</option>
            ) : (
              models.map(model => (
                <option key={model.id} value={model.id}>
                  {model.id}
                </option>
              ))
            )}
          </select>

          <button
            onClick={() => setShowLoginModal(true)}
            className="ml-auto px-4 py-2 text-sm font-medium text-[var(--color-primary)] border border-[var(--color-primary)] rounded-lg hover:bg-[var(--color-primary)] hover:text-white transition-colors"
          >
            Login for more models
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <h2 className="text-2xl font-bold text-[var(--color-primary)] mb-2">Welcome to Compute3 Chat</h2>
              <p className="text-[var(--color-text)] opacity-70">Start a conversation by typing a message below</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-[var(--color-primary)] text-white'
                        : 'bg-[var(--color-bg-secondary)] border border-[var(--color-border)]'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    ) : msg.content ? (
                      <div
                        className="text-sm markdown-content"
                        dangerouslySetInnerHTML={renderMarkdown(msg.content)}
                      />
                    ) : (
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-[var(--color-primary)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-[var(--color-border)]">
          <div className="max-w-3xl mx-auto flex gap-3">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Shift+Enter for new line)"
              disabled={isStreaming || !selectedModel}
              rows={1}
              className="flex-1 px-4 py-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] text-sm resize-none focus:outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
            />
            <button
              onClick={handleSendMessage}
              disabled={isStreaming || !message.trim() || !selectedModel}
              className="btn-primary text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Top Up Modal */}
      <TopUpModal
        isOpen={showTopUpModal}
        onClose={() => setShowTopUpModal(false)}
        onSuccess={() => {
          // Refresh balance after successful top-up
          fetchBalance();
        }}
      />

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-bg)] rounded-2xl shadow-2xl p-8 max-w-md w-full relative border border-[var(--color-border)]">
            <button
              onClick={() => setShowLoginModal(false)}
              className="absolute top-4 right-4 text-[var(--color-text)] opacity-50 hover:opacity-100 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <WalletAuth
              showTitle={true}
              title="Connect Wallet"
              description="Sign in with your wallet to save your chat history and top up your account"
              onAuthSuccess={() => {
                setShowLoginModal(false);
                window.location.reload();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-text)] text-xl">Loading...</div>
      </div>
    }>
      <ChatPageContent />
    </Suspense>
  );
}
