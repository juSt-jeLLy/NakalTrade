'use client';

import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
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
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '1rem',
      }}
    >
      <div
        className="nes-container with-title is-centered"
        style={{ width: '90vw', maxWidth: '1200px' }}
      >
        <Image
          src="/KnuckleNakal.png"
          alt="NakalTrade Logo"
          width={100}
          height={100}
          style={{ marginBottom: '1rem' }}
        />
        <p className="title">NakalTrade Agent</p>
        <div
          className="nes-container"
          style={{
            height: '65vh',
            overflowY: 'auto',
            marginBottom: '1rem',
            padding: '1rem',
          }}
        >
          <div className="messages">
            {messages.map((msg, index) => (
              <section
                key={index}
                className={`message -${msg.isUser ? 'right' : 'left'}`}
                style={{ 
                  maxWidth: '75%',
                  marginLeft: msg.isUser ? 'auto' : '0',
                  marginRight: msg.isUser ? '0' : 'auto',
                  display: 'block'
                }}
              >
                <div
                  className={`nes-balloon from-${
                    msg.isUser ? 'right' : 'left'
                  }`}
                  style={{
                    fontSize: '0.8rem',
                    lineHeight: '1.2'
                  }}
                  dangerouslySetInnerHTML={{
                    __html: `${
                      !msg.isUser
                        ? `<span class="nes-text is-primary" style="font-size: 0.75rem;">${msg.agentName}</span><br>`
                        : ''
                    }<span style="color: black;">${msg.content.replace(
                      /\n/g,
                      '<br />'
                    )}</span>`,
                  }}
                />
                {!msg.isUser && (
                  <p style={{ fontSize: '10px' }}>{msg.agentName}</p>
                )}
              </section>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>
        {isTyping && <p className="nes-text is-disabled" style={{ fontSize: '0.8rem' }}>NakalTrade is analyzing...</p>}
        <div className="nes-field is-inline">
          <input
            type="text"
            id="inline_field"
            className="nes-input"
            placeholder="e.g., analyze 0x... on eth"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            disabled={isTyping}
            style={{ fontSize: '0.85rem' }}
          />
          <button
            type="button"
            className={`nes-btn ${isTyping ? 'is-disabled' : 'is-primary'}`}
            onClick={handleSendMessage}
            disabled={isTyping}
            style={{ fontSize: '0.85rem' }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}