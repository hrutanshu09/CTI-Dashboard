import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, LoaderCircle } from 'lucide-react';
import { getAIResponse } from '../services/api'; // We will add this function next

const AIAssistantPage = () => {
  const [messages, setMessages] = useState([
    { sender: 'ai', text: 'Hello! How can I help you with your threat intelligence tasks today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const aiText = await getAIResponse(input);
      const aiMessage = { sender: 'ai', text: aiText };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      const errorMessage = { sender: 'ai', text: 'Sorry, I encountered an error. Please try again.' };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-6 bg-background">
      <h1 className="text-2xl font-bold text-white mb-4">AI Assistant</h1>
      
      <div className="flex-1 overflow-y-auto pr-4 space-y-6">
        {messages.map((msg, index) => (
          <div key={index} className={`flex items-start gap-4 ${msg.sender === 'user' ? 'justify-end' : ''}`}>
            {msg.sender === 'ai' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-neon-blue/20 flex items-center justify-center">
                <Bot className="w-5 h-5 text-neon-blue" />
              </div>
            )}
            <div className={`max-w-xl px-4 py-3 rounded-lg ${msg.sender === 'user' ? 'bg-blue-500/20' : 'bg-panel'}`}>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">{msg.text}</p>
            </div>
             {msg.sender === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
                <User className="w-5 h-5 text-gray-300" />
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="flex items-start gap-4">
             <div className="flex-shrink-0 w-8 h-8 rounded-full bg-neon-blue/20 flex items-center justify-center">
                <Bot className="w-5 h-5 text-neon-blue" />
              </div>
             <div className="max-w-xl px-4 py-3 rounded-lg bg-panel flex items-center">
                <LoaderCircle className="w-5 h-5 animate-spin text-gray-400" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="mt-6">
        <form onSubmit={handleSend} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about recent threats, CVEs, or IOCs..."
            className="w-full bg-panel border border-border rounded-lg pl-4 pr-12 py-3 text-white focus:outline-none focus:ring-2 focus:ring-neon-blue text-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-neon-blue text-black hover:bg-opacity-80 disabled:bg-gray-500 transition-colors"
            disabled={isLoading || !input.trim()}
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
};

export default AIAssistantPage;