'use client';

import { motion } from 'framer-motion';

export function NeuralCore() {
  return (
    <div className="relative w-96 h-96 flex items-center justify-center">
      {/* Outer ring - 60 tick marks */}
      <motion.div
        className="absolute inset-0 rounded-full border border-cyan/30"
        animate={{ rotate: 360 }}
        transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
      >
        {Array.from({ length: 60 }).map((_, i) => (
          <div
            key={i}
            className="absolute top-0 left-1/2 h-2 w-px bg-cyan/50"
            style={{
              transformOrigin: '0 192px',
              transform: `rotate(${i * 6}deg)`,
            }}
          />
        ))}
      </motion.div>

      {/* Middle ring - 12 scale markers */}
      <motion.div
        className="absolute inset-8 rounded-full border border-electric/40"
        animate={{ rotate: -360 }}
        transition={{ duration: 45, repeat: Infinity, ease: 'linear' }}
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="absolute top-0 left-1/2 h-3 w-0.5 bg-electric/60"
            style={{
              transformOrigin: '0 176px',
              transform: `rotate(${i * 30}deg)`,
            }}
          />
        ))}
      </motion.div>

      {/* Inner circle */}
      <div className="absolute inset-16 rounded-full border border-cyan/50 shadow-lg shadow-cyan/20" />

      {/* Center point */}
      <motion.div
        className="absolute w-3 h-3 rounded-full bg-cyan shadow-lg shadow-cyan"
        animate={{ opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 2.5, repeat: Infinity }}
      />

      {/* Radial line */}
      <motion.svg
        className="absolute inset-0"
        viewBox="0 0 384 384"
        animate={{ rotate: 360 }}
        transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
      >
        <line
          x1="192"
          y1="192"
          x2="280"
          y2="192"
          stroke="#25E6F7"
          strokeWidth="2"
        />
      </motion.svg>

      {/* State label */}
      <div className="absolute -bottom-12 text-cyan text-sm tracking-widest">
        IDLE — READY
      </div>
    </div>
  );
}
