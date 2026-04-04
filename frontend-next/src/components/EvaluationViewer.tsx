"use client";
import React, { useState, useRef, useEffect } from 'react';

type BoundingBox = [number, number, number, number] | { ymin: number, xmin: number, ymax: number, xmax: number };

interface VisualAnnotation {
  text: string;
  issue_type: string;
  coordinates: BoundingBox;
  marking_style: string;
  suggestion: string;
}

interface EvaluationViewerProps {
  imageUrl: string;
  annotations: VisualAnnotation[];
}

const EvaluationViewer: React.FC<EvaluationViewerProps> = ({ imageUrl, annotations }) => {
  const [imgSize, setImgSize] = useState({ width: 0, height: 0 });
  const imgRef = useRef<HTMLImageElement>(null);

  const updateSize = () => {
    if (imgRef.current) {
      setImgSize({
        width: imgRef.current.clientWidth,
        height: imgRef.current.clientHeight
      });
    }
  };

  useEffect(() => {
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  const onImgLoad = () => {
    setTimeout(updateSize, 100); // Small delay to ensure layout is ready
  };

  return (
    <div className="relative inline-block w-full rounded-2xl overflow-hidden shadow-2xl bg-slate-100 border border-slate-200 dark:border-slate-800">
      <div className="absolute top-4 left-4 z-10 bg-black/50 backdrop-blur-md text-white text-xs px-3 py-1.5 rounded-full font-medium">
        Answer Sheet View
      </div>
      
      <img 
        ref={imgRef}
        src={imageUrl} 
        alt="Answer Sheet" 
        onLoad={onImgLoad}
        className="w-full h-auto block select-none"
      />
      
      {/* SVG Overlay for marking errors */}
      <svg 
        className="absolute top-0 left-0 w-full h-full pointer-events-none"
        style={{ width: '100%', height: '100%' }}
      >
        {imgSize.width > 0 && annotations && annotations.map((ann, idx) => {
          const isArray = Array.isArray(ann.coordinates);
          const ymin = isArray ? (ann.coordinates as any)[0] : (ann.coordinates as any).ymin;
          const xmin = isArray ? (ann.coordinates as any)[1] : (ann.coordinates as any).xmin;
          const ymax = isArray ? (ann.coordinates as any)[2] : (ann.coordinates as any).ymax;
          const xmax = isArray ? (ann.coordinates as any)[3] : (ann.coordinates as any).xmax;
          
          // Normalized 0-1000 to pixel coordinates
          const top = (ymin * imgSize.height) / 1000;
          const left = (xmin * imgSize.width) / 1000;
          const bottom = (ymax * imgSize.height) / 1000;
          const right = (xmax * imgSize.width) / 1000;
          const width = right - left;
          const height = bottom - top;

          const isSpelling = ann.issue_type === 'spelling';
          const strokeColor = isSpelling ? '#f43f5e' : '#f59e0b'; // Tailwind rose-500 for spelling, amber-500 for others
          const bgColor = isSpelling ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)';

          return (
            <g key={idx} className="transition-all duration-500">
              {/* Highlight Box */}
              <rect 
                x={left} 
                y={top} 
                width={width} 
                height={height} 
                fill={bgColor}
                stroke={strokeColor}
                strokeWidth="2"
                strokeDasharray={isSpelling ? "0" : "4 2"}
                rx="4"
              />
              
              {/* Suggestion Callout (Label outside the word) */}
              <g className="animate-fade-in" style={{ animationDelay: `${idx * 100}ms` }}>
                 {/* Connection Line */}
                 <line 
                   x1={right} 
                   y1={top + height/2} 
                   x2={right + 30} 
                   y2={top - 10} 
                   stroke={strokeColor} 
                   strokeWidth="1.5" 
                   strokeDasharray="2 2"
                 />
                 
                 {/* Label Container */}
                 <foreignObject
                   x={right + 35} 
                   y={top - 30}
                   width="150"
                   height="60"
                 >
                   <div className="flex flex-col items-start">
                     <span 
                       className="bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-[10px] sm:text-[12px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 shadow-xl font-bold"
                       style={{ borderColor: strokeColor }}
                     >
                       {ann.suggestion || 'Correction'}
                     </span>
                     <span className="text-[8px] uppercase tracking-tighter font-bold mt-0.5 px-1 rounded bg-slate-200 dark:bg-slate-800 text-slate-500">
                       {ann.issue_type}
                     </span>
                   </div>
                 </foreignObject>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default EvaluationViewer;
