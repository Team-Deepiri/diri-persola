import React, { useState, useEffect, useRef } from 'react';
import { agentsApi } from '../../api';
import type { AgentConfig, InvokeRequest, InvokeResponse } from '../../types';
import './AgentPlayground.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface Session {
  id: string;
  name: string;
}

export const AgentPlayground: React.FC = () => {
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentConfig | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadAgents = async () => {
    try {
      const response = await agentsApi.list();
      setAgents(response.data);
      if (response.data.length > 0) {
        setSelectedAgent(response.data[0]);
      }
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!currentMessage.trim() || !selectedAgent || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: currentMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsLoading(true);

    try {
      const request: InvokeRequest = {
        message: currentMessage,
        history: messages.map(msg => ({
          role: msg.role,
          content: msg.content,
        })),
      };

      const response = await agentsApi.invoke(selectedAgent.agent_id, request);
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (error) {
      console.error('Failed to invoke agent:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error while processing your message.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearConversation = () => {
    setMessages([]);
  };

  return (
    <div className="agent-playground">
      <div className="playground-header">
        <h2>Agent Playground</h2>
        <div className="playground-controls">
          <select
            value={selectedAgent?.agent_id || ''}
            onChange={(e) => {
              const agent = agents.find(a => a.agent_id === e.target.value);
              setSelectedAgent(agent || null);
            }}
            className="agent-select"
          >
            <option value="">Select an agent...</option>
            {agents.map(agent => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name} ({agent.role})
              </option>
            ))}
          </select>
          <button
            onClick={clearConversation}
            className="clear-button"
            disabled={messages.length === 0}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Select an agent and start a conversation!</p>
            </div>
          ) : (
            messages.map(message => (
              <div
                key={message.id}
                className={`message ${message.role}`}
              >
                <div className="message-avatar">
                  {message.role === 'user' ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                  <div className="message-text">{message.content}</div>
                  <div className="message-time">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="message assistant">
              <div className="message-avatar">🤖</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="message-input-container">
          <textarea
            value={currentMessage}
            onChange={(e) => setCurrentMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="message-input"
            rows={3}
            disabled={!selectedAgent || isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={!currentMessage.trim() || !selectedAgent || isLoading}
            className="send-button"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};