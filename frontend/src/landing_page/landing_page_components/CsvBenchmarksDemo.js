// import React, { useEffect, useMemo, useState } from 'react';
// import { LeaderboardSDK } from '../../lib/leaderboardSdk';

// export default function CsvBenchmarksDemo() {
//   const [loading, setLoading] = useState(false);
//   const [datasets, setDatasets] = useState([]);
//   const [selected, setSelected] = useState({});
//   const [filter, setFilter] = useState('');
//   const [sampleSize, setSampleSize] = useState(10);
//   const [results, setResults] = useState(null);
//   const [error, setError] = useState(null);
//   const [echoMode, setEchoMode] = useState(false);
//   const [modelCatalog, setModelCatalog] = useState([]);
//   const [modelSelected, setModelSelected] = useState({});
//   const [showRaw, setShowRaw] = useState(false);
//   const [rawJson, setRawJson] = useState('');

//   useEffect(() => {
//     let ignore = false;
//     (async () => {
//       setLoading(true);
//       setError(null);
//       try {
//         const data = await LeaderboardSDK.listBenchmarkCsvs();
//         if (!ignore) {
//           const items = (data?.datasets || []).filter(d => d.task_type !== 'unknown');
//           setDatasets(items);
//           // Preselect up to 5 datasets for a quick demo
//           const init = {};
//           items.slice(0, 5).forEach(it => { init[it.filename] = true; });
//           setSelected(init);
//         }
//         // Load default models (from backend/models.py)
//         const m = await LeaderboardSDK.listBenchmarkModels();
//         if (!ignore) {
//           const models = Array.isArray(m?.models) ? m.models : [];
//           setModelCatalog(models);
//           const msel = {};
//           models.slice(0, 3).forEach(mm => { msel[mm.name] = true; });
//           setModelSelected(msel);
//         }
//       } catch (e) {
//         if (!ignore) setError(e.message || 'Failed to load datasets');
//       } finally {
//         if (!ignore) setLoading(false);
//       }
//     })();
//     return () => { ignore = true; };
//   }, []);

//   const selectedList = useMemo(() => Object.keys(selected).filter(k => selected[k]), [selected]);

//   async function runBench() {
//     setLoading(true);
//     setError(null);
//     setResults(null);
//     try {
//       const payload = { datasets: selectedList, sample_size: Number(sampleSize) || 10 };
//       if (echoMode) {
//         payload.models = [{ name: 'echo', provider: 'echo' }];
//       } else {
//         const chosen = modelCatalog.filter(m => modelSelected[m.name]);
//         if (chosen.length > 0) {
//           payload.models = chosen.map(m => ({ name: m.name, provider: m.provider || 'py', fn: m.fn }));
//         }
//         // If none chosen, omit to use backend defaults
//       }
//       const data = await LeaderboardSDK.runCsvBenchmarks(payload);
//       setResults(data);
//       setRawJson(JSON.stringify(data, null, 2));
//       setShowRaw(true);
//     } catch (e) {
//       setError(e.message || 'Benchmark failed');
//     } finally {
//       setLoading(false);
//     }
//   }

//   const modelNames = useMemo(() => {
//     if (!results?.runs) return [];
//     const names = new Set();
//     results.runs.forEach(r => {
//       if (r.results) Object.keys(r.results).forEach(n => names.add(n));
//     });
//     return Array.from(names);
//   }, [results]);

//   const filteredDatasets = useMemo(() => {
//     const q = filter.trim().toLowerCase();
//     if (!q) return datasets;
//     return datasets.filter(ds => ds.filename.toLowerCase().includes(q) || (ds.task_type || '').toLowerCase().includes(q));
//   }, [datasets, filter]);

//   function selectAll() {
//     const next = { ...selected };
//     filteredDatasets.forEach(it => { next[it.filename] = true; });
//     setSelected(next);
//   }

//   function clearSelection() {
//     const next = { ...selected };
//     Object.keys(next).forEach(k => { next[k] = false; });
//     setSelected(next);
//   }

//   function formatMetricCell(res) {
//     if (!res) return '—';
//     const metric = res.metric || 'score';
//     const val = typeof res.score === 'number' ? res.score : (typeof res.f1 === 'number' ? res.f1 : null);
//     if (val === null) return JSON.stringify(res);
//     return `${val.toFixed(3)} ${metric}`;
//   }

//   return (
//     <div className="max-w-6xl mx-auto px-4 py-8">
//       <h1 className="text-2xl font-semibold mb-1">CSV Benchmarks Demo</h1>
//       <p className="text-sm text-gray-500 mb-6">Select datasets from the bundled benchmark CSVs and run zero-shot models. Use Echo mode to dry-run without API keys.</p>

