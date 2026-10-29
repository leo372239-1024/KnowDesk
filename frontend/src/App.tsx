import { Layout, Menu } from "antd";
import { BookOutlined, CommentOutlined, ExperimentOutlined, FileTextOutlined } from "@ant-design/icons";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import EvalPage from "./pages/EvalPage";
import LoginPage from "./pages/LoginPage";
import { getToken } from "./api/client";

const { Sider, Content } = Layout;

const MENU_ITEMS = [
  { key: "/chat", icon: <CommentOutlined />, label: <Link to="/chat">智能问答</Link> },
  { key: "/documents", icon: <FileTextOutlined />, label: <Link to="/documents">文档管理</Link> },
  { key: "/eval", icon: <ExperimentOutlined />, label: <Link to="/eval">评测中心</Link> },
];

function Shell() {
  const location = useLocation();
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" width={220}>
        <div style={{ color: "#fff", fontSize: 18, fontWeight: 600, padding: "20px 16px" }}>
          <BookOutlined /> KnowDesk
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={MENU_ITEMS} />
      </Sider>
      <Layout>
        <Content style={{ margin: 24, background: "#fff", borderRadius: 8, padding: 24 }}>
          <Routes>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/eval" element={<EvalPage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  const authed = !!getToken();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={authed ? <Shell /> : <Navigate to="/login" replace />} />
    </Routes>
  );
}
