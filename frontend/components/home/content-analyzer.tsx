"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Upload, FileText } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import ImageUploader from "@/components/analyzers/image-uploader"
import { processContent } from "@/lib/api"

export default function ContentAnalyzer() {
  const [text, setText] = useState("")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [activeTab, setActiveTab] = useState("text")
  const { toast } = useToast()
  const router = useRouter()

  const handleAnalyzeText = async () => {
    if (!text.trim()) {
      toast({
        title: "Empty content",
        description: "Please enter some text to analyse",
        variant: "destructive",
      })
      return
    }

    setIsAnalyzing(true)

    try {
      const result = await processContent(text)
      
      if (result.error) {
        throw new Error(result.error)
      }

      // Store the analysis result in localStorage for the results page
      localStorage.setItem('lastAnalysis', JSON.stringify(result))
      
      // Generate a simple ID based on timestamp
      const analysisId = Date.now().toString()
      
      // Navigate to results page
      router.push(`/results/${analysisId}`)
    } catch (error) {
      toast({
        title: "Analysis failed",
        description: error instanceof Error ? error.message : "There was an error analyzing your content. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <section id="analyzer">
      <Card className="max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle>Check for Misinformation</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="text" onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2 mb-6">
              <TabsTrigger value="text">
                <FileText className="mr-2 h-4 w-4" />
                Text
              </TabsTrigger>
              <TabsTrigger value="image">
                <Upload className="mr-2 h-4 w-4" />
                Image
              </TabsTrigger>
            </TabsList>

            <TabsContent value="text">
              <Textarea
                placeholder="Paste or type the text you want to analyse..."
                className="min-h-[200px]"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </TabsContent>

            <TabsContent value="image">
              <ImageUploader key={activeTab} />
            </TabsContent>
          </Tabs>
        </CardContent>

        {activeTab === "text" && (
          <CardFooter>
            <Button
              onClick={handleAnalyzeText}
              disabled={isAnalyzing || !text.trim()}
              className="w-full"
            >
              {isAnalyzing ? "Analysing..." : "Analyse"}
            </Button>
          </CardFooter>
        )}
      </Card>
    </section>
  )
}