//       {error && <div className="p-3 mb-3 border border-red-300 text-red-700 rounded">{String(error)}</div>}
//       {loading && <div className="mb-3 text-sm">Running… This may take a minute for real models.</div>}

//       <div className="mb-4 flex items-center gap-3 flex-wrap">
//         <label className="mr-2 text-sm">Sample size per dataset:</label>
//         <input type="number" value={sampleSize} min={1} max={200} onChange={e => setSampleSize(e.target.value)} className="border px-2 py-1 w-24" />
//         <label className="ml-4 text-sm flex items-center gap-2">
//           <input type="checkbox" checked={echoMode} onChange={e => setEchoMode(e.target.checked)} />
//           Echo mode (no API keys)
//         </label>
//         <button onClick={runBench} disabled={loading || selectedList.length === 0} className="ml-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50">
//           Run Benchmarks
//         </button>
//         <button onClick={selectAll} disabled={loading || filteredDatasets.length === 0} className="px-3 py-1 border rounded">Select All</button>
//         <button onClick={clearSelection} disabled={loading || selectedList.length === 0} className="px-3 py-1 border rounded">Clear</button>
//       </div>

//       <div className="flex items-center justify-between mb-2">
//         <div className="text-xs text-gray-500">Selected {selectedList.length} of {datasets.length} datasets</div>
//         <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter datasets…" className="border px-2 py-1 text-sm w-56" />
//       </div>

//       <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
//         {filteredDatasets.map(ds => (
//           <label key={ds.filename} className="border rounded p-2 flex items-center gap-2">
//             <input type="checkbox" checked={!!selected[ds.filename]} onChange={(e) => setSelected(s => ({ ...s, [ds.filename]: e.target.checked }))} />
//             <span className="font-medium">{ds.filename}</span>
//             <span className="text-xs text-gray-500">({ds.task_type})</span>
//           </label>
//         ))}
//       </div>

//       {!echoMode && modelCatalog.length > 0 && (
//         <div className="mb-6">
//           <h2 className="font-medium mb-2">Models</h2>
//           <p className="text-xs text-gray-500 mb-2">Select specific models to run. If none selected, backend defaults are used.</p>
//           <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
//             {modelCatalog.map(m => (
//               <label key={m.name} className="border rounded p-2 flex items-center gap-2">
//                 <input type="checkbox" checked={!!modelSelected[m.name]} onChange={(e) => setModelSelected(s => ({ ...s, [m.name]: e.target.checked }))} />
//                 <span className="font-medium">{m.name}</span>
//                 {m.fn && <span className="text-xs text-gray-500">(fn: {m.fn})</span>}
//               </label>
//             ))}
//           </div>
//         </div>
//       )}

//       {results?.runs && results.runs.length > 0 && (
//         <div className="overflow-x-auto">
//           <div className="flex items-center justify-between mb-2">
//             <div className="text-sm">Runs: {results.runs.length} • Models: {modelNames.length}</div>
//             <button onClick={() => setShowRaw(v => !v)} className="text-sm underline">{showRaw ? 'Hide' : 'Show'} sample response</button>
//           </div>
//           {showRaw && (
//             <pre className="border rounded bg-gray-50 text-gray-800 p-3 text-xs mb-3 overflow-auto max-h-64">{rawJson}</pre>
//           )}
//           <table className="min-w-full border text-sm">
//             <thead>
//               <tr>
//                 <th className="border px-2 py-1 text-left">Dataset</th>
//                 <th className="border px-2 py-1 text-left">Task</th>
//                 <th className="border px-2 py-1 text-left">Count</th>
//                 {modelNames.map(m => (
//                   <th className="border px-2 py-1 text-left" key={m}>{m}</th>
//                 ))}
//               </tr>
//             </thead>
//             <tbody>
//               {results.runs.map((r) => (
//                 <tr key={r.dataset}>
//                   <td className="border px-2 py-1">{r.dataset}</td>
//                   <td className="border px-2 py-1">{r.task_type}</td>
//                   <td className="border px-2 py-1">{r.count}</td>
//                   {modelNames.map((m) => {
//                     const res = r.results?.[m];
//                     if (!res) return <td className="border px-2 py-1" key={m}>—</td>;
//                     const display = formatMetricCell(res);
//                     return <td className="border px-2 py-1" key={m}>{display}</td>;
//                   })}
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         </div>
//       )}
//     </div>
//   );
// }
import React, { useEffect, useMemo, useState } from 'react';
import { LeaderboardSDK } from '../../lib/leaderboardSdk';

