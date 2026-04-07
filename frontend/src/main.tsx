import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import Layout from "./components/layout/Layout";
import HomePage from "./pages/HomePage";
import SearchPage from "./pages/SearchPage";
import BuilderPage from "./pages/BuilderPage";
import BuilderChoosePage from "./pages/BuilderChoosePage";
import ComparePage from "./pages/ComparePage";
import CommunityPage from "./pages/CommunityPage";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/"        element={<HomePage />} />
          <Route path="/search"  element={<SearchPage />} />
          <Route path="/builder" element={<BuilderPage />} />
          <Route path="/builder/choose" element={<BuilderChoosePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/community" element={<CommunityPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
