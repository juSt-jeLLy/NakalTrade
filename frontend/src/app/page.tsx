'use client';

import { useState, useEffect, useRef } from 'react';
import { Wallet } from '@coinbase/onchainkit/wallet';
import { Address } from '@coinbase/onchainkit/identity';
import { useAccount } from 'wagmi';

type Message = {
  content: string;
  isUser: boolean;
  agentName?: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      content:
        'Welcome! I am the NakalTrade agent. I can analyze the historical performance of any wallet on a supported blockchain.<br/><br/>Try asking: <strong>analyze 0x... on eth</strong>',
      isUser: false,
      agentName: 'NakalTrade',
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { address, isConnected } = useAccount();

  const API_URL = 'http://localhost:8100/chat';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (input.trim() === '') return;

    const userMessage: Message = { content: input, isUser: true };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
      const data = await response.json();
      const agentResponse: Message = {
        content: data.response,
        isUser: false,
        agentName: 'NakalTrade',
      };
      setMessages((prev) => [...prev, agentResponse]);

    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = {
        content: '⚠️ Could not connect to the NakalTrade agent. Please ensure it is running.',
        isUser: false,
        agentName: 'NakalTrade',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-[#1a1a1a]">
      <div className="chat-container w-full max-w-3xl h-[90vh] max-h-[800px] bg-[#252525] rounded-xl border border-[#333] flex flex-col shadow-lg">
        <div className="chat-header p-5 bg-[#333] border-b border-[#444] rounded-t-xl flex justify-between items-center">
          <h1 className="text-2xl font-semibold text-white">NakalTrade Agent</h1>
          {isConnected ? <Address address={address as `0x${string}`} /> : <Wallet />}
        </div>
        <div className="chat-messages flex-1 p-5 overflow-y-auto">
          {messages.map((msg, index) => (
            <div key={index} className={`message mb-4 flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`message-content inline-block py-3 px-4 rounded-2xl max-w-[80%] break-words ${
                  msg.isUser ? 'bg-[#007aff] text-white' : 'bg-[#444] text-[#e0e0e0]'
                }`}
              >
                {!msg.isUser && <span className="agent-name font-bold block mb-1 text-[#007aff]">{msg.agentName}</span>}
                <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\n/g, '<br />') }} />
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        {isTyping && <div className="typing-indicator p-3 text-sm italic text-[#aaa]">NakalTrade is analyzing...</div>}
        <div className="chat-input-container p-5 border-t border-[#333]">
          <div className="flex gap-3">
            <input
              type="text"
              className="chat-input flex-1 py-3 px-4 bg-[#333] border border-[#555] rounded-full text-base text-white outline-none focus:border-[#007aff] transition-colors"
              placeholder="e.g., analyze 0x... on eth"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={isTyping}
            />
            <button
              className="send-button py-3 px-6 bg-[#007aff] text-white border-none rounded-full text-base font-semibold cursor-pointer transition-colors hover:bg-[#0056b3] disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleSendMessage}
              disabled={isTyping}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
