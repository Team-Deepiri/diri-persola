import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from 'react';
import './SampleUpload.css';

const MIN_CHARS = 80;
const MAX_CHARS = 20_000;

interface SampleUploadProps {
  onAnalyze: (text: string) => void;
  analyzing: boolean;
}

function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function SampleUpload({ onAnalyze, analyzing }: SampleUploadProps) {
  const [text, setText] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const chars = text.length;
  const words = wordCount(text);
  const tooShort = chars < MIN_CHARS;
  const tooLong = chars > MAX_CHARS;
  const canAnalyze = !tooShort && !tooLong && !analyzing;

  const readFile = useCallback((file: File) => {
    setFileError(null);
    if (!file.name.match(/\.(txt|md|text)$/i) && file.type !== 'text/plain') {
      setFileError('Only plain text files (.txt, .md) are supported.');
      return;
    }
    const reader = new FileReader();
    reader.onload = e => {
      const content = e.target?.result as string;
      setText(content.slice(0, MAX_CHARS));
    };
    reader.onerror = () => setFileError('Failed to read file.');
    reader.readAsText(file);
  }, []);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) readFile(file);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) readFile(file);
    // Reset so the same file can be re-selected
    e.target.value = '';
  };

  const handleClear = () => {
    setText('');
    setFileError(null);
  };

  return (
    <div className="sample-upload">
      <div className="upload-intro">
        <h2 className="upload-title">Writing Sample Analysis</h2>
        <p className="upload-subtitle">
          Paste text or drop a plain‑text file. The analysis engine extracts communication
          style, personality traits, and reasoning patterns, then maps them to persona knobs.
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${text ? 'has-content' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !text && fileInputRef.current?.click()}
        role="button"
        tabIndex={text ? -1 : 0}
        aria-label="Drop a text file here or click to browse"
        onKeyDown={e => e.key === 'Enter' && !text && fileInputRef.current?.click()}
      >
        {!text && (
          <div className="drop-zone-hint">
            <div className="drop-zone-icon">📄</div>
            <p className="drop-zone-primary">Drop a .txt file here</p>
            <p className="drop-zone-secondary">
              or{' '}
              <span className="drop-zone-link" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                browse
              </span>{' '}
              your files
            </p>
          </div>
        )}

        <textarea
          className="sample-textarea"
          placeholder="…or paste your writing sample here"
          value={text}
          onChange={e => { setText(e.target.value.slice(0, MAX_CHARS)); setFileError(null); }}
          spellCheck={false}
          aria-label="Writing sample text"
        />

        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,text/plain"
          className="file-input-hidden"
          onChange={handleFileInput}
          tabIndex={-1}
        />
      </div>

      {/* Status row */}
      <div className="upload-status-row">
        <div className="upload-counters">
          <span className={`counter ${tooShort && chars > 0 ? 'counter-warn' : ''} ${tooLong ? 'counter-error' : ''}`}>
            {chars.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
          </span>
          <span className="counter counter-words">{words.toLocaleString()} words</span>
          {tooShort && chars > 0 && (
            <span className="counter counter-warn">
              Need at least {MIN_CHARS} characters
            </span>
          )}
          {tooLong && (
            <span className="counter counter-error">Exceeds the {MAX_CHARS.toLocaleString()} character limit</span>
          )}
        </div>

        {fileError && <p className="upload-file-error">⚠ {fileError}</p>}

        <div className="upload-actions">
          {text && (
            <button type="button" className="btn btn-secondary" onClick={handleClear} disabled={analyzing}>
              Clear
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => canAnalyze && onAnalyze(text)}
            disabled={!canAnalyze}
          >
            {analyzing ? (
              <>
                <span className="btn-spinner" />
                Analyzing…
              </>
            ) : (
              '🔍 Analyze Style'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
