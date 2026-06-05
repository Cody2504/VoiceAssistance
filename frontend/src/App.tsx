import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";

import MainLayout from "@/layouts/MainLayout";
import PublicLayout from "@/layouts/PublicLayout";
import AuthLayout from "@/layouts/AuthLayout";
import PrivateRoutes from "@/routes/PrivateRoutes";
import Home from "@/pages/home/Home";
import Landing from "@/pages/landing/Landing";
import Pricing from "@/pages/pricing/Pricing";
import PricingCalculator from "@/pages/pricing/PricingCalculator";
import Solutions from "@/pages/solutions/Solutions";
import SolutionPage from "@/pages/solutions/SolutionPage";
import { SOLUTIONS } from "@/pages/solutions/industryData";
import Build from "@/pages/build/Build";
import Library from "@/pages/playground/Library";
import Search from "@/pages/playground/Search";
import Analyze from "@/pages/playground/Analyze";
import Ground from "@/pages/playground/Ground";
import Segment from "@/pages/playground/Segment";
import Recommend from "@/pages/playground/Recommend";
import Highlights from "@/pages/playground/Highlights";
import Moderate from "@/pages/playground/Moderate";
import Sounds from "@/pages/playground/Sounds";
import Login from "@/pages/auth/Login";
import Signup from "@/pages/auth/Signup";
import Workspace from "@/pages/workspace/Workspace";
import VideoDetail from "@/pages/video/VideoDetail";
import Profile from "@/pages/profile/Profile";
import S3TestPage from "@/pages/s3-test/S3TestPage";
import Overview from "@/pages/overview/Overview";
import Indexes from "@/pages/indexes/Indexes";
import IndexDetail from "@/pages/indexes/IndexDetail";
import Assets from "@/pages/assets/Assets";
import Entities from "@/pages/entities/Entities";
import Examples from "@/pages/examples/Examples";
import SettingsLayout from "@/pages/settings/SettingsLayout";
import BillingPlan from "@/pages/settings/BillingPlan";
import { Organization, APIKeysPage, Usage, RateLimits, Webhooks, ProfilePage } from "@/pages/settings/SettingsStubs";

/**
 * Smoothly scroll to the #anchor in the URL after navigation. react-router does
 * not do this on its own. We retry across a few frames because the target
 * section may mount a tick after a cross-page navigation. scroll-mt-* on the
 * targets keeps them clear of the sticky navbar.
 */
function ScrollToHash() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const id = decodeURIComponent(hash.slice(1));
    let raf = 0;
    let tries = 0;
    const tryScroll = () => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      } else if (tries++ < 20) {
        raf = requestAnimationFrame(tryScroll);
      }
    };
    raf = requestAnimationFrame(tryScroll);
    return () => cancelAnimationFrame(raf);
  }, [pathname, hash]);
  return null;
}

export default function App() {
  return (
    <>
      <ScrollToHash />
      <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/product/product-overview" element={<Landing />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/pricing-calculator" element={<PricingCalculator />} />
        <Route path="/solutions" element={<Solutions />} />
        <Route path="/solutions/media-and-entertainment" element={<SolutionPage data={SOLUTIONS["media-and-entertainment"]} />} />
        <Route path="/solutions/advertising" element={<SolutionPage data={SOLUTIONS.advertising} />} />
        <Route path="/solutions/government-and-security" element={<SolutionPage data={SOLUTIONS["government-and-security"]} />} />
        <Route path="/solutions/automotive" element={<SolutionPage data={SOLUTIONS.automotive} />} />
        <Route path="/build" element={<Build />} />
      </Route>

      <Route element={<AuthLayout />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
      </Route>

      <Route path="/s3-test" element={<S3TestPage />} />

      <Route element={<PrivateRoutes />}>
        <Route element={<MainLayout />}>
          <Route path="/overview" element={<Overview />} />
          <Route path="/indexes" element={<Indexes />} />
          <Route path="/indexes/:indexId" element={<IndexDetail />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/entities" element={<Entities />} />
          <Route path="/examples" element={<Examples />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/video/:videoId" element={<VideoDetail />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/library" element={<Navigate to="/playground/library" replace />} />
          <Route path="/playground" element={<Navigate to="/playground/library" replace />} />
          <Route path="/playground/library" element={<Library />} />
          <Route path="/playground/search" element={<Search />} />
          <Route path="/playground/analyze" element={<Analyze />} />
          <Route path="/playground/ground" element={<Ground />} />
          <Route path="/playground/segment" element={<Segment />} />
          <Route path="/playground/highlights" element={<Highlights />} />
          <Route path="/playground/recommend" element={<Recommend />} />
          <Route path="/playground/moderate" element={<Moderate />} />
          <Route path="/playground/sounds" element={<Sounds />} />
          <Route path="/chat" element={<Navigate to="/workspace" replace />} />
          <Route path="/chat/:conversationId" element={<Navigate to="/workspace" replace />} />

          <Route path="/settings" element={<SettingsLayout />}>
            <Route index element={<Navigate to="/settings/billing" replace />} />
            <Route path="organization" element={<Organization />} />
            <Route path="api-keys" element={<APIKeysPage />} />
            <Route path="billing" element={<BillingPlan />} />
            <Route path="usage" element={<Usage />} />
            <Route path="rate-limits" element={<RateLimits />} />
            <Route path="webhooks" element={<Webhooks />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>

          <Route path="/api-keys" element={<Navigate to="/settings/api-keys" replace />} />
          <Route path="/api-docs" element={<Navigate to="/settings/api-keys" replace />} />
          <Route path="/help" element={<Navigate to="/settings/profile" replace />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
