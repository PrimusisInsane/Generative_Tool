import { useState } from 'react';

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
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '600px' }}>
      <h1>Book & Movie Summarizer</h1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
        <label>
          Title:{' '}
          <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: '250px' }} />
        </label>

        <label>
          Media type:{' '}
          <select value={mediaType} onChange={(e) => setMediaType(e.target.value)}>
            <option value="book">Book</option>
            <option value="movie">Movie</option>
          </select>
        </label>

        <label>
          Spoiler level:{' '}
          <select value={spoilerLevel} onChange={(e) => setSpoilerLevel(e.target.value)}>
            <option value="none">None</option>
            <option value="mild">Mild</option>
            <option value="full">Full</option>
          </select>
        </label>

        <label>
          Length:{' '}
          <select value={length} onChange={(e) => setLength(e.target.value)}>
            <option value="short">Short</option>
            <option value="medium">Medium</option>
            <option value="long">Long</option>
          </select>
        </label>
      </div>

      <button onClick={handleGenerate} disabled={loading || !title}>
        {loading ? 'Generating...' : 'Generate Summary'}
      </button>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {notFound && <p style={{ color: '#b45309' }}>No match found for "{title}" as a {mediaType}.</p>}

      {result && (
        <div style={{ marginTop: '1.5rem' }}>
          {result.confidence === 'low' && (
            <div style={{ color: '#b45309', background: '#fef3c7', padding: '0.5rem', borderRadius: '4px', marginBottom: '1rem' }}>
              ⚠️ Low confidence — this may not be accurate or the title may be ambiguous.
            </div>
          )}
          <h2>{result.title}</h2>
          <p><strong>Genre:</strong> {result.genre.join(', ')}</p>
          <p><strong>Themes:</strong> {result.themes.join(', ')}</p>
          {result.summary.split('\n\n').map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;