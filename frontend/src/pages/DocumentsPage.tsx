import { useState } from "react";
import { Table, Tag, Upload, message } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import { useDocuments, useUploadDocument } from "../hooks/useDocuments";

const STATUS_COLOR: Record<string, string> = {
  indexed: "green",
  parsing: "orange",
  failed: "red",
  pending: "default",
};

export default function DocumentsPage() {
  const { data, isLoading } = useDocuments();
  const uploadMutation = useUploadDocument();
  const [uploading, setUploading] = useState(false);

  const props: UploadProps = {
    customRequest: async (options) => {
      const file = options.file as File;
      setUploading(true);
      try {
        await uploadMutation.mutateAsync(file);
        message.success(`已上传：${file.name}`);
      } catch {
        message.error("上传失败");
      } finally {
        setUploading(false);
      }
    },
    showUploadList: false,
  };

  const columns = [
    { title: "标题", dataIndex: "title", key: "title" },
    { title: "类型", dataIndex: "file_type", key: "file_type", width: 80 },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: string) => <Tag color={STATUS_COLOR[s] || "default"}>{s}</Tag>,
    },
    { title: "分块数", dataIndex: "chunk_count", key: "chunk_count", width: 90 },
    { title: "部门", dataIndex: "department", key: "department", width: 100 },
  ];

  return (
    <div>
      <h2>文档管理</h2>
      <Upload.Dragger {...props} style={{ marginBottom: 16 }}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
        <p className="ant-upload-hint">支持 PDF、Word、Markdown、Excel、TXT</p>
      </Upload.Dragger>
      <Table
        rowKey="id"
        loading={isLoading || uploading}
        columns={columns}
        dataSource={data?.items ?? []}
        pagination={{ pageSize: 10 }}
      />
    </div>
  );
}
