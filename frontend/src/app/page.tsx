import { redirect } from "next/navigation";

export default function Home() {
  // Auth is resolved client-side in the (app) layout; send everyone to the
  // dashboard, which bounces unauthenticated users to /login.
  redirect("/dashboard");
}
