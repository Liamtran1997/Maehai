import { ShopHeader } from "../../../components/ShopHeader";
import { OrderView } from "../../../components/OrderView";

export const metadata = { title: "คำสั่งซื้อของคุณ | ร้านหมูยอแม่ฮาย", robots: { index: false } };

export default async function OrderPage({ params, searchParams }: { params: Promise<{ number: string }>; searchParams: Promise<{ t?: string }> }) {
  const { number } = await params;
  const { t } = await searchParams;
  return (
    <>
      <ShopHeader />
      <OrderView number={number} token={t ?? ""} />
    </>
  );
}
