import { redirect } from "next/navigation";

// Trade tracking lives on /portfolio. A server redirect (as /dashboard does)
// replaces the old client-side redirect, which still fetched the trade list.
export default function TradesPage() {
  redirect("/portfolio");
}
