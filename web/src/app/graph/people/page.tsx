import { redirect } from "next/navigation";

import { requirePageSession } from "@/lib/auth/page-session";

/** Legacy path — People is top-level at /people. */
export default async function GraphPeopleRedirect() {
  await requirePageSession();
  redirect("/people");
}
