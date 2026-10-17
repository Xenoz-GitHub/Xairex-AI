'use client';

import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { EnhancedNeuralCore } from '@/components/EnhancedNeuralCore';
import { useState, useEffect } from 'react';

type State = 'idle' | 'listening' | 'thinking' | 'speaking';

export default function HomePage() {
  const [demoState, setDemoState] = useState<State>('idle');
  const [isHovering, setIsHovering] = useState<string | null>(null);
  const [typedText, setTypedText] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const demoConversations = [
    { user: "Hey Xairex, what's the time?", ai: "It's 8:47 PM. Need anything else?" },
    { user: "Open Notepad for me", ai: "Opening Notepad now." },
    { user: "Set volume to 50%", ai: "Volume set to 50%." },
    { user: "What's 144 divided by 12?", ai: "144 divided by 12 equals 12." },
  ];

  const [currentConvoIndex, setCurrentConvoIndex] = useState(0);

  useEffect(() => {
    // Auto-start demo after 2 seconds
    const autoStart = setTimeout(() => {
      runDemo();
    }, 2000);
    
    return () => clearTimeout(autoStart);
  }, []);

  const runDemo = () => {
    if (demoState !== 'idle') return;
    
    const conversation = demoConversations[currentConvoIndex];
    
    // Reset
    setTypedText('');
    setAiResponse('');
    setIsTyping(true);
    setDemoState('listening');
    
    // Type user message
    const userText = conversation.user;
    let charIndex = 0;
    const typeInterval = setInterval(() => {
      if (charIndex < userText.length) {
        setTypedText(userText.slice(0, charIndex + 1));
        charIndex++;
      } else {
        clearInterval(typeInterval);
        // Start AI processing
        setTimeout(() => {
          setDemoState('thinking');
          setTimeout(() => {
            setDemoState('speaking');
            // Type AI response
            const aiText = conversation.ai;
            let aiCharIndex = 0;
            const aiTypeInterval = setInterval(() => {
              if (aiCharIndex < aiText.length) {
                setAiResponse(aiText.slice(0, aiCharIndex + 1));
                aiCharIndex++;
              } else {
                clearInterval(aiTypeInterval);
                setTimeout(() => {
                  setDemoState('idle');
                  setIsTyping(false);
                  // Move to next conversation and auto-restart
                  setCurrentConvoIndex((prev) => (prev + 1) % demoConversations.length);
                  setTimeout(() => {
                    runDemo();
                  }, 3000);
                }, 2000);
              }
            }, 40);
          }, 1000);
        }, 600);
      }
    }, 60);
  };

  return (
    <main className="min-h-screen relative overflow-hidden">
      {/* Animated Background Grid */}
      <div className="fixed inset-0 pointer-events-none opacity-20">
        <div className="absolute inset-0" style={{
          backgroundImage: `
            linear-gradient(rgba(37, 230, 247, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37, 230, 247, 0.1) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
          animation: 'grid-move 20s linear infinite'
        }}></div>
      </div>

      {/* Professional Banner Section */}
      <div className="relative w-full h-[400px] overflow-hidden border-b border-cyan/30 shadow-2xl">
        <motion.div
          initial={{ scale: 1.2, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.5 }}
          className="absolute inset-0"
        >
          <img 
            src="/banner.png" 
            alt="Xairex AI Banner" 
            className="w-full h-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-neural/50 to-neural"></div>
        </motion.div>
        
        {/* Scan Line Effect */}
        <motion.div
          className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-cyan to-transparent"
          animate={{
            top: ['-10%', '110%'],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* Banner Content */}
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            className="text-center"
          >
            <motion.img 
              src="/iconxairex.png" 
              alt="Xairex Icon" 
              className="w-24 h-24 mx-auto mb-6"
              animate={{
                rotateY: [0, 360],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: 'linear',
              }}
            />
            <h1 className="text-6xl font-bold text-cyan mb-4 drop-shadow-[0_0_25px_rgba(37,230,247,0.8)]">
              XAIREX AI
            </h1>
            <p className="text-2xl text-gray-300 mb-2">OFFLINE NEURAL VOICE ASSISTANT</p>
            <div className="flex gap-3 justify-center items-center text-sm">
              <motion.span 
                className="px-3 py-1 bg-green-500/20 border border-green-400 text-green-400 rounded-full"
                animate={{ boxShadow: ['0 0 10px rgba(74, 222, 128, 0.3)', '0 0 20px rgba(74, 222, 128, 0.5)', '0 0 10px rgba(74, 222, 128, 0.3)'] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                ● SYSTEM ONLINE
              </motion.span>
              <span className="text-gray-500">|</span>
              <span className="text-gray-400">v0.1.0</span>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Advanced Navigation Bar - STICKY */}
      <motion.header 
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ type: 'spring', stiffness: 100 }}
        className="fixed top-0 left-0 right-0 z-50 bg-neural/95 backdrop-blur-xl border-b border-cyan/30 shadow-lg"
      >
        <div className="container mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <motion.div 
              className="flex items-center gap-3"
              whileHover={{ scale: 1.05 }}
            >
              <img src="/iconxairex.png" alt="Xairex" className="w-8 h-8" />
              <span className="text-xl font-bold bg-gradient-to-r from-cyan via-electric to-cyan bg-clip-text text-transparent">
                XAIREX
              </span>
            </motion.div>
            
            <nav className="hidden md:flex gap-2">
              {['Features', 'CLI', 'About'].map((item) => (
                <motion.div
                  key={item}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onHoverStart={() => setIsHovering(item)}
                  onHoverEnd={() => setIsHovering(null)}
                >
                  <Link 
                    href={`/${item.toLowerCase()}`}
                    className="relative px-5 py-2 text-sm font-medium text-gray-300 hover:text-cyan transition-colors"
                  >
                    {item}
                    {isHovering === item && (
                      <motion.div
                        layoutId="navbar-indicator"
                        className="absolute inset-0 bg-cyan/10 border border-cyan/50 rounded-lg -z-10"
                        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                      />
                    )}
                  </Link>
                </motion.div>
              ))}
              
              <motion.a
                href="https://github.com/Xenoz-GitHub/Xairex-AI"
                target="_blank"
                whileHover={{ scale: 1.05, boxShadow: '0 0 20px rgba(37, 230, 247, 0.5)' }}
                whileTap={{ scale: 0.95 }}
                className="px-5 py-2 bg-gradient-to-r from-cyan to-electric text-neural font-bold rounded-lg text-sm relative overflow-hidden"
              >
                <motion.div
                  className="absolute inset-0 bg-white/20"
                  animate={{
                    x: ['-100%', '100%'],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: 'linear',
                  }}
                />
                <span className="relative z-10">GitHub</span>
              </motion.a>
            </nav>

            <div className="hidden lg:flex gap-2 text-xs">
              {[
                { label: 'OFFLINE', color: 'green' },
                { label: 'CPU-ONLY', color: 'electric' },
                { label: 'NO CLOUD', color: 'purple' },
              ].map((badge) => (
                <motion.span
                  key={badge.label}
                  whileHover={{ scale: 1.1, y: -2 }}
                  className={`px-3 py-1.5 border ${
                    badge.color === 'green' ? 'border-green-400 text-green-400 bg-green-400/10' :
                    badge.color === 'electric' ? 'border-electric text-electric bg-electric/10' :
                    'border-purple-400 text-purple-400 bg-purple-400/10'
                  } rounded-full font-semibold backdrop-blur`}
                >
                  {badge.label}
                </motion.span>
              ))}
            </div>
          </div>
        </div>
      </motion.header>


      {/* Hero Section - Realistic Xairex GUI Simulation */}
      <section className="py-20 relative">
        <div className="container mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16 items-start">
            {/* Realistic Xairex GUI Window */}
            <motion.div
              initial={{ opacity: 0, x: -100 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: 'spring', stiffness: 60, damping: 15 }}
              className="relative group"
            >
              {/* Window Shadow */}
              <div className="absolute -inset-1 bg-gradient-to-r from-cyan via-electric to-purple-500 rounded-2xl opacity-50 blur-lg group-hover:opacity-75 transition-opacity duration-500"></div>
              
              {/* Main Window */}
              <div className="relative bg-gradient-to-br from-[#0C1622] via-[#050A0F] to-[#0C1622] border-2 border-cyan/30 rounded-2xl shadow-2xl overflow-hidden">
                {/* Window Title Bar */}
                <div className="bg-gradient-to-r from-cyan/20 to-electric/20 border-b border-cyan/30 px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-2">
                      <motion.div className="w-3 h-3 rounded-full bg-red-500" whileHover={{ scale: 1.3 }} />
                      <motion.div className="w-3 h-3 rounded-full bg-yellow-500" whileHover={{ scale: 1.3 }} />
                      <motion.div className="w-3 h-3 rounded-full bg-green-500" whileHover={{ scale: 1.3 }} />
                    </div>
                    <span className="text-cyan font-bold text-sm">XAIREX AI v0.1.0</span>
                  </div>
                  <motion.div
                    className="flex items-center gap-2 text-xs"
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    <span className="text-green-400 font-bold">ONLINE</span>
                  </motion.div>
                </div>

                {/* Status Bar */}
                <div className="bg-neural/80 border-b border-cyan/20 px-4 py-2 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-4">
                    <span className="text-gray-500">Model:</span>
                    <span className="text-cyan font-mono">xairex-fast</span>
                    <span className="text-gray-600">|</span>
                    <span className="text-gray-500">Voice:</span>
                    <span className="text-cyan font-mono">amy</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <motion.div
                      className={`px-2 py-1 rounded text-xs font-bold ${
                        demoState === 'listening' ? 'bg-green-500/20 text-green-400 border border-green-400' :
                        demoState === 'thinking' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-400' :
                        demoState === 'speaking' ? 'bg-purple-500/20 text-purple-400 border border-purple-400' :
                        'bg-cyan/20 text-cyan border border-cyan'
                      }`}
                      animate={{ scale: demoState !== 'idle' ? [1, 1.05, 1] : 1 }}
                      transition={{ duration: 0.5, repeat: demoState !== 'idle' ? Infinity : 0 }}
                    >
                      {demoState === 'listening' ? 'LISTENING' :
                       demoState === 'thinking' ? 'THINKING' :
                       demoState === 'speaking' ? 'SPEAKING' :
                       'READY'}
                    </motion.div>
                  </div>
                </div>

                {/* Chat Transcript Area */}
                <div className="bg-[#050A0F] p-6 h-[400px] overflow-y-auto custom-scrollbar">
                  <div className="space-y-4">
                    {/* Welcome Message */}
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex items-start gap-3"
                    >
                      <div className="w-8 h-8 rounded-full bg-cyan/20 border border-cyan flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-cyan" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                          <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-cyan font-bold text-sm">XAIREX</span>
                          <span className="text-xs text-gray-600">system</span>
                        </div>
                        <p className="text-gray-400 text-sm">
                          Hello! I'm Xairex, your offline AI assistant. Try asking me something!
                        </p>
                      </div>
                    </motion.div>

                    {/* User Message (Typed) */}
                    <AnimatePresence>
                      {typedText && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="flex items-start gap-3"
                        >
                          <div className="w-8 h-8 rounded-full bg-electric/20 border border-electric flex items-center justify-center flex-shrink-0">
                            <svg className="w-4 h-4 text-electric" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd"/>
                            </svg>
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-electric font-bold text-sm">You</span>
                              <span className="text-xs text-gray-600">voice</span>
                            </div>
                            <p className="text-gray-300 text-sm">
                              {typedText}
                              {isTyping && demoState === 'listening' && (
                                <motion.span
                                  animate={{ opacity: [0, 1, 0] }}
                                  transition={{ duration: 0.5, repeat: Infinity }}
                                  className="text-electric"
                                >
                                  |
                                </motion.span>
                              )}
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* AI Response (Typed) */}
                    <AnimatePresence>
                      {aiResponse && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="flex items-start gap-3"
                        >
                          <div className="w-8 h-8 rounded-full bg-cyan/20 border border-cyan flex items-center justify-center flex-shrink-0">
                            <svg className="w-4 h-4 text-cyan" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                              <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
                            </svg>
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-cyan font-bold text-sm">XAIREX</span>
                              <span className="text-xs text-gray-600">{
                                demoState === 'thinking' ? 'processing...' :
                                demoState === 'speaking' ? 'speaking' : 'response'
                              }</span>
                            </div>
                            <p className="text-gray-300 text-sm">
                              {aiResponse}
                              {demoState === 'speaking' && (
                                <motion.span
                                  animate={{ opacity: [0, 1, 0] }}
                                  transition={{ duration: 0.5, repeat: Infinity }}
                                  className="text-cyan"
                                >
                                  |
                                </motion.span>
                              )}
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Input Area */}
                <div className="bg-neural/80 border-t border-cyan/30 p-4">
                  <div className="flex items-center gap-3 bg-[#050A0F] rounded-lg px-4 py-3 border border-cyan/20">
                    <svg className="w-5 h-5 text-gray-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd"/>
                    </svg>
                    <input
                      type="text"
                      placeholder={isTyping ? "Processing..." : "Type a message or press TALK..."}
                      disabled={isTyping}
                      className="flex-1 bg-transparent border-none outline-none text-gray-400 placeholder-gray-600 text-sm font-mono"
                    />
                    {!isTyping && (
                      <motion.span
                        animate={{ opacity: [0, 1, 0] }}
                        transition={{ duration: 1, repeat: Infinity }}
                        className="text-cyan"
                      >
                        |
                      </motion.span>
                    )}
                  </div>
                </div>

                {/* Footer Metrics */}
                <div className="bg-gradient-to-r from-cyan/10 to-electric/10 border-t border-cyan/20 px-4 py-2">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-600">●</span>
                        <span className="text-gray-500">Bridge:</span>
                        <span className="text-green-400">Connected</span>
                      </div>
                      <div className="text-gray-600">|</div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-500">Tools:</span>
                        <span className="text-cyan">23 ready</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {demoState !== 'idle' && (
                        <>
                          <span className="text-gray-500">Response:</span>
                          <span className="text-yellow-400 font-mono">
                            {demoState === 'thinking' ? '607ms' : demoState === 'speaking' ? '890ms' : '—'}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Enhanced Neural Core with 3D Effect */}
            <motion.div
              initial={{ opacity: 0, x: 100, rotateY: 15 }}
              animate={{ opacity: 1, x: 0, rotateY: 0 }}
              transition={{ type: 'spring', stiffness: 60, damping: 15, delay: 0.2 }}
              className="flex flex-col items-center relative"
            >
              {/* Floating Particles Around Core */}
              {Array.from({ length: 20 }).map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-1 h-1 bg-cyan rounded-full"
                  style={{
                    left: `${Math.random() * 100}%`,
                    top: `${Math.random() * 100}%`,
                  }}
                  animate={{
                    y: [0, -30, 0],
                    opacity: [0, 1, 0],
                  }}
                  transition={{
                    duration: 2 + Math.random() * 2,
                    repeat: Infinity,
                    delay: Math.random() * 2,
                  }}
                />
              ))}

              <div className="relative z-10">
                <EnhancedNeuralCore state={demoState} />
              </div>
              
              {/* Advanced Action Buttons */}
              <div className="mt-20 flex flex-wrap gap-4 justify-center relative z-10">
                <motion.button
                  onClick={runDemo}
                  disabled={demoState !== 'idle'}
                  whileHover={demoState === 'idle' ? { scale: 1.05, boxShadow: '0 0 30px rgba(74, 222, 128, 0.6)' } : {}}
                  whileTap={demoState === 'idle' ? { scale: 0.95 } : {}}
                  className={`relative px-8 py-4 font-bold rounded-xl transition-all duration-300 overflow-hidden ${
                    demoState !== 'idle'
                      ? 'bg-gray-800 border-2 border-gray-700 text-gray-600 cursor-not-allowed'
                      : 'bg-gradient-to-r from-green-500 to-emerald-500 border-2 border-green-400 text-white shadow-lg'
                  }`}
                >
                  {demoState !== 'idle' && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                  )}
                  <span className="relative z-10 flex items-center gap-2">
                    {demoState === 'idle' ? '▶ RUN ANIMATION' : `◈ ${demoState.toUpperCase()}`}
                  </span>
                </motion.button>
                
                <Link href="/features">
                  <motion.button
                    whileHover={{ scale: 1.05, boxShadow: '0 0 30px rgba(37, 230, 247, 0.6)' }}
                    whileTap={{ scale: 0.95 }}
                    className="relative px-8 py-4 bg-gradient-to-r from-cyan to-electric border-2 border-cyan text-white font-bold rounded-xl overflow-hidden shadow-lg"
                  >
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                    <span className="relative z-10">▸ VIEW FEATURES</span>
                  </motion.button>
                </Link>
              </div>
            </motion.div>
          </div>
        </div>
      </section>


      {/* Advanced CTA Section */}
      <section className="py-32 relative border-t border-cyan/30 overflow-hidden" id="about">
        {/* Animated Background Shapes */}
        <div className="absolute inset-0 overflow-hidden">
          {Array.from({ length: 5 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-64 h-64 rounded-full"
              style={{
                background: `radial-gradient(circle, ${i % 2 === 0 ? 'rgba(37, 230, 247, 0.1)' : 'rgba(14, 165, 233, 0.1)'}, transparent)`,
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
              }}
              animate={{
                x: [0, Math.random() * 100 - 50],
                y: [0, Math.random() * 100 - 50],
                scale: [1, 1.2, 1],
              }}
              transition={{
                duration: 10 + i * 2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>

        <div className="container mx-auto px-6 text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <motion.h2 
              className="text-5xl font-bold bg-gradient-to-r from-cyan via-electric to-purple-500 bg-clip-text text-transparent mb-6"
              animate={{
                backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
              }}
              transition={{
                duration: 5,
                repeat: Infinity,
                ease: 'linear',
              }}
              style={{
                backgroundSize: '200% 200%',
              }}
            >
              Ready to Install?
            </motion.h2>
            
            <motion.p 
              className="text-gray-300 text-xl mb-12 max-w-3xl mx-auto leading-relaxed"
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
            >
              One command. Fully offline. Zero cloud. Your personal AI assistant running entirely on your machine.
              <br />
              <span className="text-cyan font-bold">23 powerful tools</span> at your voice command.
            </motion.p>

            <div className="flex gap-6 justify-center flex-wrap mb-12">
              <Link href="/cli">
                <motion.button
                  whileHover={{ scale: 1.05, y: -5 }}
                  whileTap={{ scale: 0.95 }}
                  className="relative px-12 py-5 bg-gradient-to-r from-cyan via-electric to-cyan text-neural font-bold text-lg rounded-xl overflow-hidden shadow-2xl group"
                  style={{
                    backgroundSize: '200% 100%',
                  }}
                  animate={{
                    backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
                  }}
                  transition={{
                    backgroundPosition: {
                      duration: 3,
                      repeat: Infinity,
                      ease: 'linear',
                    },
                  }}
                >
                  <motion.div
                    className="absolute inset-0 bg-white/20"
                    animate={{
                      x: ['-100%', '200%'],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: 'linear',
                    }}
                  />
                  <span className="relative z-10 flex items-center gap-3">
                    <span className="text-2xl">⚡</span>
                    Install Now
                    <span>→</span>
                  </span>
                </motion.button>
              </Link>
              
              <motion.a
                href="https://github.com/Xenoz-GitHub/Xairex-AI"
                target="_blank"
                whileHover={{ scale: 1.05, y: -5 }}
                whileTap={{ scale: 0.95 }}
              >
                <motion.button
                  className="relative px-12 py-5 bg-transparent border-2 border-cyan text-cyan font-bold text-lg rounded-xl overflow-hidden group"
                  whileHover={{
                    boxShadow: '0 0 40px rgba(37, 230, 247, 0.6)',
                    borderColor: 'rgba(14, 165, 233, 1)',
                  }}
                >
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-r from-cyan/0 via-cyan/20 to-cyan/0"
                    initial={{ x: '-100%' }}
                    whileHover={{ x: '100%' }}
                    transition={{ duration: 0.6 }}
                  />
                  <span className="relative z-10 flex items-center gap-3">
                    <span className="text-xl">★</span>
                    View Source
                    <span>→</span>
                  </span>
                </motion.button>
              </motion.a>
            </div>

            {/* Feature Highlights Grid */}
            <motion.div
              className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
            >
              {[
                {
                  icon: <svg className="w-10 h-10" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd"/></svg>,
                  title: '100% Private',
                  desc: 'No data leaves your machine. Ever.',
                  color: 'green',
                },
                {
                  icon: <svg className="w-10 h-10" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd"/></svg>,
                  title: 'Lightning Fast',
                  desc: 'Sub-second responses on CPU.',
                  color: 'yellow',
                },
                {
                  icon: <svg className="w-10 h-10" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M6 6V5a3 3 0 013-3h2a3 3 0 013 3v1h2a2 2 0 012 2v3.57A22.952 22.952 0 0110 13a22.95 22.95 0 01-8-1.43V8a2 2 0 012-2h2zm2-1a1 1 0 011-1h2a1 1 0 011 1v1H8V5zm1 5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd"/><path d="M2 13.692V16a2 2 0 002 2h12a2 2 0 002-2v-2.308A24.974 24.974 0 0110 15c-2.796 0-5.487-.46-8-1.308z"/></svg>,
                  title: '23 Tools',
                  desc: 'System control, browser, files, and more.',
                  color: 'cyan',
                },
              ].map((feature, i) => (
                <motion.div
                  key={i}
                  className="bg-terminal/50 backdrop-blur border border-cyan/20 rounded-2xl p-6 hover:border-cyan/50 transition-all group"
                  whileHover={{ scale: 1.05, y: -10 }}
                  transition={{ type: 'spring', stiffness: 300 }}
                >
                  <motion.div
                    className={`text-${feature.color}-400 mb-4 flex justify-center`}
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 3, repeat: Infinity, delay: i * 0.2 }}
                  >
                    {feature.icon}
                  </motion.div>
                  <h3 className={`text-xl font-bold text-${feature.color}-400 mb-2`}>
                    {feature.title}
                  </h3>
                  <p className="text-gray-400 text-sm">
                    {feature.desc}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Advanced Footer */}
      <footer className="py-16 border-t border-cyan/30 relative overflow-hidden">
        {/* Animated Binary Rain Background */}
        <div className="absolute inset-0 opacity-5 pointer-events-none">
          {Array.from({ length: 30 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute text-cyan font-mono text-xs"
              style={{
                left: `${(i * 100) / 30}%`,
              }}
              animate={{
                y: ['-100%', '100vh'],
              }}
              transition={{
                duration: 10 + Math.random() * 10,
                repeat: Infinity,
                ease: 'linear',
                delay: Math.random() * 5,
              }}
            >
              {Array.from({ length: 20 })
                .map(() => (Math.random() > 0.5 ? '1' : '0'))
                .join('\n')}
            </motion.div>
          ))}
        </div>

        <div className="container mx-auto px-6 relative z-10">
          <div className="flex flex-col items-center gap-6">
            {/* Logo */}
            <motion.div
              whileHover={{ scale: 1.1, rotate: 360 }}
              transition={{ duration: 0.8 }}
              className="w-16 h-16"
            >
              <img src="/iconxairex.png" alt="Xairex" className="w-full h-full" />
            </motion.div>

            {/* Brand */}
            <div className="text-center">
              <h3 className="text-2xl font-bold bg-gradient-to-r from-cyan to-electric bg-clip-text text-transparent mb-2">
                XAIREX AI
              </h3>
              <p className="text-gray-400 mb-4">Offline Neural Voice Assistant</p>
              <div className="flex gap-3 justify-center text-sm">
                <span className="text-green-400">● Fully offline</span>
                <span className="text-gray-600">|</span>
                <span className="text-electric">● CPU-only</span>
                <span className="text-gray-600">|</span>
                <span className="text-purple-400">● Zero cloud</span>
              </div>
            </div>

            {/* Links */}
            <div className="flex gap-6 text-sm">
              {[
                { label: 'Features', href: '/features' },
                { label: 'CLI', href: '/cli' },
                { label: 'Extension', href: '/extension' },
                { label: 'About', href: '/about' },
              ].map((link) => (
                <motion.div key={link.label} whileHover={{ y: -3 }}>
                  <Link
                    href={link.href}
                    className="text-gray-400 hover:text-cyan transition-colors"
                  >
                    {link.label}
                  </Link>
                </motion.div>
              ))}
            </div>

            {/* Social/GitHub */}
            <motion.a
              href="https://github.com/Xenoz-GitHub/Xairex-AI"
              target="_blank"
              whileHover={{ scale: 1.1 }}
              className="px-6 py-2 bg-terminal border border-cyan/30 rounded-full text-cyan hover:border-cyan transition-colors"
            >
              ★ Star on GitHub
            </motion.a>

            {/* Copyright */}
            <div className="text-center text-gray-500 text-sm mt-6">
              <p className="mb-1">Created by <span className="text-cyan font-bold">XenozExe</span></p>
              <p className="text-xs text-gray-600">
                © 2026 Xairex AI. Licensed under MIT. Privacy-first design.
              </p>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
