import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { analysisApi, knobsApi } from '../../api';
import type { AnalysisExtractResponse, KnobDefinition, PersonaProfile } from '../../types';
import { SampleUpload } from './SampleUpload';
import { AnalysisResult } from './AnalysisResult';
import './AnalysisView.css';

export function AnalysisView() {
  const navigate = useNavigate();
  const [knobDefs, setKnobDefs] = useState<KnobDefinition[]>([]);

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisExtractResponse | null>(null);

  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdPersona, setCreatedPersona] = useState<PersonaProfile | null>(null);

  // Persist the last submitted text across renders for extract-and-create
  const lastTextRef = useRef('');

  useEffect(() => {
    knobsApi.getKnobs()
      .then(r => setKnobDefs(r.data.knobs))
      .catch(err => console.error('Failed to load knob definitions:', err));
  }, []);

  const handleAnalyze = async (text: string) => {
    setAnalyzing(true);
    setAnalyzeError(null);
    setResult(null);
    setCreatedPersona(null);
    setCreateError(null);

    try {
      const res = await analysisApi.extract(text);
      setResult(res.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Analysis failed. Is the backend running?';
      setAnalyzeError(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleCreatePersona = async (name: string) => {
    if (!result) return;
    setCreating(true);
    setCreateError(null);

    try {
      const res = await analysisApi.extractAndCreate(
        lastTextRef.current,
        name,
      );
      setCreatedPersona(res.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create persona.';
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  // Stash the most recently analyzed text so we can re-submit for extract-and-create
  const handleAnalyzeWithCache = async (text: string) => {
    lastTextRef.current = text;
    await handleAnalyze(text);
  };

  const handleOpenPersona = (persona: PersonaProfile) => {
    navigate('/', { state: { persona } });
  };

  const handleReset = () => {
    setResult(null);
    setAnalyzeError(null);
    setCreatedPersona(null);
    setCreateError(null);
  };

  return (
    <div className="analysis-view">
      <div className="analysis-view-inner">
        {/* Upload area is always visible; collapses visually when result shown */}
        <div className={`analysis-upload-section ${result ? 'has-result' : ''}`}>
          <SampleUpload onAnalyze={handleAnalyzeWithCache} analyzing={analyzing} />
        </div>

        {analyzeError && (
          <div className="analysis-error-banner">
            <span>⚠</span>
            {analyzeError}
            <button className="analysis-error-dismiss" onClick={() => setAnalyzeError(null)}>✕</button>
          </div>
        )}

        {analyzing && (
          <div className="analysis-progress-bar">
            <div className="analysis-progress-fill" />
          </div>
        )}

        {result && (
          <>
            <div className="analysis-result-divider">
              <span>Analysis complete</span>
              <button className="analysis-redo-btn" onClick={handleReset}>
                ↩ Analyze another sample
              </button>
            </div>

            {createError && (
              <div className="analysis-error-banner">
                <span>⚠</span>
                {createError}
                <button className="analysis-error-dismiss" onClick={() => setCreateError(null)}>✕</button>
              </div>
            )}

            <AnalysisResult
              result={result}
              knobDefs={knobDefs}
              onCreatePersona={handleCreatePersona}
              onOpenPersona={handleOpenPersona}
              createdPersona={createdPersona}
              creating={creating}
            />
          </>
        )}
      </div>
    </div>
  );
}
