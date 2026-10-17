'use client';

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

interface EnhancedNeuralCoreProps {
  state?: 'idle' | 'listening' | 'thinking' | 'speaking';
}

export function EnhancedNeuralCore({ state = 'idle' }: EnhancedNeuralCoreProps) {
  const [audioLevels, setAudioLevels] = useState<number[]>(Array(12).fill(0.3));

  // Simulate audio levels when speaking
  useEffect(() => {
    if (state === 'speaking') {
      const interval = setInterval(() => {
        setAudioLevels(Array(12).fill(0).map(() => Math.random() * 0.8 + 0.2));
      }, 100);
      return () => clearInterval(interval);
    } else {
      setAudioLevels(Array(12).fill(0.3));
    }
  }, [state]);

  const stateColors = {
    idle: '#25E6F7',
    listening: '#10B981',
    thinking: '#F59E0B',
    speaking: '#8B5CF6'
  };

  const stateLabels = {
    idle: 'IDLE — READY',
    listening: 'LISTENING...',
    thinking: 'PROCESSING...',
    speaking: 'SPEAKING...'
  };

  const currentColor = stateColors[state];
  const currentLabel = stateLabels[state];

  return (
    <div className="relative w-[450px] h-[450px] flex items-center justify-center">
      {/* Outer glow ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, transparent 60%, ${currentColor}15 100%)`
        }}
        animate={{
          opacity: state === 'idle' ? 0.3 : 0.8,
          scale: state === 'idle' ? 1 : [1, 1.05, 1]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: 'easeInOut'
        }}
      />

      {/* Outer ring - 60 tick marks */}
      <motion.div
        className="absolute inset-0 rounded-full border"
        style={{ borderColor: `${currentColor}30` }}
        animate={{ rotate: state === 'thinking' ? 360 : 360 }}
        transition={{
          duration: state === 'thinking' ? 15 : 30,
          repeat: Infinity,
          ease: 'linear'
        }}
      >
        {Array.from({ length: 60 }).map((_, i) => (
          <motion.div
            key={i}
            className="absolute top-0 left-1/2 w-px"
            style={{
              height: i % 5 === 0 ? '12px' : '8px',
              backgroundColor: i % 5 === 0 ? `${currentColor}80` : `${currentColor}40`,
              transformOrigin: '0 225px',
              transform: `rotate(${i * 6}deg)`,
            }}
            animate={{
              opacity: state === 'listening' && i % 12 === Math.floor(Date.now() / 100) % 12 ? 1 : 0.6
            }}
          />
        ))}
      </motion.div>

      {/* Middle ring - 12 scale markers with audio bars */}
      <motion.div
        className="absolute inset-12 rounded-full border"
        style={{ borderColor: `${currentColor}50` }}
        animate={{ rotate: state === 'thinking' ? -360 : -360 }}
        transition={{
          duration: state === 'thinking' ? 30 : 45,
          repeat: Infinity,
          ease: 'linear'
        }}
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <motion.div
            key={i}
            className="absolute top-0 left-1/2"
            style={{
              transformOrigin: '0 201px',
              transform: `rotate(${i * 30}deg)`,
            }}
          >
            {/* Audio bar effect */}
            <motion.div
              className="w-1 bg-gradient-to-t rounded-full"
              style={{
                backgroundImage: `linear-gradient(to top, ${currentColor}, transparent)`,
                height: `${16 + audioLevels[i] * 20}px`
              }}
              animate={{
                opacity: state === 'speaking' ? 0.9 : 0.4,
                scaleY: state === 'speaking' ? audioLevels[i] + 0.5 : 1
              }}
              transition={{ duration: 0.1 }}
            />
          </motion.div>
        ))}
      </motion.div>

      {/* Rotating orbital particles */}
      {state !== 'idle' && (
        <>
          {Array.from({ length: 3 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-2 h-2 rounded-full"
              style={{
                backgroundColor: currentColor,
                boxShadow: `0 0 10px ${currentColor}`
              }}
              animate={{
                rotate: 360,
                x: [0, 100 * Math.cos(i * 120 * Math.PI / 180), 0],
                y: [0, 100 * Math.sin(i * 120 * Math.PI / 180), 0]
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                delay: i * 0.4,
                ease: 'easeInOut'
              }}
            />
          ))}
        </>
      )}

      {/* Inner hexagon */}
      <motion.div
        className="absolute inset-24 flex items-center justify-center"
        animate={{ rotate: state === 'thinking' ? 360 : 0 }}
        transition={{
          duration: 8,
          repeat: Infinity,
          ease: 'linear'
        }}
      >
        <svg width="200" height="200" viewBox="0 0 200 200">
          <polygon
            points="100,20 170,60 170,140 100,180 30,140 30,60"
            fill="none"
            stroke={currentColor}
            strokeWidth="2"
            opacity="0.4"
          />
          <polygon
            points="100,40 150,70 150,130 100,160 50,130 50,70"
            fill="none"
            stroke={currentColor}
            strokeWidth="2"
            opacity="0.6"
          />
        </svg>
      </motion.div>

      {/* Center core */}
      <motion.div
        className="absolute w-16 h-16 rounded-full border-2 flex items-center justify-center"
        style={{
          borderColor: currentColor,
          backgroundColor: `${currentColor}10`,
          boxShadow: `0 0 30px ${currentColor}40`
        }}
        animate={{
          scale: state === 'idle' ? [1, 1.1, 1] : [1, 1.2, 1],
          opacity: [0.7, 1, 0.7]
        }}
        transition={{
          duration: state === 'idle' ? 2.5 : 1.5,
          repeat: Infinity
        }}
      >
        <motion.div
          className="w-6 h-6 rounded-full"
          style={{
            backgroundColor: currentColor,
            boxShadow: `0 0 20px ${currentColor}`
          }}
          animate={{
            opacity: [0.8, 1, 0.8]
          }}
          transition={{
            duration: 1,
            repeat: Infinity
          }}
        />
      </motion.div>

      {/* Scanning radial line */}
      <motion.svg
        className="absolute inset-0 pointer-events-none"
        viewBox="0 0 450 450"
        animate={{ rotate: 360 }}
        transition={{
          duration: state === 'listening' ? 6 : 12,
          repeat: Infinity,
          ease: state === 'listening' ? 'linear' : 'easeInOut'
        }}
      >
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={currentColor} stopOpacity="0" />
            <stop offset="100%" stopColor={currentColor} stopOpacity="0.8" />
          </linearGradient>
        </defs>
        <line
          x1="225"
          y1="225"
          x2="350"
          y2="225"
          stroke="url(#lineGradient)"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </motion.svg>

      {/* Data points */}
      {state === 'thinking' && (
        <div className="absolute inset-0">
          {Array.from({ length: 8 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 rounded-full"
              style={{
                backgroundColor: currentColor,
                top: '50%',
                left: '50%',
                boxShadow: `0 0 6px ${currentColor}`
              }}
              animate={{
                x: [0, (Math.random() - 0.5) * 300],
                y: [0, (Math.random() - 0.5) * 300],
                opacity: [0, 1, 0]
              }}
              transition={{
                duration: 2 + Math.random() * 2,
                repeat: Infinity,
                delay: i * 0.3
              }}
            />
          ))}
        </div>
      )}

      {/* State label */}
      <motion.div
        className="absolute -bottom-16 text-sm tracking-widest font-mono"
        style={{ color: currentColor }}
        animate={{
          opacity: [0.7, 1, 0.7]
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity
        }}
      >
        {currentLabel}
      </motion.div>

      {/* Metrics overlay */}
      <div className="absolute -bottom-32 w-full">
        <div className="flex justify-around text-xs">
          <div className="text-center">
            <div className="text-gray-600">LATENCY</div>
            <div className="text-cyan font-mono mt-1">
              {state === 'idle' ? '—' : state === 'listening' ? '210ms' : state === 'thinking' ? '607ms' : '185ms'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-600">CPU</div>
            <div className="text-green-400 font-mono mt-1">
              {state === 'idle' ? '8%' : state === 'thinking' ? '42%' : '24%'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-600">RAM</div>
            <div className="text-electric font-mono mt-1">2.8GB</div>
          </div>
        </div>
      </div>
    </div>
  );
}
