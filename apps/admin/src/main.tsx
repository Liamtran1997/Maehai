import "@maehai/ui/styles.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuthProvider } from "./lib/auth";
import { Account } from "./pages/Account";
import { Categories } from "./pages/Categories";
import { Warehouse } from "./pages/Warehouse";
import { NewSlipPage } from "./pages/warehouse/NewSlip";
import { SlipPage } from "./pages/warehouse/SlipPage";
import { Promotions } from "./pages/Promotions";
import { Staff } from "./pages/Staff";
import { RequirePermission } from "./components/RequirePermission";
import { Campaigns } from "./pages/Campaigns";
import { Coupons } from "./pages/Coupons";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { OrderDetail } from "./pages/OrderDetail";
import { Orders } from "./pages/Orders";
import { Products } from "./pages/Products";

// The icon path depends on the base (/admin/ in Docker), so the link is added here rather than in index.html.
for (const [rel, sizes, file] of [["icon", "32x32", "icon-32.png"], ["apple-touch-icon", "192x192", "icon-192.png"]] as const) {
  const link = document.createElement("link");
  link.rel = rel;
  link.sizes = sizes;
  link.type = "image/png";
  link.href = `${import.meta.env.BASE_URL}brand/${file}`;
  document.head.appendChild(link);
}

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: true } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="orders" element={<RequirePermission perm="orders.view"><Orders /></RequirePermission>} />
              <Route path="orders/:number" element={<RequirePermission perm="orders.view"><OrderDetail /></RequirePermission>} />
              <Route path="products" element={<RequirePermission perm="catalog.view"><Products /></RequirePermission>} />
              <Route path="inventory" element={<Navigate to="/warehouse?tab=stock" replace />} />
              <Route path="warehouse" element={<RequirePermission perm="inventory.view"><Warehouse /></RequirePermission>} />
              <Route path="warehouse/documents/:number" element={<RequirePermission perm="inventory.view"><SlipPage /></RequirePermission>} />
              <Route path="warehouse/new/:kind" element={<RequirePermission perm="inventory.view"><NewSlipPage /></RequirePermission>} />
              <Route path="categories" element={<RequirePermission perm="catalog.view"><Categories /></RequirePermission>} />
              <Route path="promotions" element={<RequirePermission perm="catalog.view"><Promotions /></RequirePermission>} />
              <Route path="coupons" element={<RequirePermission perm="coupons.view"><Coupons /></RequirePermission>} />
              <Route path="campaigns" element={<RequirePermission perm="reports.view"><Campaigns /></RequirePermission>} />
              <Route path="staff" element={<RequirePermission perm="staff.manage"><Staff /></RequirePermission>} />
              <Route path="account" element={<Account />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
