import { useState } from 'react';
import './App.css';

const GRAPHQL_URL = 'http://localhost:8000/graphql';

function App() {
  const [title, setTitle] = useState('');
  const [mediaType, setMediaType] = useState('book');
  const [spoilerLevel, setSpoilerLevel] = useState('mild');
  const [length, setLength] = useState('medium');

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    setResult(null);

    try {
      const res = await fetch(GRAPHQL_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `
            mutation GenerateSummary($title: String!, $mediaType: String!, $spoilerLevel: String!, $length: String!) {
              generateSummary(title: $title, mediaType: $mediaType, spoilerLevel: $spoilerLevel, length: $length) {
                id
                title
                genre
                themes
                summary
                confidence
              }
            }
          `,
          variables: { title, mediaType, spoilerLevel, length },
        }),
      });

      const data = await res.json();

      if (data.errors) {
        throw new Error(data.errors[0].message);
      }

      if (data.data.generateSummary === null) {
        setNotFound(true);
      } else {
        setResult(data.data.generateSummary);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="app-card">
        <header className="hero-panel">
          <div className="hero-badge">AI Summary Studio</div>
          <h1 className="hero-title">Book & Movie Summarizer</h1>
          <p className="hero-copy">
            Enter a title, choose your spoiler and length preference, then let the AI unfold the story in
            a beautifully crafted summary.
          </p>
        </header>

        <section className="controls-panel">
          <div className="field-group">
            <label htmlFor="title">Title</label>
            <input
              id="title"
              type="text"
              placeholder="Enter book or movie title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="field-group">
            <label htmlFor="mediaType">Media type</label>
            <select id="mediaType" value={mediaType} onChange={(e) => setMediaType(e.target.value)}>
              <option value="book">Book</option>
              <option value="movie">Movie</option>
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="spoilerLevel">Spoiler level</label>
            <select id="spoilerLevel" value={spoilerLevel} onChange={(e) => setSpoilerLevel(e.target.value)}>
              <option value="none">None</option>
              <option value="mild">Mild</option>
              <option value="full">Full</option>
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="length">Length</label>
            <select id="length" value={length} onChange={(e) => setLength(e.target.value)}>
              <option value="short">Short</option>
              <option value="medium">Medium</option>
              <option value="long">Long</option>
            </select>
          </div>

          <button className="primary-button" onClick={handleGenerate} disabled={loading || !title}>
            {loading ? 'Generating summary…' : 'Generate Summary'}
          </button>

          {error && <p className="status-message status-error">Error: {error}</p>}
          {notFound && <p className="status-message status-warning">No match found for “{title}” as a {mediaType}.</p>}
        </section>

        {result && (
          <section className="result-panel">
            {result.confidence === 'low' && (
              <div className="confidence-banner">
                ⚠️ Low confidence — the title may be ambiguous or the summary may need extra verification.
              </div>
            )}

            <div className="result-header">
              <div>
                <p className="result-meta">{mediaType.toUpperCase()} SUMMARY</p>
                <h2>{result.title}</h2>
              </div>
              <div className="result-tags">
                <span>{result.genre.join(', ')}</span>
                <span>{result.themes.join(', ')}</span>
              </div>
            </div>

            <div className="summary-content">
              {result.summary.split('\n\n').map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export default App;