import { Tag, Tooltip } from "antd";
import { Citation as CitationType } from "../types/chat";

interface CitationProps {
  citation: CitationType;
}

export function Citation({ citation }: CitationProps) {
  const tooltip = (
    <div>
      <div>{citation.snippet || citation.section_path || "原文片段"}</div>
      {citation.page_num != null && <div>第 {citation.page_num} 页</div>}
    </div>
  );
  return (
    <Tooltip title={tooltip}>
      <Tag color="blue" style={{ cursor: "pointer" }}>
        [{citation.chunk_id}]
      </Tag>
    </Tooltip>
  );
}
