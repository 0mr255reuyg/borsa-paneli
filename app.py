import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { GoogleGenAI, Type } from "@google/genai";
import { 
  LineChart, 
  Search, 
  Activity, 
  BarChart2, 
  TrendingUp, 
  AlertCircle,
  CheckCircle2,
  XCircle,
  Play,
  Loader2,
  Info
} from 'lucide-react';

// --- Constants & Config ---

// A subset of BIST stocks for demonstration to avoid hitting rate limits immediately.
// In a full production build, this would include all XTUM.
const DEFAULT_BIST_STOCKS = [
  "THYAO", "ASELS", "KCHOL", "AKBNK", "GARAN", "SISE", "EREGL", "TUPRS", "BIMAS", "SASA",
  "HEKTS", "PETKM", "ISCTR", "SAHOL", "FROTO", "YKBNK", "ENKAI", "TOASO", "PGSUS", "TCELL",
  "ASTOR", "EUPWR", "KONTR", "GESAN", "ODAS", "KOZAL", "KRDMD", "VESTL", "ARCLK", "ALARK"
];

// --- Types ---

interface ScoringDetail {
  criteria: string;
  score: number;
  maxScore: number;
  reason: string;
}

interface StockAnalysis {
  symbol: string;
  price: number;
  changePct: number;
  swingScore: number;
  summary: string;
  details: {
    rsi: number;
    macd_bullish: boolean;
    volume_surge: boolean;
    adx_trend: boolean;
    supertrend_buy: boolean;
    bollinger_squeeze: boolean;
  };
  scoringBreakdown: ScoringDetail[];
  timestamp: string;
}

// --- Gemini API Service ---

const getGeminiClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("API Key not found");
  return new GoogleGenAI({ apiKey });
};

const analyzeStockWithGemini = async (symbol: string): Promise<StockAnalysis> => {
  const ai = getGeminiClient();
  const ticker = symbol.endsWith('.IS') ? symbol : `${symbol}.IS`;

  const systemInstruction = `
    You are an expert Technical Analyst for Borsa Istanbul (BIST).
    Your task is to search for real-time technical indicators for the stock ${ticker} and calculate a "Swing Trading Score" (0-100) based on EXACT rules.
    
    CRITICAL: You MUST use the 'googleSearch' tool to find the LATEST price and indicator values (RSI, MACD, Volume, ADX, SuperTrend, Bollinger Bands) for ${ticker}.
    
    SCORING ALGORITHM (Total 100 Points):
    
    1. RSI (14) [Max 20 Pts]:
       - 55-60: +20 (Perfect)
       - 50-55 OR 60-65: +15 (Good)
       - 45-50 OR 65-70: +10 (Medium)
       - Else: 0
       
    2. MACD (12, 26, 9) [Max 20 Pts]:
       - Bullish Cross (MACD > Signal) AND MACD > 0 AND Histogram Increasing: +20
       - MACD > Signal AND MACD > 0: +15
       - MACD > Signal (but < 0): +12
       - Else: 0
       
    3. Volume & MFI (14) [Max 20 Pts]:
       - Vol > (Avg20 * 1.5) AND MFI 50-80: +20 (Whale)
       - Vol > (Avg20 * 1.2) AND MFI Increasing: +15
       - Vol > Avg20: +10
       - Else: 0
       
    4. ADX (14) [Max 15 Pts]:
       - ADX > 25 AND DI+ > DI-: +15 (Strong Trend)
       - ADX 20-25 AND ADX Rising: +10
       - Else: 0
       
    5. SuperTrend (7, 3) [Max 15 Pts]:
       - Price > SuperTrend (Buy Signal): +15
       - Else: 0
       
    6. Bollinger Bands (20, 2) [Max 10 Pts]:
       - %B > 0.8: +10
       - Squeeze (Low Bandwidth) AND Price > Mid: +8
       - %B 0.5-0.8: +5
       - Else: 0
  `;

  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: `Analyze ${ticker}. Fetch current data and apply the scoring rules. Return the result in JSON format.`,
    config: {
      tools: [{ googleSearch: {} }],
      systemInstruction: systemInstruction,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          symbol: { type: Type.STRING },
          price: { type: Type.NUMBER },
          changePct: { type: Type.NUMBER },
          swingScore: { type: Type.NUMBER },
          summary: { type: Type.STRING },
          details: {
            type: Type.OBJECT,
            properties: {
              rsi: { type: Type.NUMBER },
              macd_bullish: { type: Type.BOOLEAN },
              volume_surge: { type: Type.BOOLEAN },
              adx_trend: { type: Type.BOOLEAN },
              supertrend_buy: { type: Type.BOOLEAN },
              bollinger_squeeze: { type: Type.BOOLEAN },
            }
          },
          scoringBreakdown: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                criteria: { type: Type.STRING },
                score: { type: Type.NUMBER },
                maxScore: { type: Type.NUMBER },
                reason: { type: Type.STRING }
              }
            }
          }
        }
      }
    }
  });

  if (response.text) {
    const data = JSON.parse(response.text) as StockAnalysis;
    data.timestamp = new Date().toLocaleTimeString();
    return data;
  }
  throw new Error("No data returned from AI");
};

