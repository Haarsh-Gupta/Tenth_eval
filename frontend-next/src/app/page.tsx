"use client";
import React, { useState, useEffect, useRef, useCallback } from 'react';
import EvaluationViewer from '@/components/EvaluationViewer';
import ReactMarkdown from 'react-markdown';

interface StatusUpdate {
  message: string;
  step: string;
  icon?: string;
  status?: 'running' | 'completed' | 'error';
}

interface EvaluationResult {
  feedback: any;
  original_files: string[];
  annotated_files: string[];
  static_url_prefix: string;
  question_extracted?: string;
  answer_extracted?: string;
  search_queries?: string[];
  context?: any[];
}

const PIPELINE_STEPS = [
  { key: 'init', label: 'Initialize', icon: '🚀' },
  { key: 'ocr', label: 'OCR Extraction', icon: '📝' },
  { key: 'query', label: 'Query Generation', icon: '🧠' },
  { key: 'rag', label: 'Context Retrieval', icon: '📚' },
  { key: 'evaluation', label: 'AI Evaluation', icon: '🎯' },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const FilePreview = ({ file }: { file: File }) => {
  const [url, setUrl] = useState<string>('');
  
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  if (!url) return <div className="h-[400px] bg-slate-100 dark:bg-slate-800 animate-pulse rounded-xl" />;

  return (
    <div className="glass-card p-2 w-full">
      {file.type === 'application/pdf' ? (
        <iframe src={url} className="w-full h-[800px] rounded-xl border-0" title={file.name} />
      ) : (
        <img src={url} alt={file.name} className="w-full h-auto rounded-xl object-contain bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800" />
      )}
    </div>
  );
};

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [instructions, setInstructions] = useState('');
  const [useReranking, setUseReranking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusUpdates, setStatusUpdates] = useState<StatusUpdate[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<EvaluationResult | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const statusEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    statusEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [statusUpdates]);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const validFiles = Array.from(newFiles).filter(f =>
      f.type.startsWith('image/') ||
      f.type === 'application/pdf' ||
      f.name.toLowerCase().endsWith('.pdf') ||
      f.name.toLowerCase().endsWith('.png') ||
      f.name.toLowerCase().endsWith('.jpg') ||
      f.name.toLowerCase().endsWith('.jpeg') ||
      f.name.toLowerCase().endsWith('.webp')
    );
    if (validFiles.length > 0) {
      setFiles(prev => [...prev, ...validFiles]);
    }
  }, []);

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // ---- Drag & Drop handlers ----
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    dragCounter.current = 0;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
      // Reset so the same file can be selected again
      e.target.value = '';
    }
  };

  // ---- SSE-based evaluation ----
  const handleEvaluate = async () => {
    if (files.length === 0) return;

    setLoading(true);
    setStatusUpdates([]);
    setCurrentStep(null);
    setCompletedSteps(new Set());
    setResult(null);
    setErrorMessage(null);

    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    if (instructions) formData.append('instructions', instructions);
    formData.append('use_reranking', String(useReranking));

    try {
      const response = await fetch('http://localhost:8000/evaluate', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Server error (${response.status}): ${errText}`);
      }

      if (!response.body) throw new Error('No response body — SSE not supported');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are delimited by double newlines
        // Handle both \r\n\r\n and \n\n
        const messages = buffer.split(/\r?\n\r?\n/);
        buffer = messages.pop() || '';

        for (const message of messages) {
          if (!message.trim()) continue;

          // Parse SSE fields from the message block
          let eventType = 'message';
          let dataLines: string[] = [];

          for (const line of message.split(/\r?\n/)) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              dataLines.push(line.slice(5).trim());
            }
            // Ignore id:, retry:, comments (:)
          }

          if (dataLines.length === 0) continue;
          const dataStr = dataLines.join('\n');

          try {
            const data = JSON.parse(dataStr);

            if (eventType === 'status') {
              const update: StatusUpdate = {
                message: data.message,
                step: data.step,
                icon: data.icon,
                status: data.status,
              };

              setStatusUpdates(prev => [...prev, update]);

              if (data.status === 'running') {
                setCurrentStep(data.step);
              }
              if (data.status === 'completed') {
                setCompletedSteps(prev => new Set([...prev, data.step]));
              }

            } else if (eventType === 'result') {
              setResult(data);
              setLoading(false);
              setCurrentStep(null);

            } else if (eventType === 'error') {
              setErrorMessage(data.message || 'Unknown error occurred');
              setLoading(false);
              setCurrentStep(null);
            }
          } catch (parseErr) {
            console.warn('Failed to parse SSE data:', dataStr, parseErr);
          }
        }
      }

      // If we exited the loop but loading is still true, mark as done
      setLoading(false);

    } catch (err: any) {
      console.error('Evaluation error:', err);
      setErrorMessage(err.message || 'Failed to connect to the evaluation server');
      setLoading(false);
    }
  };

  const API_URL = 'http://localhost:8000';

  // Derive the step status for the stepper
  const getStepStatus = (stepKey: string): 'idle' | 'running' | 'completed' => {
    if (completedSteps.has(stepKey)) return 'completed';
    if (currentStep === stepKey) return 'running';
    return 'idle';
  };

  return (
    <main className="min-h-screen p-4 md:p-8 flex flex-col items-center bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="w-full max-w-6xl flex flex-col md:flex-row justify-between items-center mb-12 animate-fade-in">
        <div className="text-center md:text-left">
          <h1 className="text-4xl md:text-6xl font-black tracking-tight mb-2 bg-clip-text text-transparent bg-linear-to-r from-indigo-500 to-rose-500">
            CBSE AI Evaluator
          </h1>
          <p className="text-slate-500 dark:text-slate-400 font-medium">
            Smart Answer Sheet Grading • Modern CBSE Standards
          </p>
        </div>
        
        <button 
          onClick={() => setShowSettings(!showSettings)}
          className="mt-6 md:mt-0 p-3 rounded-2xl glass-card hover:bg-slate-100 dark:hover:bg-slate-800 transition-all flex items-center gap-2 group"
        >
          <span className="text-xl group-hover:rotate-90 transition-transform duration-500">⚙️</span>
          <span className="font-semibold text-sm">Settings</span>
        </button>
      </div>

      {/* Settings Overlay */}
      {mounted && showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass-card w-full max-w-lg p-8 relative overflow-hidden backdrop-blur-2xl">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 blur-3xl -z-10 rounded-full" />
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Preferences</h2>
              <button onClick={() => setShowSettings(false)} className="text-2xl hover:scale-110 transition-transform">✕</button>
            </div>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-bold mb-2 uppercase tracking-widest text-slate-400">Custom Prompt Instructions</label>
                <textarea 
                  className="input-field w-full h-32 resize-none"
                  placeholder="E.g. Be very strict with grammar, Focus on historical dates..."
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </div>
              
              <div className="flex items-center justify-between p-4 bg-slate-100/50 dark:bg-slate-800/50 rounded-2xl border border-slate-200/50 dark:border-slate-700/50">
                <div>
                  <h3 className="font-bold text-sm uppercase tracking-wider">BM25 Reranking</h3>
                  <p className="text-xs text-slate-500">Use hybrid search for higher accuracy</p>
                </div>
                <button 
                  onClick={() => setUseReranking(!useReranking)}
                  className={`w-12 h-6 rounded-full transition-all flex items-center px-1 ${useReranking ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-700'}`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${useReranking ? 'translate-x-6' : 'translate-x-0'}`} />
                </button>
              </div>
              
              <button 
                onClick={() => setShowSettings(false)}
                className="btn-primary w-full"
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Upload & Control */}
        <div className="lg:col-span-4 flex flex-col gap-6 animate-fade-in" style={{ animationDelay: '100ms' }}>
          <div className="glass-card p-8 group overflow-hidden relative">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 blur-3xl rounded-full" />
            <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
              <span className="p-2 bg-indigo-500/10 rounded-lg text-indigo-500">📂</span>
              Upload Paper
            </h3>
            
            {/* Drop Zone */}
            <div 
              className={`border-2 border-dashed rounded-3xl p-10 transition-all duration-300 flex flex-col items-center justify-center gap-3 text-center cursor-pointer relative
              ${isDragOver
                ? 'border-indigo-500 bg-indigo-500/10 scale-[1.02] shadow-lg shadow-indigo-500/20'
                : files.length > 0
                  ? 'border-indigo-500 bg-indigo-500/5'
                  : 'border-slate-300 dark:border-slate-700 hover:border-indigo-500/50 hover:bg-slate-100/50 dark:hover:bg-slate-800/50'
              }`}
              onClick={() => fileInputRef.current?.click()}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              <input 
                ref={fileInputRef}
                id="fileInput"
                type="file" 
                multiple 
                accept="image/*,.pdf"
                className="hidden"
                onChange={handleFileChange}
              />

              {isDragOver && (
                <div className="absolute inset-0 flex items-center justify-center bg-indigo-500/10 rounded-3xl z-10">
                  <div className="text-indigo-500 font-bold text-lg animate-pulse">
                    Drop files here
                  </div>
                </div>
              )}

              <div className={`text-5xl transition-transform duration-500 ${isDragOver ? 'scale-125' : 'group-hover:scale-110'}`}>
                {isDragOver ? '📥' : '📎'}
              </div>
              <div>
                <p className="font-bold">
                  {files.length > 0 ? `${files.length} File${files.length > 1 ? 's' : ''} Selected` : 'Drop or Click to Upload'}
                </p>
                <p className="text-xs text-slate-500 mt-1">Images (PNG, JPG, WebP) or PDF accepted</p>
              </div>
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="mt-4 space-y-2 max-h-[200px] overflow-y-auto pr-1 scrollbar-hide">
                {files.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200/50 dark:border-slate-700/50 group/file animate-fade-in"
                  >
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-sm">
                      {file.type === 'application/pdf' ? '📄' : '🖼️'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-[10px] text-slate-500">{formatFileSize(file.size)}</p>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                      className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-500/10 text-rose-500 flex items-center justify-center text-xs opacity-0 group-hover/file:opacity-100 transition-opacity hover:bg-rose-500/20"
                      title="Remove file"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            <button 
              onClick={handleEvaluate}
              disabled={loading || files.length === 0}
              className={`btn-primary w-full mt-6 py-4 flex items-center justify-center gap-3 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 ${loading ? 'animate-pulse' : ''}`}
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  🚀 Start Evaluation
                </>
              )}
            </button>
          </div>

          {/* Pipeline Stepper */}
          {(loading || statusUpdates.length > 0) && (
            <div className="glass-card p-6 animate-fade-in relative overflow-hidden">
              <div className="absolute bottom-0 right-0 w-32 h-32 bg-rose-500/5 blur-3xl rounded-full" />
              <h3 className="font-bold mb-5 flex items-center gap-2 text-slate-400 uppercase tracking-widest text-xs">
                Pipeline Status
              </h3>
              
              <div className="space-y-1">
                {PIPELINE_STEPS.map((step, idx) => {
                  const status = getStepStatus(step.key);
                  return (
                    <div key={step.key} className="flex items-center gap-3 py-2">
                      {/* Step indicator */}
                      <div className="relative flex flex-col items-center">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-500
                            ${status === 'completed'
                              ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30'
                              : status === 'running'
                                ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30 animate-pulse'
                                : 'bg-slate-200 dark:bg-slate-800 text-slate-400'
                            }`}
                        >
                          {status === 'completed' ? '✓' : step.icon}
                        </div>
                        {/* Connector line */}
                        {idx < PIPELINE_STEPS.length - 1 && (
                          <div className={`absolute top-8 w-0.5 h-4 transition-colors duration-500
                            ${status === 'completed' ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-800'}`}
                          />
                        )}
                      </div>
                      
                      {/* Step label */}
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-semibold transition-colors duration-300
                          ${status === 'completed'
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : status === 'running'
                              ? 'text-indigo-600 dark:text-indigo-400'
                              : 'text-slate-400'
                          }`}
                        >
                          {step.label}
                        </p>
                        {status === 'running' && (
                          <p className="text-[10px] text-indigo-500 dark:text-indigo-400 animate-pulse">In progress...</p>
                        )}
                        {status === 'completed' && (
                          <p className="text-[10px] text-emerald-500">Completed</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Error display */}
              {errorMessage && (
                <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-600 dark:text-rose-400 text-sm font-medium">
                  ⚠️ {errorMessage}
                </div>
              )}

              <div ref={statusEndRef} />
            </div>
          )}
        </div>

        {/* Right Column: Visualization & Feedback */}
        <div className="lg:col-span-8 space-y-8 animate-fade-in" style={{ animationDelay: '200ms' }}>
          {result ? (
            <>
              {/* Feedback Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="glass-card p-6 border-l-4 border-l-indigo-600">
                  <p className="text-xs text-slate-500 uppercase tracking-widest font-bold mb-1">Score</p>
                  <p className="text-3xl font-black">{result.feedback?.marks_awarded ?? '—'} <span className="text-lg text-slate-400">/ {result.feedback?.total_marks || 10}</span></p>
                </div>
                <div className="glass-card p-6 border-l-4 border-l-emerald-600">
                  <p className="text-xs text-slate-500 uppercase tracking-widest font-bold mb-1">Performance</p>
                  <p className="text-3xl font-black capitalize text-emerald-600">{result.feedback?.overall_performance || '—'}</p>
                </div>
                <div className="glass-card p-6 border-l-4 border-l-rose-600">
                  <p className="text-xs text-slate-500 uppercase tracking-widest font-bold mb-1">Annotations</p>
                  <p className="text-3xl font-black">{result.feedback?.visual_annotations?.length || 0}</p>
                </div>
              </div>

              {/* Pipeline Meta-Data Expandables */}
              <div className="glass-card p-6 space-y-4">
                 <h4 className="text-sm font-bold uppercase tracking-widest text-slate-400">Processing Details</h4>
                 <details className="group border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                    <summary className="p-4 bg-slate-50 dark:bg-slate-900 font-semibold cursor-pointer select-none">
                      📝 Extracted Text (OCR)
                    </summary>
                    <div className="p-4 text-sm whitespace-pre-wrap text-slate-600 dark:text-slate-300">
                      <strong>Question:</strong> {result.question_extracted}
                      <hr className="my-3 border-slate-200 dark:border-slate-800" />
                      <strong>Answer:</strong> {result.answer_extracted}
                    </div>
                 </details>
                 
                 <details className="group border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                    <summary className="p-4 bg-slate-50 dark:bg-slate-900 font-semibold cursor-pointer select-none">
                      🧠 Search Queries
                    </summary>
                    <ul className="p-4 text-sm list-disc list-inside text-slate-600 dark:text-slate-300 space-y-1">
                      {result.search_queries?.map((q, i) => <li key={i}>{q}</li>)}
                    </ul>
                 </details>

                 <details className="group border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                    <summary className="p-4 bg-slate-50 dark:bg-slate-900 font-semibold cursor-pointer select-none">
                      📚 Retrieved Context
                    </summary>
                    <div className="p-4 text-sm space-y-3 text-slate-600 dark:text-slate-300 max-h-[400px] overflow-y-auto">
                      {result.context?.map((c, i) => (
                        <div key={i} className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                          <strong className="text-indigo-500">Source {i+1} ({c.book_name}):</strong>
                          <div className="mt-2 prose prose-sm prose-slate dark:prose-invert">
                            <ReactMarkdown>{c.content}</ReactMarkdown>
                          </div>
                        </div>
                      ))}
                    </div>
                 </details>
              </div>

              {/* View Container */}
              <div className="space-y-6">
                <div className="flex justify-between items-end">
                  <h3 className="text-2xl font-black tracking-tight">Visual Marking</h3>
                  <div className="flex gap-2">
                    <span className="text-xs p-1.5 rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 font-bold uppercase">Spelling Error</span>
                    <span className="text-xs p-1.5 rounded-lg bg-amber-500/10 text-amber-500 border border-amber-500/20 font-bold uppercase">Content Issue</span>
                  </div>
                </div>
                
                {result.original_files.map((filename, i) => (
                  <div key={i} className="animate-fade-in" style={{ animationDelay: `${i * 200}ms` }}>
                    <EvaluationViewer 
                      imageUrl={`${API_URL}/static/${filename}`} 
                      annotations={result.feedback?.visual_annotations || []}
                    />
                  </div>
                ))}
              </div>

              {/* Textual Feedback */}
              <div className="glass-card p-8">
                 <h3 className="text-xl font-bold mb-6 pb-4 border-b border-slate-200 dark:border-slate-800">Content Feedback</h3>
                 <div className="prose prose-slate dark:prose-invert max-w-none">
                    <p className="text-slate-600 dark:text-slate-300 leading-relaxed italic">
                      &ldquo;{result.feedback?.content_feedback || 'No feedback available.'}&rdquo;
                    </p>
                    
                    {result.feedback?.suggested_rewrite && (
                      <div className="mt-8 p-6 bg-slate-100 dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                        <h4 className="text-sm font-bold uppercase tracking-widest text-indigo-500 mb-4">Suggested Perfect Rewrite</h4>
                        <p className="text-sm leading-7">{result.feedback.suggested_rewrite}</p>
                      </div>
                    )}
                 </div>
              </div>
            </>
          ) : files.length > 0 ? (
            <div className="space-y-6">
              <div className="flex justify-between items-end mb-4">
                <h3 className="text-2xl font-black tracking-tight flex items-center gap-2">
                  <span className="text-slate-400">👀</span> File Preview
                </h3>
              </div>
              {files.map((file, i) => (
                <div key={i} className="animate-fade-in" style={{ animationDelay: `${i * 100}ms` }}>
                  <FilePreview file={file} />
                </div>
              ))}
            </div>
          ) : (
            <div className="h-[600px] glass-card flex flex-col items-center justify-center text-center p-12 border-dashed border-2 border-slate-200 dark:border-slate-800">
              <div className="w-24 h-24 bg-slate-100 dark:bg-slate-900 rounded-full flex items-center justify-center text-4xl animate-bounce mb-6 grayscale opacity-50">
                📄
              </div>
              <h3 className="text-2xl font-bold text-slate-300">Ready to Evaluate</h3>
              <p className="text-slate-500 max-w-sm mt-2">
                Upload your answer sheet scan or PDF to see real-time AI grading with visual feedback.
              </p>
            </div>
          )}
        </div>
      </div>
      
      {/* Footer */}
      <footer className="mt-20 py-8 border-t border-slate-200 dark:border-slate-800 w-full max-w-6xl flex justify-between items-center text-slate-500 text-xs">
        <p>© 2024 CBSE Answer Sheet Evaluator • Powered by Antigravity AI Engine</p>
        <div className="flex gap-4">
          <span className="hover:text-indigo-500 cursor-pointer transition-colors">Privacy</span>
          <span className="hover:text-indigo-500 cursor-pointer transition-colors">Documentation</span>
          <span className="hover:text-indigo-500 cursor-pointer transition-colors">Support</span>
        </div>
      </footer>
    </main>
  );
}
