import { z } from "zod";

export const CitationSchema = z.object({
  chunk_id: z.string(),
  document_id: z.string(),
  section_path: z.string().default(""),
  page_num: z.number().nullable().optional(),
  bbox: z.record(z.unknown()).nullable().optional(),
  snippet: z.string().default(""),
});
export type Citation = z.infer<typeof CitationSchema>;

export const ChatResponseSchema = z.object({
  answer: z.string(),
  citations: z.array(CitationSchema),
  refused: z.boolean(),
  trace_id: z.string(),
  evidence_score: z.number(),
  degraded: z.boolean().default(false),
});
export type ChatResponse = z.infer<typeof ChatResponseSchema>;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  refused: boolean;
  trace_id?: string;
  message_id?: string;
  feedback?: number | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageRecord {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  refused: boolean;
  feedback: number | null;
  created_at: string;
}

export interface TraceSpan {
  name: string;
  start_ms: number;
  elapsed_ms?: number;
  [key: string]: unknown;
}

export interface TraceDetail {
  trace_id: string;
  spans: TraceSpan[];
  created_at: string;
}