// --- Components ---

const ProgressBar = ({ progress, total, currentStock }: { progress: number, total: number, currentStock: string }) => (
  <div className="w-full bg-slate-800 rounded-lg p-4 mb-6 border border-slate-700 animate-in fade-in slide-in-from-top-4">
    <div className="flex justify-between mb-2 text-sm text-slate-300">
      <span>Analyzing Markets...</span>
      <span>{Math.round((progress / total) * 100)}%</span>
    </div>
    <div className="w-full bg-slate-700 rounded-full h-2.5 mb-2">
      <div 
        className="bg-blue-500 h-2.5 rounded-full transition-all duration-300 ease-out" 
        style={{ width: `${(progress / total) * 100}%` }}
      ></div>
    </div>
    <div className="text-xs text-slate-400 flex items-center gap-2">
      <Loader2 className="w-3 h-3 animate-spin" />
      Processing: <span className="font-mono text-blue-400">{currentStock}.IS</span>
    </div>
  </div>
);

const ScoreBadge = ({ score }: { score: number }) => {
  let colorClass = "bg-slate-700 text-slate-300 border-slate-600";
  if (score >= 75) colorClass = "bg-green-900/30 text-green-400 border-green-700/50";
  else if (score >= 50) colorClass = "bg-yellow-900/30 text-yellow-400 border-yellow-700/50";
  else if (score > 0) colorClass = "bg-red-900/30 text-red-400 border-red-700/50";

  return (
    <div className={`px-3 py-1 rounded-full border ${colorClass} font-bold text-sm inline-flex items-center gap-1`}>
      {score} / 100
    </div>
  );
};

