import { Navigate, Route, Routes } from "react-router";

import MainLayout from "@/layouts/MainLayout";
import PrivateRoutes from "@/routes/PrivateRoutes";
import Login from "@/pages/auth/Login";
import Workspace from "@/pages/workspace/Workspace";
import VideoDetail from "@/pages/video/VideoDetail";
import Chat from "@/pages/chat/Chat";
import Profile from "@/pages/profile/Profile";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<PrivateRoutes />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/workspace" replace />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/video/:videoId" element={<VideoDetail />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:conversationId" element={<Chat />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/library" element={<Navigate to="/workspace" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