export default function CsvBenchmarksDemo() {
  const [loading, setLoading] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [selected, setSelected] = useState({});
  const [filter, setFilter] = useState('');
  const [sampleSize, setSampleSize] = useState(10);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [echoMode, setEchoMode] = useState(false);
  const [modelCatalog, setModelCatalog] = useState([]);
  const [modelSelected, setModelSelected] = useState({});
  const [showRaw, setShowRaw] = useState(false);
  const [rawJson, setRawJson] = useState('');

  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await LeaderboardSDK.listBenchmarkCsvs();
        if (!ignore) {
          const items = (data?.datasets || []).filter(d => d.task_type !== 'unknown');
          setDatasets(items);
          const init = {};
          items.slice(0, 5).forEach(it => { init[it.filename] = true; });
          setSelected(init);
        }
        const m = await LeaderboardSDK.listBenchmarkModels();
        if (!ignore) {
          const models = Array.isArray(m?.models) ? m.models : [];
          setModelCatalog(models);
          const msel = {};
          models.slice(0, 3).forEach(mm => { msel[mm.name] = true; });
          setModelSelected(msel);
        }
      } catch (e) {
        if (!ignore) setError(e.message || 'Failed to load datasets');
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  const selectedList = useMemo(() => Object.keys(selected).filter(k => selected[k]), [selected]);

  async function runBench() {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const payload = { datasets: selectedList, sample_size: Number(sampleSize) || 10 };
      if (echoMode) {
        payload.models = [{ name: 'echo', provider: 'echo' }];
      } else {
        const chosen = modelCatalog.filter(m => modelSelected[m.name]);
        if (chosen.length > 0) {
          payload.models = chosen.map(m => ({ name: m.name, provider: m.provider || 'py', fn: m.fn }));
        }
      }
      const data = await LeaderboardSDK.runCsvBenchmarks(payload);
      setResults(data);
      setRawJson(JSON.stringify(data, null, 2));
      setShowRaw(true);
    } catch (e) {
      setError(e.message || 'Benchmark failed');
    } finally {
      setLoading(false);
    }
  }

  const modelNames = useMemo(() => {
    if (!results?.runs) return [];
    const names = new Set();
    results.runs.forEach(r => {
      if (r.results) Object.keys(r.results).forEach(n => names.add(n));
    });
    return Array.from(names);
  }, [results]);

  const filteredDatasets = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return datasets;
    return datasets.filter(ds => ds.filename.toLowerCase().includes(q) || (ds.task_type || '').toLowerCase().includes(q));
  }, [datasets, filter]);

  function selectAll() {
    const next = { ...selected };
    filteredDatasets.forEach(it => { next[it.filename] = true; });
    setSelected(next);
  }

  function clearSelection() {
    const next = { ...selected };
    Object.keys(next).forEach(k => { next[k] = false; });
    setSelected(next);
  }

  function formatMetricCell(res) {
    if (!res) return '—';
    const metric = res.metric || 'score';
    const val = typeof res.score === 'number' ? res.score : (typeof res.f1 === 'number' ? res.f1 : null);
    if (val === null) return JSON.stringify(res);
    return `${val.toFixed(3)} ${metric}`;
  }

  return (
    <div className="min-h-screen bg-[#111827] px-4 py-10 text-gray-100">
    <div className="max-w-6xl mx-auto">
      <div className="text-xs uppercase tracking-[0.2em] text-[#defe47] mb-3">Benchmark Runner</div>
      <h1 className="text-3xl sm:text-4xl font-extrabold mb-2 bg-gradient-to-r from-[#defe47] to-[#28b2fb] bg-clip-text text-transparent">CSV Benchmarks</h1>
      <p className="text-sm text-gray-300 mb-6 max-w-2xl">
        Select datasets from the bundled benchmark CSVs and run zero-shot models.
        Use Echo mode to dry-run without API keys.
      </p>

      {error && <div className="p-3 mb-4 border border-red-500/50 bg-red-950 text-red-200 rounded-md">{String(error)}</div>}
      {loading && <div className="mb-3 text-sm text-[#defe47]">Running... This may take a minute for real models.</div>}

      <div className="mb-6 flex items-center gap-3 flex-wrap border border-gray-800 bg-[#0d1421] rounded-lg p-4">
        <label className="text-sm font-medium">Sample size per dataset:</label>
        <input
          type="number"
          value={sampleSize}
          min={1}
          max={200}
          onChange={e => setSampleSize(e.target.value)}
          className="border border-gray-700 bg-[#111827] px-2 py-1 w-24 rounded-md text-white focus:outline-none focus:border-[#defe47]/70"
        />
        <label className="ml-4 text-sm flex items-center gap-2">
          <input type="checkbox" checked={echoMode} onChange={e => setEchoMode(e.target.checked)} />
          Echo mode (no API keys)
        </label>
        <button
          onClick={runBench}
          disabled={loading || selectedList.length === 0}
          className="ml-3 px-4 py-2 bg-[#defe47] hover:bg-[#28b2fb] text-black font-semibold rounded-md disabled:opacity-40"
        >
          Run Benchmarks
        </button>
        <button
          onClick={selectAll}
          disabled={loading || filteredDatasets.length === 0}
          className="px-4 py-2 border border-[#defe47]/60 text-[#defe47] rounded-md hover:bg-[#defe47]/10 disabled:opacity-40"
        >
          Select All
        </button>
        <button
          onClick={clearSelection}
          disabled={loading || selectedList.length === 0}
          className="px-4 py-2 border border-gray-700 text-gray-300 rounded-md hover:bg-[#111827] disabled:opacity-40"
        >
          Clear
        </button>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-400">
          Selected {selectedList.length} of {datasets.length} datasets
        </div>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter datasets…"
          className="border border-gray-700 bg-[#111827] px-2 py-1 text-sm rounded-md text-white w-56 focus:outline-none focus:border-[#defe47]/70"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
        {filteredDatasets.map(ds => (
          <label key={ds.filename} className="border border-gray-800 rounded-lg p-3 flex items-center gap-3 bg-[#0d1421] hover:border-[#defe47]/50 cursor-pointer transition-colors">
            <input
              type="checkbox"
              checked={!!selected[ds.filename]}
              onChange={(e) => setSelected(s => ({ ...s, [ds.filename]: e.target.checked }))}
            />
            <span className="font-medium">{ds.filename}</span>
            <span className="text-xs text-gray-400">({ds.task_type})</span>
          </label>
        ))}
      </div>

      {!echoMode && modelCatalog.length > 0 && (
        <div className="mb-8">
          <h2 className="font-semibold text-[#defe47] mb-2">Models</h2>
          <p className="text-xs text-gray-400 mb-3">
            Select specific models to run. If none selected, backend defaults are used.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {modelCatalog.map(m => (
              <label key={m.name} className="border border-gray-800 rounded-lg p-3 flex items-center gap-3 bg-[#0d1421] hover:border-[#defe47]/50 cursor-pointer transition-colors">
                <input
                  type="checkbox"
                  checked={!!modelSelected[m.name]}
                  onChange={(e) => setModelSelected(s => ({ ...s, [m.name]: e.target.checked }))}
                />
                <span className="font-medium">{m.name}</span>
                {m.fn && <span className="text-xs text-gray-400">(fn: {m.fn})</span>}
              </label>
            ))}
          </div>
        </div>
      )}

      {results?.runs && results.runs.length > 0 && (
        <div className="overflow-x-auto border border-gray-800 rounded-lg bg-[#0d1421] p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-gray-300">
              Runs: {results.runs.length} • Models: {modelNames.length}
            </div>
            <button onClick={() => setShowRaw(v => !v)} className="text-sm underline text-[#defe47]">
              {showRaw ? 'Hide' : 'Show'} sample response
            </button>
          </div>
          {showRaw && (
            <pre className="border border-gray-800 rounded-md bg-[#111827] text-[#defe47] p-3 text-xs mb-3 overflow-auto max-h-64">
              {rawJson}
            </pre>
          )}
          <table className="min-w-full border border-gray-800 text-sm">
            <thead className="bg-[#111827] text-[#defe47]">
              <tr>
                <th className="border border-gray-800 px-2 py-2 text-left">Dataset</th>
                <th className="border border-gray-800 px-2 py-2 text-left">Task</th>
                <th className="border border-gray-800 px-2 py-2 text-left">Count</th>
                {modelNames.map(m => (
                  <th className="border border-gray-800 px-2 py-2 text-left" key={m}>{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.runs.map((r) => (
                <tr key={r.dataset} className="hover:bg-[#111827]">
                  <td className="border border-gray-800 px-2 py-1">{r.dataset}</td>
                  <td className="border border-gray-800 px-2 py-1">{r.task_type}</td>
                  <td className="border border-gray-800 px-2 py-1">{r.count}</td>
                  {modelNames.map((m) => {
                    const res = r.results?.[m];
                    if (!res) return <td className="border border-gray-800 px-2 py-1" key={m}>—</td>;
                    const display = formatMetricCell(res);
                    return <td className="border border-gray-800 px-2 py-1" key={m}>{display}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
    </div>
  );
}
