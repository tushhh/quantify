import { redirect } from "next/navigation";

// /screener duplicated /predict (same data, same API calls); the picks live on /predict.
export default function ScreenerPage() {
  redirect("/predict");
}
