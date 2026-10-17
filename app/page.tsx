'use client';

import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { EnhancedNeuralCore } from '@/components/EnhancedNeuralCore';
import { useState, useEffect } from 'react';

type State = 'idle' | 'listening' | 'thinking' | 'speaking';

export default function HomePage() {
  const [demoState, setDemoState] = useState<State>('idle');
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState<string | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const runDemo = () => {
    setDemoState('listening');
    setTimeout(() => setDemoState('thinking'), 2000);
    setTimeout(() => setDemoState('speaking'), 3500);
    setTimeout(() => setDemoState('idle'), 5500);
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

      {/* Mouse Trail Effect */}
      <motion.div
        className="fixed w-96 h-96 rounded-full pointer-events-none z-0"
        style={{
          background: 'radial-gradient(circle, rgba(37, 230, 247, 0.15) 0%, transparent 70%)',
          left: mousePos.x - 192,
          top: mousePos.y - 192,
        }}
        animate={{
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
        }}
      />

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

      {/* Advanced Navigation Bar */}
      <motion.header 
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ type: 'spring', stiffness: 100 }}
        className="sticky top-0 z-50 bg-neural/95 backdrop-blur-xl border-b border-cyan/30 shadow-lg"
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


      {/* Hero Section - Advanced Terminal & Neural Core */}
      <section className="py-20 relative">
        <div className="container mx-auto px-6">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Advanced Terminal Card */}
            <motion.div
              initial={{ opacity: 0, x: -100, rotateY: -15 }}
              animate={{ opacity: 1, x: 0, rotateY: 0 }}
              transition={{ type: 'spring', stiffness: 60, damping: 15 }}
              className="relative group"
            >
              {/* Glowing Border Effect */}
              <div className="absolute -inset-1 bg-gradient-to-r from-cyan via-electric to-purple-500 rounded-2xl opacity-50 blur-lg group-hover:opacity-75 transition-opacity duration-500"></div>
              
              <div className="relative bg-gradient-to-br from-terminal via-neural to-terminal border border-cyan/30 rounded-2xl p-8 shadow-2xl backdrop-blur-sm">
                {/* Terminal Header */}
                <div className="flex gap-2 mb-6">
                  {['red', 'yellow', 'green'].map((color, i) => (
                    <motion.div
                      key={color}
                      className={`w-4 h-4 rounded-full bg-${color}-500`}
                      whileHover={{ scale: 1.3, rotate: 180 }}
                      animate={{
                        boxShadow: [
                          `0 0 5px var(--color-${color})`,
                          `0 0 15px var(--color-${color})`,
                          `0 0 5px var(--color-${color})`
                        ]
                      }}
                      transition={{ duration: 2, repeat: Infinity, delay: i * 0.3 }}
                    />
                  ))}
                </div>

                {/* Title with Glitch Effect */}
                <motion.div 
                  className="mb-8"
                  whileHover={{ scale: 1.02 }}
                >
                  <motion.h1 
                    className="text-5xl font-bold text-cyan mb-3 drop-shadow-[0_0_20px_rgba(37,230,247,0.8)]"
                    animate={{
                      textShadow: [
                        '0 0 20px rgba(37,230,247,0.8)',
                        '0 0 30px rgba(37,230,247,1)',
                        '0 0 20px rgba(37,230,247,0.8)'
                      ]
                    }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    XAIREX
                  </motion.h1>
                  <p className="text-gray-300 text-lg uppercase tracking-wider">
                    OFFLINE NEURAL VOICE ASSISTANT
                  </p>
                  <motion.div
                    className="flex items-center gap-2 mt-3"
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-green-400 text-sm font-bold">SYSTEM READY</span>
                  </motion.div>
                </motion.div>

                {/* Feature List with Animated Icons */}
                <div className="space-y-3 mb-8">
                  {[
                    { icon: '▶', text: 'Local speech-to-text (Whisper)', delay: 0 },
                    { icon: '◆', text: 'Local LLM brain (Ollama)', delay: 0.1 },
                    { icon: '♦', text: 'Local text-to-speech (Piper)', delay: 0.2 },
                    { icon: '⚡', text: '23 OS integration tools', delay: 0.3 },
                    { icon: '●', text: 'Zero cloud dependencies', delay: 0.4 },
                  ].map((item, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: item.delay + 0.5 }}
                      whileHover={{ x: 10, scale: 1.02 }}
                      className="flex items-center gap-3 text-gray-400 hover:text-cyan transition-colors cursor-pointer group/item"
                    >
                      <motion.span
                        animate={{ scale: [1, 1.2, 1] }}
                        transition={{ duration: 2, repeat: Infinity, delay: i * 0.2 }}
                        className="text-2xl text-cyan"
                      >
                        {item.icon}
                      </motion.span>
                      <span className="group-hover/item:translate-x-2 transition-transform">
                        → {item.text}
                      </span>
                    </motion.div>
                  ))}
                </div>

                {/* Animated Metrics Dashboard */}
                <motion.div
                  className="pt-6 border-t border-cyan/30"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1 }}
                >
                  <p className="text-xs text-gray-600 mb-4 uppercase tracking-widest">RUNTIME METRICS</p>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { label: 'CPU', value: 'i5-13420H', color: 'cyan' },
                      { label: 'RAM', value: '15.7 GB', color: 'electric' },
                      { label: 'Response', value: '~1s warm', color: 'green' },
                      { label: 'Status', value: 'READY', color: 'green' },
                    ].map((metric, i) => (
                      <motion.div
                        key={i}
                        className="bg-neural/50 rounded-lg p-3 border border-cyan/20"
                        whileHover={{ scale: 1.05, borderColor: 'rgba(37, 230, 247, 0.5)' }}
                      >
                        <div className="text-xs text-gray-500 mb-1">{metric.label}</div>
                        <div className={`text-sm font-mono font-bold text-${metric.color}-400`}>
                          {metric.value}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>

                {/* Interactive Command Line */}
                <motion.div 
                  className="mt-6 pt-4 border-t border-cyan/30"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1.2 }}
                >
                  <div className="flex items-center gap-3 bg-neural/70 rounded-lg p-4 border border-cyan/20 hover:border-cyan/40 transition-colors">
                    <span className="text-cyan font-bold">$</span>
                    <input
                      type="text"
                      placeholder="Type a command or 'talk' to speak..."
                      className="flex-1 bg-transparent border-none outline-none text-cyan placeholder-gray-600 font-mono"
                    />
                    <motion.span
                      animate={{ opacity: [0, 1, 0] }}
                      transition={{ duration: 1, repeat: Infinity }}
                      className="text-cyan text-xl font-bold"
                    >
                      |
                    </motion.span>
                  </div>
                </motion.div>
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

              <EnhancedNeuralCore state={demoState} />
              
              {/* Advanced Action Buttons */}
              <div className="mt-16 flex flex-wrap gap-4 justify-center">
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
                  icon: '■',
                  title: '100% Private',
                  desc: 'No data leaves your machine. Ever.',
                  color: 'green',
                },
                {
                  icon: '▲',
                  title: 'Lightning Fast',
                  desc: 'Sub-second responses on CPU.',
                  color: 'yellow',
                },
                {
                  icon: '◆',
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
                    className={`text-5xl mb-4 text-${feature.color}-400 font-bold`}
                    animate={{ scale: [1, 1.2, 1] }}
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
