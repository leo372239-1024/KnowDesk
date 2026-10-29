import { z } from "zod";

export const DocumentSchema = z.object({
  id: z.string(),
  title: z.string(),
  file_type: z.string(),
  status: z.string(),
  department: z.string(),
  chunk_count: z.number(),
  version: z.string(),
  created_at: z.string(),
});
export type DocumentItem = z.infer<typeof DocumentSchema>;

export const DocumentListSchema = z.object({
  items: z.array(DocumentSchema),
  total: z.number(),
});
export type DocumentList = z.infer<typeof DocumentListSchema>;