const StockDetailView = ({ data, onClose }: { data: StockAnalysis, onClose: () => void }) => {
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex justify-between items-start sticky top-0 bg-slate-900 z-10">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-3xl font-bold text-white tracking-tight">{data.symbol}.IS</h2>
              <ScoreBadge score={data.swingScore} />
            </div>
            <div className="flex items-center gap-4 text-slate-400">
              <span className="text-2xl font-mono text-white">{data.price} TL</span>
              <span className={`flex items-center gap-1 ${data.changePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {data.changePct >= 0 ? <TrendingUp size={16} /> : <TrendingUp size={16} className="rotate-180" />}
                {data.changePct}%
              </span>
              <span className="text-sm border-l border-slate-700 pl-4">Updated: {data.timestamp}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors">
            <XCircle size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Main Summary */}
          <div className="md:col-span-2 space-y-6">
            <div className="bg-slate-800/50 rounded-lg p-5 border border-slate-700">
              <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <Activity className="text-blue-400" size={20} />
                AI Analysis Summary
              </h3>
              <p className="text-slate-300 leading-relaxed">{data.summary}</p>
            </div>

            <div className="space-y-3">
               <h3 className="text-lg font-semibold text-white mb-3">Scoring Breakdown</h3>
               {data.scoringBreakdown.map((item, idx) => (
                 <div key={idx} className="bg-slate-800/30 p-4 rounded-lg border border-slate-700/50 flex flex-col gap-2">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-slate-200">{item.criteria}</span>
                      <span className={`text-sm font-bold px-2 py-0.5 rounded ${item.score > 0 ? 'bg-green-900/50 text-green-400' : 'bg-slate-700 text-slate-400'}`}>
                        +{item.score} Pts
                      </span>
                    </div>
                    <p className="text-sm text-slate-400">{item.reason}</p>
                 </div>
               ))}
            </div>
          </div>

          {/* Key Metrics Sidebar */}
          <div className="space-y-4">
             <div className="bg-slate-800/50 p-5 rounded-lg border border-slate-700">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <BarChart2 className="text-purple-400" size={20} />
                  Technical Indicators
                </h3>
                
                <div className="space-y-4">
                  <div className="flex justify-between items-center pb-2 border-b border-slate-700/50">
                    <span className="text-slate-400 text-sm">RSI (14)</span>
                    <span className={`font-mono font-bold ${data.details.rsi > 70 || data.details.rsi < 30 ? 'text-yellow-400' : 'text-white'}`}>
                      {data.details.rsi?.toFixed(2)}
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center pb-2 border-b border-slate-700/50">
                    <span className="text-slate-400 text-sm">MACD Signal</span>
                    {data.details.macd_bullish ? 
                      <span className="text-green-400 flex items-center gap-1 text-sm font-bold"><CheckCircle2 size={14}/> Bullish</span> : 
                      <span className="text-slate-500 text-sm">Neutral/Bear</span>
                    }
                  </div>

                  <div className="flex justify-between items-center pb-2 border-b border-slate-700/50">
                    <span className="text-slate-400 text-sm">Volume</span>
                    {data.details.volume_surge ? 
                      <span className="text-green-400 flex items-center gap-1 text-sm font-bold"><Activity size={14}/> High</span> : 
                      <span className="text-slate-500 text-sm">Normal</span>
                    }
                  </div>

                   <div className="flex justify-between items-center pb-2 border-b border-slate-700/50">
                    <span className="text-slate-400 text-sm">SuperTrend</span>
                    {data.details.supertrend_buy ? 
                      <span className="text-green-400 flex items-center gap-1 text-sm font-bold">BUY</span> : 
                      <span className="text-red-400 flex items-center gap-1 text-sm font-bold">SELL</span>
                    }
                  </div>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-sm">Bollinger</span>
                    {data.details.bollinger_squeeze ? 
                      <span className="text-blue-400 flex items-center gap-1 text-sm font-bold">Squeeze</span> : 
                      <span className="text-slate-500 text-sm">Normal</span>
                    }
                  </div>
                </div>
             </div>
             
             <div className="bg-blue-900/20 p-4 rounded-lg border border-blue-800/30 text-xs text-blue-200">
               <div className="flex gap-2 mb-2">
                 <Info size={16} />
                 <span className="font-bold">Pro Tip</span>
               </div>
               High Swing Scores (>70) indicate a strong probability of short-term upward momentum based on multiple confirming indicators.
             </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<StockAnalysis[]>([]);
  const [currentProcessing, setCurrentProcessing] = useState<string>("");
  const [progress, setProgress] = useState(0);
  const [selectedStock, setSelectedStock] = useState<StockAnalysis | null>(null);
  const [stocksToScan, setStocksToScan] = useState<string[]>(DEFAULT_BIST_STOCKS);

  const startAnalysis = async () => {
    setIsRunning(true);
    setResults([]);
    setProgress(0);

    for (let i = 0; i < stocksToScan.length; i++) {
      const stock = stocksToScan[i];
      setCurrentProcessing(stock);
      
      try {
        const result = await analyzeStockWithGemini(stock);
        setResults(prev => [...prev, result].sort((a, b) => b.swingScore - a.swingScore));
      } catch (error) {
        console.error(`Error analyzing ${stock}:`, error);
        // Continue to next stock even if one fails
      }
      
      setProgress(i + 1);
    }

    setIsRunning(false);
    setCurrentProcessing("");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans flex flex-col md:flex-row">
      
      {/* Sidebar */}
      <div className="w-full md:w-64 bg-slate-900 border-r border-slate-800 p-6 flex flex-col shrink-0">
        <div className="mb-8 flex items-center gap-2 text-blue-500">
          <LineChart size={28} />
          <h1 className="text-xl font-bold text-white tracking-wider">BIST<span className="font-light">SWING</span></h1>
        </div>

        <div className="space-y-6">
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">Settings</label>
            <div className="bg-slate-800/50 p-3 rounded text-sm text-slate-400 mb-2">
              <div className="flex justify-between mb-1">
                <span>Universe:</span>
                <span className="text-white">BIST 30+</span>
              </div>
              <div className="flex justify-between">
                <span>Count:</span>
                <span className="text-white">{stocksToScan.length} Stocks</span>
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Note: Full BIST All (XTUM) scan is limited in this demo environment.
            </p>
          </div>

          <button
            onClick={startAnalysis}
            disabled={isRunning}
            className={`w-full py-3 px-4 rounded-lg font-bold flex items-center justify-center gap-2 transition-all shadow-lg
              ${isRunning 
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-500 text-white hover:shadow-blue-500/20 active:scale-95'
              }`}
          >
            {isRunning ? (
              <>
                <Loader2 className="animate-spin" size={18} />
                Scanning...
              </>
            ) : (
              <>
                <Play size={18} fill="currentColor" />
                Start Analysis
              </>
            )}
          </button>
        </div>
        
        <div className="mt-auto pt-6 border-t border-slate-800">
          <p className="text-xs text-slate-600 text-center">
            Powered by Gemini 2.5 & Streamlit-Logic
          </p>
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 p-6 md:p-10 overflow-y-auto">
        
        {/* Progress Section */}
        {isRunning && (
          <ProgressBar 
            progress={progress} 
            total={stocksToScan.length} 
            currentStock={currentProcessing} 
          />
        )}

        {/* Empty State */}
        {!isRunning && results.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4 min-h-[400px]">
            <Search size={64} className="text-slate-700 mb-4" />
            <h2 className="text-2xl font-bold text-slate-400">Ready to Scan Markets</h2>
            <p className="max-w-md text-center">
              Click the "Start Analysis" button to scan the BIST index using the 100-point Swing Trading Algorithm.
            </p>
          </div>
        )}

        {/* Results Table */}
        {results.length > 0 && (
          <div className="animate-in fade-in slide-in-from-bottom-4">
             <div className="flex justify-between items-end mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-white">Market Opportunities</h2>
                  <p className="text-slate-400">Sorted by Swing Score (Highest to Lowest)</p>
                </div>
                <div className="text-sm text-slate-500">
                  {results.length} results found
                </div>
             </div>

             <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
               <div className="overflow-x-auto">
                 <table className="w-full text-left border-collapse">
                   <thead>
                     <tr className="bg-slate-800/50 text-slate-400 text-sm uppercase tracking-wider">
                       <th className="p-4 font-semibold">Symbol</th>
                       <th className="p-4 font-semibold text-right">Price</th>
                       <th className="p-4 font-semibold text-right">Change</th>
                       <th className="p-4 font-semibold text-center">Swing Score</th>
                       <th className="p-4 font-semibold text-center">Action</th>
                     </tr>
                   </thead>
                   <tbody className="divide-y divide-slate-800">
                     {results.map((stock) => (
                       <tr 
                          key={stock.symbol} 
                          className="hover:bg-slate-800/30 transition-colors group cursor-pointer"
                          onClick={() => setSelectedStock(stock)}
                       >
                         <td className="p-4">
                           <div className="font-bold text-white">{stock.symbol}.IS</div>
                           <div className="text-xs text-slate-500">Borsa Istanbul</div>
                         </td>
                         <td className="p-4 text-right font-mono text-slate-300">
                           {stock.price.toFixed(2)} ₺
                         </td>
                         <td className={`p-4 text-right font-mono font-medium ${stock.changePct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                           {stock.changePct > 0 ? '+' : ''}{stock.changePct}%
                         </td>
                         <td className="p-4 text-center">
                           <ScoreBadge score={stock.swingScore} />
                         </td>
                         <td className="p-4 text-center">
                           <button 
                            onClick={(e) => { e.stopPropagation(); setSelectedStock(stock); }}
                            className="text-blue-400 hover:text-blue-300 hover:bg-blue-900/30 p-2 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                           >
                             Details
                           </button>
                         </td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               </div>
             </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedStock && (
        <StockDetailView 
          data={selectedStock} 
          onClose={() => setSelectedStock(null)} 
        />
      )}
    </div>
  );
}
