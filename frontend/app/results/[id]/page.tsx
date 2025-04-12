"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

// Updated interface to match backend response
interface FactCheckAnalysis {
  verification_status: string;
  confidence_score: number;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  reasoning: string;
  evidence_gaps: string[];
  recommendations: string[];
  sources: string[];
}

interface FactCheck {
  question: { question: string };
  analysis: FactCheckAnalysis;
}

interface AnalysisResult {
  initial_questions?: string[]; // Renamed from questions
  fact_checks?: FactCheck[];   // Renamed from facts and typed
  follow_up_questions?: string[]; // Added, though currently unused
  recommendations?: string[];   // Added, though currently unused
  metadata?: any;              // Added, though currently unused
  error?: string;
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Retrieve the analysis result from localStorage
    const savedAnalysis = localStorage.getItem('lastAnalysis')
    if (savedAnalysis) {
      try {
        const parsedResult = JSON.parse(savedAnalysis);
        console.log("Parsed result from localStorage:", parsedResult); // Debug log
        setResult(parsedResult);
      } catch (e) {
        console.error("Error parsing saved analysis:", e);
        // Handle potential parsing error (e.g., invalid JSON)
        setResult({ error: "Failed to load saved analysis results." })
      }
    }
    setLoading(false)
  }, [])

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 flex justify-center items-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (!result) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Alert variant="destructive">
          <AlertTitle>Analysis Not Found</AlertTitle>
          <AlertDescription>
            We couldn't find the analysis results. Please try analyzing your content again.
          </AlertDescription>
        </Alert>
        <Button onClick={() => router.push('/')} className="mt-4">
          Back to Analyzer
        </Button>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>Analysis Results</CardTitle>
        </CardHeader>
        <CardContent>
          {result.error ? (
            <Alert variant="destructive">
              <AlertTitle>Analysis Failed</AlertTitle>
              <AlertDescription>{result.error}</AlertDescription>
            </Alert>
          ) : (
            <>
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Initial Questions Generated</h3>
                {result.initial_questions && result.initial_questions.length > 0 ? (
                  <ul className="list-disc pl-6 space-y-2">
                    {result.initial_questions.map((question, index) => (
                      <li key={index}>{question}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500">No initial questions were generated.</p>
                )}
              </div>

              <div>
                <h3 className="text-lg font-semibold mb-2">Fact Checking Results</h3>
                {result.fact_checks && result.fact_checks.length > 0 ? (
                  <div className="space-y-4">
                    {result.fact_checks.map((factCheck, index) => (
                      <div key={index} className="border p-4 rounded-lg bg-gray-50/50">
                        <p className="font-medium mb-3"><span className="font-semibold">Q:</span> {factCheck.question?.question || "Question not available"}</p>
                        
                        <p className="mb-1"><span className="font-semibold">Status:</span> {factCheck.analysis?.verification_status || "N/A"} (Confidence: {factCheck.analysis?.confidence_score?.toFixed(2) ?? "N/A"})</p>
                        
                        {factCheck.analysis?.reasoning && (
                           <p className="text-sm text-gray-700 my-2"><span className="font-semibold">Reasoning:</span> {factCheck.analysis.reasoning}</p>
                        )}

                        {factCheck.analysis?.supporting_evidence && factCheck.analysis.supporting_evidence.length > 0 && (
                          <div className="mt-2"><p className="text-sm font-semibold">Supporting Evidence:</p>
                            <ul className="list-disc pl-6 text-sm text-green-700">{factCheck.analysis.supporting_evidence.map((ev, i) => <li key={`sup-${i}`}>{ev}</li>)}</ul>
                          </div>
                        )}

                        {factCheck.analysis?.contradicting_evidence && factCheck.analysis.contradicting_evidence.length > 0 && (
                          <div className="mt-2"><p className="text-sm font-semibold">Contradicting Evidence:</p>
                            <ul className="list-disc pl-6 text-sm text-red-700">{factCheck.analysis.contradicting_evidence.map((ev, i) => <li key={`con-${i}`}>{ev}</li>)}</ul>
                          </div>
                        )}

                        {factCheck.analysis?.evidence_gaps && factCheck.analysis.evidence_gaps.length > 0 && (
                          <div className="mt-2"><p className="text-sm font-semibold">Evidence Gaps:</p>
                            <ul className="list-disc pl-6 text-sm text-yellow-700">{factCheck.analysis.evidence_gaps.map((ev, i) => <li key={`gap-${i}`}>{ev}</li>)}</ul>
                          </div>
                        )}

                        {factCheck.analysis?.sources && factCheck.analysis.sources.length > 0 && (
                          <div className="mt-3"><p className="text-sm font-semibold">Sources Used:</p>
                            <ul className="list-disc pl-6 text-sm text-blue-600">{factCheck.analysis.sources.map((source, i) => <li key={`src-${i}`}>{source.startsWith('http') ? <a href={source} target="_blank" rel="noopener noreferrer" className="hover:underline">{source}</a> : source}</li>)}</ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No fact checks were performed or results are available.</p>
                )}
              </div>
            </>
          )}
          
          <Button onClick={() => router.push('/')} className="mt-6">
            Analyze Another Text
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
